# Codex Aura Architecture

## Overview

Codex Aura is a code context mapping tool designed to help AI agents understand codebases. It analyzes source code to build dependency graphs and provides APIs for querying code relationships.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Codex Aura                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   CLI    │    │   API    │    │ VS Code  │    │  GitHub  │  │
│  │          │    │  Server  │    │Extension │    │  Action  │  │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘  │
│       │               │               │               │         │
│       └───────────────┴───────┬───────┴───────────────┘         │
│                               │                                  │
│                    ┌──────────▼──────────┐                      │
│                    │      Core Engine     │                      │
│                    │  ┌────────────────┐  │                      │
│                    │  │   Analyzer     │  │                      │
│                    │  │  (Python AST)  │  │                      │
│                    │  └────────────────┘  │                      │
│                    │  ┌────────────────┐  │                      │
│                    │  │    Storage     │  │                      │
│                    │  │   (SQLite)     │  │                      │
│                    │  └────────────────┘  │                      │
│                    │  ┌────────────────┐  │                      │
│                    │  │    Models      │  │                      │
│                    │  │ (Graph/Node/   │  │                      │
│                    │  │     Edge)      │  │                      │
│                    │  └────────────────┘  │                      │
│                    └─────────────────────┘                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Analyzer (`src/codex_aura/analyzer/`)

The analyzer extracts code structure from source files using AST parsing.

```
analyzer/
├── base.py           # BaseAnalyzer abstract class
├── python.py         # PythonAnalyzer implementation
└── utils.py          # Shared utilities
```

#### PythonAnalyzer Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scan Files │────▶│  Parse AST  │────▶│ Extract     │
│  (.py)      │     │             │     │ Nodes/Edges │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Build      │◀────│  Resolve    │◀────│ Calculate   │
│  Graph      │     │  References │     │ Metrics     │
└─────────────┘     └─────────────┘     └─────────────┘
```

#### Node Types

| Type | Description | Example ID |
|------|-------------|------------|
| `file` | Python source file | `src/utils.py::file` |
| `class` | Class definition | `src/utils.py::class::Helper` |
| `function` | Function/method | `src/utils.py::function::process` |

#### Edge Types

| Type | Description | Example |
|------|-------------|---------|
| `IMPORTS` | Import statement | `main.py` → `utils.py` |
| `CALLS` | Function call | `main()` → `helper()` |
| `EXTENDS` | Class inheritance | `Dog` → `Animal` |

---

### 2. Storage (`src/codex_aura/storage/`)

Storage layer handles graph persistence.

```
storage/
├── base.py           # GraphRepository protocol
├── sqlite.py         # SQLite implementation
├── json_file.py      # JSON file storage (legacy)
└── memory.py         # In-memory storage (testing)
```

#### SQLite Schema

```sql
┌─────────────────┐       ┌─────────────────┐
│     graphs      │       │      nodes      │
├─────────────────┤       ├─────────────────┤
│ id (PK)         │───┐   │ id (PK)         │
│ repo_path       │   │   │ graph_id (FK)   │◀─┐
│ repo_name       │   │   │ type            │  │
│ sha             │   │   │ name            │  │
│ created_at      │   │   │ path            │  │
│ node_count      │   │   │ line_start      │  │
│ edge_count      │   │   │ line_end        │  │
└─────────────────┘   │   │ docstring       │  │
                      │   └─────────────────┘  │
                      │                        │
                      │   ┌─────────────────┐  │
                      │   │      edges      │  │
                      │   ├─────────────────┤  │
                      └──▶│ graph_id (FK)   │  │
                          │ source_id (FK)  │──┤
                          │ target_id (FK)  │──┘
                          │ type            │
                          │ line            │
                          └─────────────────┘
```

---

### 3. API Server (`src/codex_aura/api/`)

FastAPI-based HTTP server providing REST endpoints.

```
api/
├── server.py         # Main FastAPI app
├── routes/           # Endpoint handlers
├── middleware/       # Request processing
└── schemas/          # Request/Response models
```

#### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Analyze repository |
| GET | `/api/v1/graphs` | List all graphs |
| GET | `/api/v1/graph/{id}` | Get graph details |
| DELETE | `/api/v1/graph/{id}` | Delete graph |
| GET | `/api/v1/graph/{id}/dependencies` | Query dependencies |
| POST | `/api/v1/context` | Get context for files |
| POST | `/api/v1/graph/{id}/impact` | Analyze change impact |

#### Request Flow

```
Client Request
      │
      ▼
