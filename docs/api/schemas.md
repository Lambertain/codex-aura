# API Schemas

## Node Schema

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "description": "Unique identifier for the node"
    },
    "type": {
      "type": "string",
      "enum": ["module", "class", "function", "method"],
      "description": "Type of the code entity"
    },
    "name": {
      "type": "string",
      "description": "Name of the entity"
    },
    "module": {
      "type": "string",
      "description": "Module path"
    },
    "line_start": {
      "type": "integer",
      "description": "Starting line number"
    },
    "line_end": {
      "type": "integer",
      "description": "Ending line number"
    },
    "properties": {
      "type": "object",
      "description": "Additional properties"
    }
  },
  "required": ["id", "type", "name"]
}
```

## Edge Schema

```json
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "description": "Source node ID"
    },
    "target": {
      "type": "string",
      "description": "Target node ID"
    },
    "type": {
      "type": "string",
      "enum": ["imports", "calls", "extends", "contains"],
      "description": "Type of relationship"
    },
    "properties": {
      "type": "object",
      "description": "Additional edge properties"
    }
  },
  "required": ["source", "target", "type"]
}
```

## Graph Schema

```json
{
  "type": "object",
  "properties": {
    "nodes": {
      "type": "array",
      "items": {"$ref": "#/definitions/Node"}
    },
    "edges": {
      "type": "array",
      "items": {"$ref": "#/definitions/Edge"}
    },
    "metadata": {
      "type": "object",
      "properties": {
        "version": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "analyzer_version": {"type": "string"},
        "analysis_time": {"type": "number"}
      }
    }
  },
  "required": ["nodes", "edges", "metadata"]
}
```

## Analysis Request Schema

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "description": "Path to analyze"
    },
    "edge_types": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Types of edges to extract"
    },
    "exclude_patterns": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Patterns to exclude"
    },
    "include_patterns": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Patterns to include"
    }
  }
}
```

## Statistics Schema

```json
{
  "type": "object",
  "properties": {
    "node_count": {"type": "integer"},
    "edge_count": {"type": "integer"},
    "node_types": {
      "type": "object",
      "patternProperties": {
        ".*": {"type": "integer"}
      }
    },
    "edge_types": {
      "type": "object",
      "patternProperties": {
        ".*": {"type": "integer"}
      }
    }
  }
}