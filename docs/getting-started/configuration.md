# Configuration

Codex Aura can be configured through command-line options or configuration files.

## Command Line Options

### Analysis Options

- `--path, -p`: Path to analyze (default: current directory)
- `--output, -o`: Output file path (default: codex-aura-graph.json)
- `--edge-types`: Comma-separated edge types (default: imports,calls,extends)
- `--exclude-patterns`: Patterns to exclude from analysis
- `--include-patterns`: Patterns to include in analysis

### Server Options

- `--host`: Server host (default: 127.0.0.1)
- `--port`: Server port (default: 8000)
- `--debug`: Enable debug mode

## Configuration File

Create a `codex-aura.toml` or `codex-aura.yaml` file in your project root:

```toml
[analysis]
path = "."
output = "graph.json"
edge_types = ["imports", "calls", "extends"]
exclude_patterns = ["test_*", "*/migrations/*"]
include_patterns = ["*.py"]

[server]
host = "127.0.0.1"
port = 8000
debug = false
```

## Edge Types

- `imports`: Module import relationships
- `calls`: Function/method calls
- `extends`: Class inheritance
- `contains`: Containment relationships

## Examples

Analyze specific directory with custom output:

```bash
codex-aura analyze src/ --output my-graph.json
```

Exclude test files:

```bash
codex-aura analyze . --exclude-patterns "test_*"
```

Start server with custom port:

```bash
codex-aura serve graph.json --port 3000