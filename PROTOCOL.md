# Codex Aura Protocol Specification v1.0

## Overview

The Codex Aura Protocol defines a standard format for representing code dependency graphs and APIs for querying them. This protocol enables tools to analyze, store, and exchange code dependency information in a consistent manner.

The protocol supports:
- Static code analysis for multiple programming languages
- Dependency graph generation and storage
- Context-aware code retrieval
- Impact analysis for code changes
- Plugin-based extensibility

## Versioning

- Protocol version: MAJOR.MINOR
- Backward compatible changes: MINOR bump
- Breaking changes: MAJOR bump
- Current version: 1.0

## Data Types

### Node

Represents a node in the code dependency graph. A node can represent a file, class, or function in the analyzed codebase.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | yes | Unique identifier for the node |
| type | enum | yes | Node type: "file", "class", or "function" |
| name | string | yes | Name of the entity (filename, class name, or function name) |
| path | string | yes | Relative path to the file containing this node |
| lines | [int, int] | no | Start and end line numbers where the entity is defined |
| docstring | string | no | Documentation string extracted from the code |
| blame | BlameInfo | no | Git blame information for authorship tracking |

### Edge

Represents a directed relationship between two nodes in the code graph.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source | string | yes | ID of the source node |
| target | string | yes | ID of the target node |
| type | enum | yes | Relationship type: "IMPORTS", "CALLS", or "EXTENDS" |
| line | int | no | Line number where the relationship is defined |

### Graph

Complete representation of a code dependency graph containing all nodes, edges, and metadata.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| version | string | yes | Version of the graph format |
| generated_at | datetime | yes | Timestamp when the graph was generated (ISO 8601) |
| repository | Repository | yes | Information about the analyzed repository |
| stats | Stats | yes | Statistics about the graph contents |
| nodes | [Node] | yes | List of all nodes in the graph |
| edges | [Edge] | yes | List of all edges in the graph |
| sha | string | no | Current commit SHA of the analyzed repository |

### Repository

Information about the analyzed repository.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| path | string | yes | Absolute path to the repository root |
| name | string | yes | Name of the repository (basename of the path) |

### Stats

Statistics about the analyzed codebase.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| total_nodes | int | yes | Total number of nodes in the graph |
| total_edges | int | yes | Total number of edges in the graph |
| node_types | object | yes | Count of nodes by type (file, class, function) |
| average_complexity | float | no | Average complexity score across all nodes |
| hot_spots_count | int | no | Number of high-complexity or high-connectivity nodes |

### BlameInfo

Git blame information for a file.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| primary_author | string | yes | Primary author of the file |
| contributors | [string] | yes | List of all contributors to the file |
| author_distribution | object | yes | Distribution of authorship across the file (author -> line count) |

## API Endpoints

### POST /api/v1/analyze

Analyze a repository and generate a dependency graph.

**Request Body:**
```json
{
  "repo_path": "string",
  "edge_types": ["string"],
  "options": {}
}
```

**Response:**
```json
{
  "graph_id": "string",
  "status": "string",
  "stats": {},
  "duration_ms": 0
}
```

### GET /api/v1/graphs

Get list of stored graphs.

**Query Parameters:**
- repo_path (optional): Filter by repository path

**Response:**
```json
{
  "graphs": [
    {
      "id": "string",
      "repo_name": "string",
      "repo_path": "string",
      "sha": "string",
      "created_at": "datetime",
      "node_count": 0,
      "edge_count": 0
    }
  ]
}
```

### GET /api/v1/graph/{graph_id}

Retrieve a complete dependency graph.

**Query Parameters:**
- include_code (optional): Include source code in node data
- node_types (optional): Comma-separated list of node types to include
- edge_types (optional): Comma-separated list of edge types to include

**Response:**
```json
{
  "id": "string",
  "repo_name": "string",
  "created_at": "string",
  "nodes": [],
  "edges": [],
  "stats": {}
}
```

### GET /api/v1/graph/{graph_id}/node/{node_id}

Get information about a specific node.

**Query Parameters:**
- include_code (optional): Include source code in response

**Response:**
```json
{
  "node": {},
  "edges": {
    "incoming": [],
    "outgoing": []
  }
}
```

### GET /api/v1/graph/{graph_id}/dependencies

Get dependencies for a node with traversal options.

**Query Parameters:**
- node_id: Node ID to get dependencies for
- depth: Traversal depth (1-5)
- direction: "incoming", "outgoing", or "both"
- edge_types: Comma-separated list of edge types to include

**Response:**
```json
{
  "root": "string",
  "depth": 0,
  "nodes": [],
  "edges": []
}
```

### POST /api/v1/context

Get contextual nodes around entry points.

**Request Body:**
```json
{
  "graph_id": "string",
  "entry_points": ["string"],
  "depth": 2,
  "include_code": true,
  "max_nodes": 50
}
```

**Response:**
```json
{
  "context_nodes": [
    {
      "id": "string",
      "type": "string",
      "path": "string",
      "code": "string",
      "relevance": 0.0
    }
  ],
  "total_nodes": 0,
  "truncated": false
}
```

### GET /api/v1/graph/{graph_id}/impact

Analyze impact of changes to specified files.

**Query Parameters:**
- files: Comma-separated list of changed files

**Response:**
```json
{
  "changed_files": ["string"],
  "affected_files": [
    {
      "path": "string",
      "impact_type": "string",
      "edges": ["string"],
      "distance": 0
    }
  ],
  "affected_tests": ["string"]
}
```

### DELETE /api/v1/graph/{graph_id}

Delete a graph from storage.

**Response:**
```json
{
  "deleted": true,
  "graph_id": "string"
}
```

## Extension Points

### Plugin System

The protocol supports extensibility through plugins that can:

1. **Context Plugins**: Implement custom ranking and filtering logic for context retrieval
   - Interface: `ContextPlugin.rank_nodes(nodes, task, max_tokens)`
   - Interface: `ContextPlugin.analyze_impact(changed_files, graph, depth)`

2. **Analysis Plugins**: Extend static analysis capabilities
   - Interface: Custom analyzers for new languages or analysis types

3. **Storage Plugins**: Implement alternative storage backends
   - Interface: `StoragePlugin.save_graph(graph, graph_id)`
   - Interface: `StoragePlugin.load_graph(graph_id)`

### Custom Edge Types

New edge types can be defined by extending the EdgeType enum and implementing corresponding analysis logic in plugins.

### API Extensions

New API endpoints can be added following RESTful conventions and the existing response format patterns.