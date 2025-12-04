# API Endpoints

## GET /api/v1/graph

Get the complete dependency graph.

**Response:**
```json
{
  "success": true,
  "data": {
    "nodes": [...],
    "edges": [...],
    "metadata": {...}
  }
}
```

## GET /api/v1/nodes

Get nodes with optional filtering.

**Query Parameters:**
- `type`: Filter by node type (module, class, function)
- `name`: Filter by name pattern
- `limit`: Maximum number of results
- `offset`: Pagination offset

**Response:**
```json
{
  "success": true,
  "data": {
    "nodes": [...],
    "total": 150,
    "limit": 50,
    "offset": 0
  }
}
```

## GET /api/v1/edges

Get edges with optional filtering.

**Query Parameters:**
- `type`: Filter by edge type (imports, calls, extends)
- `source`: Filter by source node
- `target`: Filter by target node

**Response:**
```json
{
  "success": true,
  "data": {
    "edges": [...],
    "total": 300
  }
}
```

## GET /api/v1/stats

Get graph statistics.

**Response:**
```json
{
  "success": true,
  "data": {
    "node_count": 150,
    "edge_count": 300,
    "node_types": {
      "module": 45,
      "class": 60,
      "function": 45
    },
    "edge_types": {
      "imports": 200,
      "calls": 80,
      "extends": 20
    }
  }
}
```

## POST /api/v1/analyze

Trigger a new analysis.

**Request Body:**
```json
{
  "path": "./src",
  "edge_types": ["imports", "calls"],
  "exclude_patterns": ["test_*"]
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "task_id": "abc-123",
    "status": "running"
  }
}
```

## GET /api/v1/health

Health check endpoint.

**Response:**
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "version": "1.0.0"
  }
}