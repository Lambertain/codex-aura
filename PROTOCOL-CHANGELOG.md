# Protocol Changelog

All notable changes to the Codex Aura Protocol will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-12-XX

### Added
- Initial protocol specification v1.0
- Node types: file, class, function
- Edge types: IMPORTS, CALLS, EXTENDS
- API endpoints: /api/v1/analyze, /api/v1/graphs, /api/v1/graph/{graph_id}, /api/v1/graph/{graph_id}/node/{node_id}, /api/v1/graph/{graph_id}/dependencies, /api/v1/context, /api/v1/graph/{graph_id}/impact, /api/v1/graph/{graph_id} (DELETE)
- JSON Schema validation for all data types
- Plugin system for extensibility
- Context analysis with relevance scoring
- Impact analysis for code changes
- Git blame information support
- Protocol extension mechanism with custom fields (x-*) and custom edge types (CUSTOM_*)

### Changed
- None (initial release)

### Deprecated
- None

### Removed
- None

### Fixed
- None

### Security
- Path traversal protection in API endpoints
- Request size limits
- Security headers middleware