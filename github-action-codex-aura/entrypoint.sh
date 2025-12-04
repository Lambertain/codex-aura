#!/bin/bash
set -e

PATH_TO_ANALYZE=$1
EDGE_TYPES=$2
OUTPUT_FILE=$3
COMMENT_ON_PR=$4

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

# Comment on PR if requested
if [ "$COMMENT_ON_PR" = "true" ]; then
  echo "::group::Adding PR comment"

  # Get PR number from event
  PR_NUMBER=$(jq -r .number $GITHUB_EVENT_PATH)

  # Create comment body
  COMMENT_BODY="## 📊 Codex Aura Analysis

| Metric | Value |
|--------|-------|
| Files | $NODE_COUNT |
| Classes | TBD |
| Functions | TBD |
| Dependencies | $EDGE_COUNT |

### Changed Files Impact
- TBD

[Download full graph](https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts)"

  # Post comment using GitHub API
  curl -X POST \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    "https://api.github.com/repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" \
    -d "{\"body\":\"$COMMENT_BODY\"}"

  echo "::endgroup::"
fi