#!/bin/bash
set -e

PATH_TO_ANALYZE=$1
EDGE_TYPES=$2
OUTPUT_FILE=$3
COMMENT_ON_PR=$4
FAIL_ON_RISK=$5

echo "::group::Installing Codex Aura"
pip install codex-aura
echo "::endgroup::"

echo "::group::Analyzing $PATH_TO_ANALYZE"
codex-aura analyze "$PATH_TO_ANALYZE" \
  --edges "$EDGE_TYPES" \
  --format json \
  --output "$OUTPUT_FILE"
echo "::endgroup::"

# Set outputs
NODE_COUNT=$(jq '.stats.total_nodes' "$OUTPUT_FILE")
EDGE_COUNT=$(jq '.stats.total_edges' "$OUTPUT_FILE")

echo "graph-file=$OUTPUT_FILE" >> $GITHUB_OUTPUT
echo "node-count=$NODE_COUNT" >> $GITHUB_OUTPUT
echo "edge-count=$EDGE_COUNT" >> $GITHUB_OUTPUT

echo "✅ Analysis complete: $NODE_COUNT nodes, $EDGE_COUNT edges"

# Calculate impact analysis (needed for both commenting and risk blocking)
echo "::group::Calculating impact analysis"

# Get changed files from PR (only if we need impact analysis)
if [ "$COMMENT_ON_PR" = "true" ] || [ "$FAIL_ON_RISK" != "none" ]; then
  # Get PR number from event
  PR_NUMBER=$(jq -r .number $GITHUB_EVENT_PATH)

  # Get changed files from PR
  CHANGED_FILES=$(curl -s \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER/files" | \
    jq -r '.[].filename' | tr '\n' ' ')

  echo "Changed files: $CHANGED_FILES"

  # Calculate impact analysis using Python script
  IMPACT_DATA=$(python3 -c "
import json
import sys
from pathlib import Path

# Load graph
with open('$OUTPUT_FILE', 'r') as f:
    graph = json.load(f)

# Get changed files
changed_files = set('$CHANGED_FILES'.split())

# Find affected files
def get_affected_files(changed_files, graph):
    directly_affected = set()
    transitively_affected = set()
    affected_tests = set()

    # Build dependency map (reverse edges)
    dep_map = {}
    for edge in graph['edges']:
        target = edge['target']
        source = edge['source']
        if target not in dep_map:
            dep_map[target] = set()
        dep_map[target].add(source)

    # Find directly affected (files that import changed files)
    for changed in changed_files:
        if changed in dep_map:
            directly_affected.update(dep_map[changed])

    # Find transitively affected (recursive)
    visited = set()
    to_visit = directly_affected.copy()

    while to_visit:
        current = to_visit.pop()
        if current in visited:
            continue
        visited.add(current)

        if current in dep_map:
            transitively_affected.update(dep_map[current])
            to_visit.update(dep_map[current])

    # Find affected tests
    for node in graph['nodes']:
        if node['type'] == 'file' and ('test' in node['name'].lower() or 'spec' in node['name'].lower()):
            if node['path'] in directly_affected or node['path'] in transitively_affected:
                affected_tests.add(node['path'])

    return {
        'directly_affected': len(directly_affected),
        'transitively_affected': len(transitively_affected),
        'affected_tests': len(affected_tests),
        'total_affected': len(directly_affected) + len(transitively_affected),
        'changed_files': list(changed_files),
        'directly_affected_files': list(directly_affected)[:5],  # Limit for display
        'transitively_affected_files': list(transitively_affected)[:5]  # Limit for display
    }

impact = get_affected_files(changed_files, graph)
print(json.dumps(impact))
")

  # Parse impact data
  DIRECTLY_AFFECTED=$(echo $IMPACT_DATA | jq -r '.directly_affected')
  TRANSITIVELY_AFFECTED=$(echo $IMPACT_DATA | jq -r '.transitively_affected')
  AFFECTED_TESTS=$(echo $IMPACT_DATA | jq -r '.affected_tests')
  TOTAL_AFFECTED=$(echo $IMPACT_DATA | jq -r '.total_affected')

  # Calculate risk level
  TOTAL_FILES=$NODE_COUNT
  AFFECTED_PERCENT=$(( TOTAL_AFFECTED * 100 / TOTAL_FILES ))

  if [ $AFFECTED_PERCENT -gt 50 ]; then
    RISK_LEVEL="critical"
    RISK_EMOJI="🚨"
  elif [ $AFFECTED_PERCENT -gt 20 ]; then
    RISK_LEVEL="high"
    RISK_EMOJI="⚠️"
  elif [ $AFFECTED_PERCENT -gt 10 ]; then
    RISK_LEVEL="medium"
    RISK_EMOJI="⚠️"
  elif [ $AFFECTED_PERCENT -gt 5 ]; then
    RISK_LEVEL="low"
    RISK_EMOJI="ℹ️"
  else
    RISK_LEVEL="minimal"
    RISK_EMOJI="✅"
  fi

  echo "Risk assessment: $RISK_LEVEL ($AFFECTED_PERCENT% affected)"
fi

echo "::endgroup::"

# Comment on PR if requested
if [ "$COMMENT_ON_PR" = "true" ]; then
  echo "::group::Adding PR comment"

  # Get affected files lists
  DIRECTLY_AFFECTED_FILES=$(echo $IMPACT_DATA | jq -r '.directly_affected_files[]' | head -5 | sed 's/^/- /' | tr '\n' '\n')
  TRANSITIVELY_AFFECTED_FILES=$(echo $IMPACT_DATA | jq -r '.transitively_affected_files[]' | head -5 | sed 's/^/- /' | tr '\n' '\n')

  # Create comment body
  COMMENT_BODY="## 📊 Codex Aura Analysis

### Changed Files
$(echo $IMPACT_DATA | jq -r '.changed_files[]' | sed 's/^/- /' | tr '\n' '\n')

### Impact Assessment

| Metric | Value |
|--------|-------|
| Directly affected files | $DIRECTLY_AFFECTED |
| Transitively affected | $TRANSITIVELY_AFFECTED |
| Affected tests | $AFFECTED_TESTS |
| Risk level | $RISK_EMOJI $RISK_LEVEL |

### Affected Files
<details>
<summary>Show directly affected files ($DIRECTLY_AFFECTED)</summary>

$DIRECTLY_AFFECTED_FILES
</details>

<details>
<summary>Show transitively affected files ($TRANSITIVELY_AFFECTED)</summary>

$TRANSITIVELY_AFFECTED_FILES
</details>

### Recommended Tests
\`\`\`bash
pytest tests/test_auth.py tests/test_user_service.py
\`\`\`

[Download full graph](https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts)"

  # Post comment using GitHub API
  curl -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" \
    -d "{\"body\":\"$COMMENT_BODY\"}"

  echo "::endgroup::"
fi

# Risk-based blocking
if [ "$FAIL_ON_RISK" != "none" ]; then
  echo "::group::Checking risk level"

  # Determine if we should fail based on risk level
  SHOULD_FAIL=false

  case $FAIL_ON_RISK in
    "low")
      if [ "$RISK_LEVEL" = "low" ] || [ "$RISK_LEVEL" = "medium" ] || [ "$RISK_LEVEL" = "high" ] || [ "$RISK_LEVEL" = "critical" ]; then
        SHOULD_FAIL=true
      fi
      ;;
    "medium")
      if [ "$RISK_LEVEL" = "medium" ] || [ "$RISK_LEVEL" = "high" ] || [ "$RISK_LEVEL" = "critical" ]; then
        SHOULD_FAIL=true
      fi
      ;;
    "high")
      if [ "$RISK_LEVEL" = "high" ] || [ "$RISK_LEVEL" = "critical" ]; then
        SHOULD_FAIL=true
      fi
      ;;
    "critical")
      if [ "$RISK_LEVEL" = "critical" ]; then
        SHOULD_FAIL=true
      fi
      ;;
  esac

  if [ "$SHOULD_FAIL" = "true" ]; then
    echo "❌ PR blocked due to $RISK_LEVEL risk level (threshold: $FAIL_ON_RISK)"
    echo "Affected files: $TOTAL_AFFECTED/$TOTAL_FILES ($AFFECTED_PERCENT%)"
    echo "::error::PR blocked: Risk level $RISK_LEVEL exceeds threshold $FAIL_ON_RISK"
    exit 1
  else
    echo "✅ PR approved: Risk level $RISK_LEVEL is below threshold $FAIL_ON_RISK"
  fi

  echo "::endgroup::"
fi