┌─────────────────┐
│  Rate Limiter   │
│   (SlowAPI)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Security Headers│
│   Middleware    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Request Logger │
│   Middleware    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Route Handler  │
│                 │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Storage      │
│   (SQLite)      │
└────────┬────────┘
         │
         ▼
    JSON Response
```

---

### 4. CLI (`src/codex_aura/cli/`)

Command-line interface for local usage.

```bash
codex-aura analyze <path>     # Analyze repository
codex-aura serve              # Start API server
codex-aura list               # List saved graphs
codex-aura stats <graph_id>   # Show graph statistics
```

---

### 5. Models (`src/codex_aura/models/`)

Pydantic data models for type safety and serialization.

```python
# Node - represents a code entity
class Node(BaseModel):
    id: str              # Unique identifier
    type: Literal["file", "class", "function"]
    name: str            # Entity name
    path: str            # File path
    lines: Optional[List[int]]  # [start, end]
    docstring: Optional[str]
    blame: Optional[BlameInfo]

# Edge - represents a relationship
class Edge(BaseModel):
    source: str          # Source node ID
    target: str          # Target node ID
    type: EdgeType       # IMPORTS, CALLS, EXTENDS
    line: Optional[int]  # Line number

# Graph - complete dependency graph
class Graph(BaseModel):
    version: str
    generated_at: datetime
    repository: Repository
    stats: Stats
    nodes: List[Node]
    edges: List[Edge]
    sha: str
```

---

### 6. Plugins (`src/codex_aura/plugins/`)

Extensible plugin architecture for custom functionality.

```
plugins/
├── base.py           # Plugin protocols
├── manager.py        # Plugin discovery/loading
└── builtin/          # Built-in plugins
    ├── context_basic.py
    └── impact_basic.py
```

#### Plugin Types

| Type | Purpose | Interface |
|------|---------|-----------|
| ContextPlugin | Custom context formatting | `format_context()` |
| ImpactPlugin | Custom impact analysis | `analyze_impact()` |

#### Entry Points (pyproject.toml)

```toml
[project.entry-points."codex_aura.plugins.context"]
basic = "codex_aura.plugins.builtin.context_basic:BasicContextPlugin"

[project.entry-points."codex_aura.plugins.impact"]
basic = "codex_aura.plugins.builtin.impact_basic:BasicImpactPlugin"
```

---

## Data Flow

### 1. Analysis Flow

```
Repository Path
      │
      ▼
┌─────────────────┐
│ find_python_    │
│ files()         │────▶ List[Path]
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ analyze_file()  │────▶ List[Node], List[Edge]
│ for each file   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ resolve_        │────▶ Resolved edges
│ references()    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ calculate_      │────▶ Stats, hot_spots
│ metrics()       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ build_graph()   │────▶ Graph object
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ storage.save()  │────▶ SQLite / JSON
└─────────────────┘
```

### 2. Context Query Flow

```
Context Request
{files: [...], max_tokens: N}
      │
      ▼
┌─────────────────┐
│ load_graph()    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ find_nodes()    │────▶ Matching nodes
│ for each file   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ expand_         │────▶ Related nodes
│ dependencies()  │      (depth-limited)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ format_         │────▶ Context string
│ context()       │      (token-limited)
└─────────────────┘
```

### 3. Impact Analysis Flow

```
Changed Files List
      │
      ▼
┌─────────────────┐
│ find_incoming_  │────▶ Files that import
│ edges()         │      changed files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ calculate_      │────▶ Impact scores
│ impact_score()  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ classify_risk() │────▶ Risk level
│                 │      (critical/high/
└─────────────────┘       medium/low)
```

---

## Extension Points

### Adding a New Analyzer (Language Support)

1. Create `analyzer/javascript.py`
2. Implement `BaseAnalyzer` interface
3. Register in analyzer factory

```python
class JavaScriptAnalyzer(BaseAnalyzer):
    def analyze(self, repo_path: Path) -> Graph:
        # Parse JS/TS files
        ...
    
    def analyze_file(self, file_path: Path) -> List[Node]:
        # Extract nodes from single file
        ...
