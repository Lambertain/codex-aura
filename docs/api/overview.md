# API Overview

Codex Aura provides a REST API for programmatic access to analysis features.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, no authentication is required. This may change in future versions.

## Response Format

All responses are in JSON format with the following structure:

```json
{
  "success": true,
  "data": {...},
  "error": null
}
```

## Error Responses

Error responses follow this format:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description"
  }
}
```

## Rate Limiting

No rate limiting is currently implemented.

## Versioning

API version is included in the URL path: `/api/v1/`

## Endpoints Summary

- `GET /api/v1/graph` - Get full graph data
- `GET /api/v1/nodes` - List nodes with filtering
- `GET /api/v1/edges` - List edges with filtering
- `GET /api/v1/stats` - Get graph statistics
- `POST /api/v1/analyze` - Trigger new analysis
- `GET /api/v1/health` - Health check

See [Endpoints](endpoints.md) for detailed documentation.