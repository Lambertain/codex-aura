# Codex Aura Analyze GitHub Action

This GitHub Action analyzes your codebase and generates a dependency graph using Codex Aura.

## Inputs

- `path`: Path to analyze (default: '.')
- `edge-types`: Edge types to extract (default: 'imports,calls,extends')
- `output`: Output file path (default: 'codex-aura-graph.json')
- `comment-on-pr`: Add comment to PR with results (default: 'false')

## Outputs

- `graph-file`: Path to generated graph file
- `node-count`: Number of nodes in graph
- `edge-count`: Number of edges in graph

## Usage

```yaml
- uses: your-org/codex-aura-action@v1
  with:
    path: './src'
    edge-types: 'imports,calls'
    output: 'graph.json'
    comment-on-pr: 'true'