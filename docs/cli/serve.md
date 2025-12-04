# Serve Command

The `serve` command starts a web server to explore generated dependency graphs interactively.

## Usage

```bash
codex-aura serve [OPTIONS] GRAPH_FILE
```

## Arguments

- `GRAPH_FILE`: Path to the graph JSON file

## Options

- `--host TEXT`: Server host (default: 127.0.0.1)
- `--port INTEGER`: Server port (default: 8000)
- `--debug`: Enable debug mode
- `--open-browser`: Automatically open browser

## Examples

Start server with default settings:

```bash
codex-aura serve codex-aura-graph.json
```

Start on specific port:

```bash
codex-aura serve graph.json --port 3000
```

Start with debug mode:

```bash
codex-aura serve graph.json --debug
```

## Web Interface Features

The web interface provides:

- **Interactive Graph Visualization**: Zoom, pan, and explore the dependency graph
- **Node Details**: Click nodes to see detailed information
- **Search**: Find specific nodes by name
- **Filters**: Filter nodes by type or properties
- **Export**: Export graph in various formats

## API Endpoints

The server also provides REST API endpoints:

- `GET /api/graph`: Get the full graph data
- `GET /api/nodes`: List all nodes
- `GET /api/edges`: List all edges
- `GET /api/stats`: Get graph statistics