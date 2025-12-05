# Codex Aura Analyze GitHub Action

This GitHub Action analyzes your codebase and generates a dependency graph using Codex Aura.

## Inputs

- `path`: Path to analyze (default: '.', deprecated: use `paths` for monorepo support)
- `paths`: Paths to analyze (one per line for monorepo support)
- `edge-types`: Edge types to extract (default: 'imports,calls,extends')
- `output`: Output file path (default: 'codex-aura-graph.json')
- `comment-on-pr`: Add comment to PR with results (default: 'false')
- `fail-on-risk`: Risk level to fail on (low/medium/high/critical/none) (default: 'none')
- `upload-artifact`: Upload graph as artifact (default: 'false')
- `artifact-name`: Name for the uploaded artifact (default: 'codex-aura-graph')
- `artifact-retention-days`: Retention days for artifact (default: '30')
- `track-metrics`: Track metrics for trend analysis (default: 'false')
- `cross-package-deps`: Analyze dependencies between packages in monorepo (default: 'false')

## Outputs

- `graph-file`: Path to generated graph file
- `node-count`: Number of nodes in graph
- `edge-count`: Number of edges in graph
- `average-complexity`: Average complexity score
- `hot-spots-count`: Number of hot spots detected

## Usage

### Basic Usage

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

### Graph Artifact Upload (E7-3)

```yaml
name: Analyze and Upload Graph
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: codex-aura/analyze-action@v1
        with:
          path: '.'
          upload-artifact: true
          artifact-name: 'codex-aura-graph'
          artifact-retention-days: 30
          comment-on-pr: 'true'
```

### Scheduled Analysis with Metrics Tracking (E7-4)

```yaml
name: Weekly Code Analysis
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: codex-aura/analyze-action@v1
        with:
          path: '.'
          track-metrics: true
          upload-artifact: true
          comment-on-pr: 'true'
```

### Monorepo Support (E7-5)

```yaml
name: Analyze Monorepo Packages
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: codex-aura/analyze-action@v1
        with:
          paths: |
            packages/auth
            packages/api
            packages/shared
          cross-package-deps: true
          comment-on-pr: 'true'
          upload-artifact: true
```

### Matrix Strategy for Monorepo (E7-6)

```yaml
name: Analyze Monorepo with Matrix
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        package: [auth, api, frontend, shared]
    steps:
      - uses: actions/checkout@v4
      - uses: codex-aura/analyze-action@v1
        with:
          path: packages/${{ matrix.package }}
          output: codex-aura-${{ matrix.package }}-graph.json
          comment-on-pr: 'true'
          upload-artifact: true
          artifact-name: codex-aura-${{ matrix.package }}-graph
```

### Advanced Usage

```yaml
- uses: codex-aura/analyze-action@v1
  with:
    path: './src'
    edge-types: 'imports,calls'
    output: 'graph.json'
    comment-on-pr: 'true'
    fail-on-risk: 'high'
    upload-artifact: true
    artifact-name: 'my-project-graph'
    artifact-retention-days: 90
    track-metrics: true