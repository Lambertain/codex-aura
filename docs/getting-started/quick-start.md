# Quick Start

Get up and running with Codex Aura in minutes.

## Basic Analysis

1. Install Codex Aura (see [Installation](installation.md))

2. Navigate to your Python project:

```bash
cd your-python-project
```

3. Run analysis:

```bash
codex-aura analyze .
```

This will generate a `codex-aura-graph.json` file with your dependency graph.

## View Results

### Web Interface

Start the web server to explore your graph interactively:

```bash
codex-aura serve codex-aura-graph.json
```

Open http://localhost:8000 in your browser.

### JSON Output

The generated JSON file contains:

```json
{
  "nodes": [
    {
      "id": "module.name",
      "type": "module",
      "properties": {...}
    }
  ],
  "edges": [
    {
      "source": "module.a",
      "target": "module.b",
      "type": "imports"
    }
  ]
}
```

## Next Steps

- [Configure analysis options](configuration.md)
- [Learn about CLI commands](../cli/commands.md)
- [Explore the API](../api/overview.md)