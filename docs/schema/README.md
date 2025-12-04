# JSON Schema Documentation

This directory contains JSON schemas and documentation for Codex Aura data formats.

## Graph Format v0.1

The graph format represents code dependency relationships as a directed graph.

### Components

- **Nodes**: Represent code entities (files, classes, functions)
- **Edges**: Represent relationships between nodes (imports, calls, inheritance)
- **Graph**: Container for nodes, edges, and metadata

### Schema Files

- [`graph-v0.1.json`](graph-v0.1.json) - Complete graph schema
- [`node-examples.json`](node-examples.json) - Node type examples
- [`edge-examples.json`](edge-examples.json) - Edge type examples
- [`graph-examples.json`](graph-examples.json) - Complete graph examples

### Node Schema

Nodes represent individual code entities in the dependency graph.

#### Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | string | ✓ | Unique identifier for the node |
| `type` | string | ✓ | Node type (file, class, function, etc.) |
| `name` | string | ✓ | Human-readable name |
| `path` | string | ✓ | File system path |
| `lines` | array | ✗ | Line numbers where entity is defined |
| `docstring` | string | ✗ | Documentation string |

#### Node Types

- `file`: Python source files
- `class`: Class definitions
- `function`: Function/method definitions
- `variable`: Module-level variables

#### Example

```json
{
  "id": "file_main_py",
  "type": "file",
  "name": "main.py",
  "path": "src/main.py",
  "lines": [1, 50],
  "docstring": "Main application entry point"
}
```

### Edge Schema

Edges represent relationships between nodes.

#### Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `source` | string | ✓ | Source node ID |
| `target` | string | ✓ | Target node ID |
| `type` | string | ✓ | Relationship type |
| `line` | integer | ✗ | Line number where relationship occurs |

#### Edge Types

- `IMPORTS`: Import relationships
- `CALLS`: Function/method calls
- `EXTENDS`: Class inheritance
- `IMPLEMENTS`: Interface implementation

#### Example

```json
{
  "source": "file_main_py",
  "target": "file_utils_py",
  "type": "IMPORTS",
  "line": 3
}
```

### Graph Schema

The root container for the entire dependency graph.

#### Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `version` | string | ✓ | Schema version |
| `generated_at` | string | ✓ | ISO 8601 timestamp |
| `repository` | object | ✓ | Repository information |
| `stats` | object | ✓ | Graph statistics |
| `nodes` | array | ✓ | Array of node objects |
| `edges` | array | ✓ | Array of edge objects |

#### Repository Object

```json
{
  "path": "/absolute/path/to/repo",
  "name": "my-python-project"
}
```

#### Stats Object

```json
{
  "total_nodes": 150,
  "total_edges": 234,
  "node_types": {
    "file": 12,
    "class": 45,
    "function": 93
  }
}
```

### Complete Example

```json
{
  "version": "0.1",
  "generated_at": "2025-12-04T14:00:00Z",
  "repository": {
    "path": "/home/user/my-project",
    "name": "my-project"
  },
  "stats": {
    "total_nodes": 5,
    "total_edges": 3,
    "node_types": {
      "file": 3,
      "function": 2
    }
  },
  "nodes": [
    {
      "id": "file_main_py",
      "type": "file",
      "name": "main.py",
      "path": "main.py"
    },
    {
      "id": "file_utils_py",
      "type": "file",
      "name": "utils.py",
      "path": "utils.py"
    },
    {
      "id": "func_format_name",
      "type": "function",
      "name": "format_name",
      "path": "utils.py",
      "lines": [5, 8]
    }
  ],
  "edges": [
    {
      "source": "file_main_py",
      "target": "file_utils_py",
      "type": "IMPORTS",
      "line": 1
    },
    {
      "source": "file_main_py",
      "target": "func_format_name",
      "type": "CALLS",
      "line": 10
    }
  ]
}
```

## Versioning

Schema versions follow semantic versioning:
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes

Current version: **v0.1** (initial release)

## Validation

Use the JSON schema files to validate your graph data:

```bash
# Using Python with jsonschema
pip install jsonschema
python -c "
import json
import jsonschema
with open('graph-v0.1.json') as f:
    schema = json.load(f)
with open('my-graph.json') as f:
    data = json.load(f)
jsonschema.validate(data, schema)
print('Valid!')
"
```

## Migration

When upgrading between versions, check the changelog for breaking changes and migration guides.