```

### Adding a New Storage Backend

1. Create `storage/postgres.py`
2. Implement `GraphRepository` protocol
3. Configure via environment variable

```python
class PostgresGraphRepository(GraphRepository):
    def save(self, graph: Graph) -> str: ...
    def load(self, graph_id: str) -> Graph: ...
    def find_by_repo(self, repo_path: str) -> List[GraphMeta]: ...
```

### Adding Custom Plugins

1. Create plugin module
2. Implement plugin protocol
3. Register via entry points

```python
# my_plugin/context.py
class MyContextPlugin:
    def format_context(self, nodes: List[Node]) -> str:
        # Custom formatting logic
        ...

# pyproject.toml
[project.entry-points."codex_aura.plugins.context"]
my_plugin = "my_plugin.context:MyContextPlugin"
```

---

## Deployment Architecture

### Local Development

```
┌─────────────────────────────────────┐
│         Developer Machine           │
├─────────────────────────────────────┤
│  codex-aura CLI                     │
│       │                             │
│       ▼                             │
│  ~/.codex-aura/graphs.db (SQLite)   │
└─────────────────────────────────────┘
```

### Docker Deployment

```
┌─────────────────────────────────────┐
│         Docker Container            │
├─────────────────────────────────────┤
│  codex-aura serve                   │
│       │                             │
│       ▼                             │
│  /data/graphs.db (volume mount)     │
│                                     │
│  Exposed: port 8000                 │
└─────────────────────────────────────┘
```

### CI/CD Integration (GitHub Action)

```
┌─────────────────────────────────────────────┐
│              GitHub Actions                  │
├─────────────────────────────────────────────┤
│  ┌─────────────────┐                        │
│  │ Checkout Code   │                        │
│  └────────┬────────┘                        │
│           │                                  │
│           ▼                                  │
│  ┌─────────────────┐                        │
│  │ Run codex-aura  │                        │
│  │ analyze         │                        │
│  └────────┬────────┘                        │
│           │                                  │
│           ▼                                  │
│  ┌─────────────────┐    ┌─────────────────┐ │
│  │ Impact Analysis │───▶│ PR Comment      │ │
│  └─────────────────┘    └─────────────────┘ │
│           │                                  │
│           ▼                                  │
│  ┌─────────────────┐                        │
│  │ Upload Artifact │                        │
│  └─────────────────┘                        │
└─────────────────────────────────────────────┘
```

---

## Performance Considerations

### Optimization Strategies

1. **Incremental Analysis**: Only re-analyze changed files
2. **AST Caching**: Cache parsed AST for unchanged files
3. **Parallel Processing**: Use multiprocessing for large repos
4. **Lazy Loading**: Load graph data on-demand
5. **Index Optimization**: SQLite indexes on frequently queried columns

### Performance Targets

| Metric | Target |
|--------|--------|
| 10K LOC analysis | < 2 seconds |
| 50K LOC analysis | < 10 seconds |
| 100K LOC analysis | < 30 seconds |
| API cold query | < 500ms |
| API cached query | < 100ms |

---

## Security Considerations

1. **Path Validation**: Prevent directory traversal attacks
2. **Rate Limiting**: Protect API from abuse
3. **Input Sanitization**: Validate all user inputs
4. **Security Headers**: CORS, CSP, X-Frame-Options
5. **File Size Limits**: Prevent DoS via large files

---

## Future Architecture (Phase 2+)

```
┌──────────────────────────────────────────────────────────────┐
│                     Codex Aura Cloud                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ API Gateway│  │ Auth/RBAC  │  │ Dashboard  │             │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘             │
│        │               │               │                      │
│        └───────────────┼───────────────┘                      │
│                        │                                      │
│              ┌─────────▼─────────┐                           │
│              │   Load Balancer   │                           │
│              └─────────┬─────────┘                           │
│                        │                                      │
│        ┌───────────────┼───────────────┐                     │
│        │               │               │                      │
│  ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐               │
│  │ Worker 1  │  │ Worker 2  │  │ Worker N  │               │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│        │               │               │                      │
│        └───────────────┼───────────────┘                      │
│                        │                                      │
│              ┌─────────▼─────────┐                           │
│              │   PostgreSQL      │                           │
│              │   + pgvector      │                           │
│              └───────────────────┘                           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```
