# Getting Started with Codex Aura

Welcome to Codex Aura! This guide will help you get started with analyzing Python code dependencies in under 15 minutes.

## Prerequisites

- Python 3.11+
- Git (optional, for cloning repositories)

## Installation

Install Codex Aura using pip:

```bash
pip install codex-aura
```

Or install from source for development:

```bash
git clone https://github.com/Lambertain/codex-aura.git
cd codex-aura
pip install -e .
```

## First Analysis (CLI)

Let's analyze a Python repository to understand its structure.

### Step 1: Prepare a sample project

Create a simple Python project to analyze:

```bash
mkdir my-python-project
cd my-python-project
```

Create the following files:

**config.py:**
```python
DATABASE_URL = "sqlite:///app.db"
DEBUG = True
```

**utils.py:**
```python
def format_name(name: str) -> str:
    """Format a name to title case."""
    return name.title()

def calculate_total(items: list) -> float:
    """Calculate total from list of items."""
    return sum(items)
```

**main.py:**
```python
from config import DATABASE_URL, DEBUG
from utils import format_name, calculate_total

def main():
    print("Welcome to my app!")
    name = format_name("john doe")
    total = calculate_total([10, 20, 30])
    print(f"Hello {name}, total: {total}")

if __name__ == "__main__":
    main()
```

### Step 2: Analyze the project

Run the analysis command:

```bash
codex-aura analyze . -o graph.json
```

This will:
- Scan all Python files in the current directory
- Parse import relationships
- Generate a dependency graph
- Save results to `graph.json`

### Step 3: View statistics

Check the analysis results:

```bash
codex-aura stats graph.json
```

Expected output:
```
Graph: my-python-project (v0.1)
Generated: 2025-12-04 14:03:49
Created: 2025-12-04 14:03:49

Nodes by type:
  file:       3 (100%)

Most connected files:
  1. main.py        (2 incoming, 0 outgoing)
  2. utils.py       (1 incoming, 0 outgoing)
  3. config.py      (1 incoming, 0 outgoing)
```

## Starting the API Server

Codex Aura provides a REST API for programmatic access.

### Start the server

```bash
codex-aura server
```

The server will start on `http://localhost:8000`.

### Access the API documentation

Open your browser and go to: `http://localhost:8000/docs`

This provides an interactive Swagger UI where you can:
- Test all API endpoints
- View request/response schemas
- Execute API calls directly

## Using the API

### Analyze a repository via API

```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_path": "./my-python-project",
    "edge_types": ["imports"]
  }'
```

Response:
```json
{
  "graph_id": "g_abc123def456",
  "status": "completed",
  "stats": {
    "files": 3,
    "classes": 0,
    "functions": 2,
    "edges": {
      "IMPORTS": 3
    }
  },
  "duration_ms": 150
}
```

### Get graph data

```bash
curl "http://localhost:8000/api/v1/graph/g_abc123def456"
```

### Analyze impact of changes

```bash
curl "http://localhost:8000/api/v1/graph/g_abc123def456/impact?files=config.py"
```

## VS Code Extension

The Codex Aura VS Code extension provides IDE integration.

### Installation

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Codex Aura"
4. Click Install

### Usage

1. Open a Python project in VS Code
2. Open Command Palette (Ctrl+Shift+P)
3. Run "Codex Aura: Analyze Project"
4. View the dependency graph in the sidebar

The extension provides:
- Visual dependency graphs
- Impact analysis for file changes
- Code navigation based on dependencies

## GitHub Action

Automate code analysis in your CI/CD pipeline.

### Basic usage

Create `.github/workflows/codex-aura.yml`:

```yaml
name: Code Analysis
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Lambertain/codex-aura-action@v1
        with:
          path: .
          output: graph.json
      - uses: actions/upload-artifact@v4
        with:
          name: dependency-graph
          path: graph.json
```

### Advanced configuration

```yaml
name: Code Analysis
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Lambertain/codex-aura-action@v1
        with:
          path: src/
          output: graph.json
          format: json
      - name: Comment PR with stats
        run: |
          STATS=$(codex-aura stats graph.json --format json)
          echo "Analysis complete: $STATS" >> $GITHUB_STEP_SUMMARY
```

## Next Steps

- Explore the [API documentation](http://localhost:8000/docs) for advanced features
- Check out [examples](../examples/) for real-world usage
- Read the [architecture docs](../adr/) to understand design decisions
- View [schema documentation](../schema/) for data formats

## Troubleshooting

### Common issues

**"No Python files found"**
- Ensure you're in a directory containing `.py` files
- Check that files aren't excluded by `.gitignore`

**"Analysis failed"**
- Verify Python syntax is valid
- Check file permissions
- Try with `--verbose` flag for more details

**"Server won't start"**
- Ensure port 8000 is available
- Check for missing dependencies: `pip install fastapi uvicorn`

For more help, visit our [GitHub repository](https://github.com/Lambertain/codex-aura).