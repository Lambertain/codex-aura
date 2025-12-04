# Architecture

This document describes the high-level architecture of Codex Aura.

## Overview

Codex Aura is a Python code analysis tool that generates dependency graphs from source code. It consists of several key components:

- **Analyzer**: Core analysis engine
- **CLI**: Command-line interface
- **API Server**: REST API for programmatic access
- **Web Interface**: Interactive graph visualization

## Core Components

### Analyzer (`src/codex_aura/analyzer/`)

The analyzer is the heart of Codex Aura. It uses Python's AST (Abstract Syntax Tree) to parse source code and extract relationships.

**Key Classes:**
- `Analyzer`: Main analysis coordinator
- `ASTVisitor`: AST traversal and relationship extraction
- `GraphBuilder`: Constructs the dependency graph
- `Node`: Represents code entities (modules, classes, functions)
- `Edge`: Represents relationships between entities

**Analysis Pipeline:**
1. Source code parsing with `ast.parse()`
2. AST traversal with custom visitor
3. Relationship extraction (imports, calls, inheritance)
4. Graph construction and serialization

### CLI (`src/codex_aura/cli/`)

Command-line interface built with Click.

**Commands:**
- `analyze`: Perform code analysis
- `serve`: Start web server
- `version`: Show version

**Configuration:**
- Command-line arguments
- Configuration files (TOML/YAML)
- Environment variables

### API Server (`src/codex_aura/server/`)

FastAPI-based REST API server.

**Endpoints:**
- `/api/v1/graph`: Graph data
- `/api/v1/nodes`: Node listing and filtering
- `/api/v1/edges`: Edge listing and filtering
- `/api/v1/stats`: Statistics
- `/api/v1/analyze`: Trigger analysis

**Features:**
- OpenAPI/Swagger documentation
- JSON responses
- CORS support
- Request validation with Pydantic

### Web Interface (`src/codex_aura/web/`)

React-based single-page application for graph visualization.

**Components:**
- Graph visualization with D3.js or Cytoscape.js
- Interactive controls (zoom, pan, filter)
- Node details panel
- Search functionality

## Data Flow

```
Source Code → AST Parser → Analyzer → Graph Builder → JSON Output
                                      ↓
                                   Web Server ← REST API ← Web Interface
```

## Graph Model

### Nodes

```json
{
  "id": "module.submodule.Class",
  "type": "class",
  "name": "Class",
  "module": "module.submodule",
  "line_start": 10,
  "line_end": 50,
  "properties": {
    "bases": ["BaseClass"],
    "methods": ["method1", "method2"]
  }
}
```

### Edges

```json
{
  "source": "module.a",
  "target": "module.b",
  "type": "imports",
  "properties": {
    "line": 5,
    "alias": "b"
  }
}
```

## Extension Points

### Custom Analyzers

Implement `BaseAnalyzer` for custom analysis logic:

```python
class CustomAnalyzer(BaseAnalyzer):
    def analyze(self, source: str) -> Graph:
        # Custom analysis logic
        pass
```

### Plugins

Plugin system for extending functionality:

- Custom node/edge extractors
- Output formatters
- Web interface extensions

## Dependencies

### Core Dependencies

- `ast`: Python AST parsing (stdlib)
- `pydantic`: Data validation
- `click`: CLI framework
- `fastapi`: API server
- `uvicorn`: ASGI server

### Optional Dependencies

- `mkdocs`: Documentation generation
- `pytest`: Testing
- `black`: Code formatting
- `ruff`: Linting

## Performance Considerations

- **Memory Usage**: AST parsing is memory-efficient
- **Analysis Speed**: Linear with codebase size
- **Caching**: Graph caching for large codebases
- **Parallelization**: Potential for multi-file analysis

## Security

- No remote code execution
- Input validation on all APIs
- Safe AST parsing (no `eval`)
- Path traversal protection

## Future Architecture

- **Microservices**: Split analyzer, API, and web components
- **Database Storage**: Persistent graph storage
- **Real-time Analysis**: Incremental updates
- **Multi-language Support**: Extend beyond Python