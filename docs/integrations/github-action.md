# GitHub Action

Integrate Codex Aura analysis into your CI/CD pipeline with the official GitHub Action.

## Basic Usage

```yaml
name: Analyze Codebase
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: codex-aura/analyze-action@v1
        with:
          path: '.'
          comment-on-pr: 'true'
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `path` | Path to analyze | No | `.` |
| `edge-types` | Edge types to extract | No | `imports,calls,extends` |
| `output` | Output file path | No | `codex-aura-graph.json` |
| `comment-on-pr` | Add comment to PR with results | No | `false` |

## Outputs

| Output | Description |
|--------|-------------|
| `graph-file` | Path to generated graph file |
| `node-count` | Number of nodes in graph |
| `edge-count` | Number of edges in graph |

## Advanced Usage

### Custom Analysis Configuration

```yaml
- uses: codex-aura/analyze-action@v1
  with:
    path: './src'
    edge-types: 'imports,calls'
    output: 'dependency-graph.json'
    comment-on-pr: 'true'
```

### Using Outputs

```yaml
- uses: codex-aura/analyze-action@v1
  id: analyze
  with:
    path: '.'
- name: Upload artifact
  uses: actions/upload-artifact@v3
  with:
    name: dependency-graph
    path: ${{ steps.analyze.outputs.graph-file }}
- name: Comment on PR
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v6
  with:
    script: |
      const nodeCount = ${{ steps.analyze.outputs.node-count }};
      const edgeCount = ${{ steps.analyze.outputs.edge-count }};
      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: `📊 **Code Analysis Complete**\n\n- Nodes: ${nodeCount}\n- Edges: ${edgeCount}`
      });
```

## Requirements

- Ubuntu runner (recommended)
- Python project with `pyproject.toml` or `requirements.txt`

## Caching

For better performance, combine with pip caching:

```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
- uses: actions/setup-python@v4
  with:
    python-version: '3.11'
- run: pip install -r requirements.txt
- uses: codex-aura/analyze-action@v1
  with:
    path: '.'
```

## Troubleshooting

### Action fails with permission error

Ensure the action has write permissions for PR comments:

```yaml
permissions:
  contents: read
  pull-requests: write
```

### Analysis takes too long

- Use specific `path` instead of `.`
- Exclude test directories with custom configuration
- Consider running on schedule instead of every push