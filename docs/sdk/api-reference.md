# Codex Aura SDK API Reference

## CodexAura Class

Main SDK client for code analysis and context generation.

### Constructor

```python
CodexAura(
    server_url: Optional[str] = None,
    repo_path: Optional[Union[str, Path]] = None,
    timeout: float = 30.0,
    max_retries: int = 3,
    db_path: str = "codex_aura.db"
)
```

**Parameters:**
- `server_url`: URL of remote Codex Aura server (remote mode)
- `repo_path`: Path to local repository (local mode)
- `timeout`: Request timeout in seconds
- `max_retries`: Maximum number of retries for failed requests
- `db_path`: Path to local database file

**Raises:** `ValidationError` if neither server_url nor repo_path is provided

### Methods

#### analyze()

Analyze repository and generate dependency graph.

```python
def analyze(self, repo_path: Optional[Union[str, Path]] = None) -> str
```

**Parameters:**
- `repo_path`: Repository path (only for remote mode, overrides instance repo_path)

**Returns:** Graph ID for the generated graph

**Raises:** `ValidationError`, `AnalysisError`

#### get_context()

Get contextual information around entry points.

```python
def get_context(
    self,
    task: str,
    entry_points: List[str],
    graph_id: Optional[str] = None,
    depth: int = 2,
    max_tokens: int = 8000,
    include_code: bool = True
) -> Context
```

**Parameters:**
- `task`: Description of the task
- `entry_points`: List of entry point identifiers
- `graph_id`: Graph ID to use (auto-detects latest if not provided)
- `depth`: Traversal depth from entry points
- `max_tokens`: Maximum tokens for context
- `include_code`: Whether to include source code in context

**Returns:** Context object with relevant nodes and relationships

**Raises:** `ValidationError`, `AnalysisError`

#### analyze_impact()

Analyze impact of changes to specified files.

```python
def analyze_impact(
    self,
    changed_files: List[str],
    graph_id: Optional[str] = None
) -> ImpactAnalysis
```

**Parameters:**
- `changed_files`: List of changed file paths
- `graph_id`: Graph ID to use (auto-detects latest if not provided)

**Returns:** ImpactAnalysis object with affected files and tests

**Raises:** `ValidationError`, `AnalysisError`

#### list_graphs()

List available graphs.

```python
def list_graphs(self) -> List[Dict[str, Any]]
```

**Returns:** List of graph information dictionaries

#### delete_graph()

Delete a graph.

```python
def delete_graph(self, graph_id: str) -> bool
```

**Parameters:**
- `graph_id`: Graph ID to delete

**Returns:** True if deleted successfully

## Context Class

Context result wrapper with formatting capabilities.

### Methods

#### to_prompt()

Convert context to formatted prompt string.

```python
def to_prompt(
    self,
    format: Literal["plain", "markdown", "xml"] = "markdown",
    include_tree: bool = False,
    include_edges: bool = False,
    max_chars: Optional[int] = None
) -> str
```

**Parameters:**
- `format`: Output format ("plain", "markdown", "xml")
- `include_tree`: Whether to include file tree structure
- `include_edges`: Whether to include edge relationships
- `max_chars`: Maximum character limit for output

**Returns:** Formatted prompt string

### Properties

- `context_nodes`: List of ContextNode objects
- `total_nodes`: Total number of nodes available
- `truncated`: Whether context was truncated
- `edges`: Optional list of Edge objects

## ContextNode Class

Represents a context node with metadata.

### Properties

- `id`: Node identifier
- `type`: Node type (function, class, etc.)
- `path`: File path
- `code`: Optional source code
- `relevance`: Relevance score (0.0 to 1.0)

## ImpactAnalysis Class

Impact analysis result wrapper.

### Properties

- `changed_files`: List of changed file paths
- `affected_files`: List of affected files with impact details
- `affected_tests`: List of affected test files

## Exceptions

### CodexAuraError

Base exception for SDK errors.

### ConnectionError

Raised when connection to server fails.

### AnalysisError

Raised when analysis operations fail.

### ValidationError

Raised when input validation fails.

### TimeoutError

Raised when requests timeout.

## Examples

### Basic Usage

```python
from codex_aura import CodexAura

# Local mode
ca = CodexAura(repo_path="./my_project")

# Analyze repository
graph_id = ca.analyze()

# Get context for bug fix
context = ca.get_context(
    task="Fix null pointer in user authentication",
    entry_points=["src/auth/user.py"]
)

# Use in prompt
prompt = f"""
Fix this bug in the authentication system:

{context.to_prompt()}

Please provide the fix:
"""

# Send to LLM...
```

### Impact Analysis

```python
# Analyze impact of changes
impact = ca.analyze_impact([
    "src/auth/login.py",
    "src/auth/session.py"
])

print(f"Affected files: {len(impact.affected_files)}")
print(f"Affected tests: {len(impact.affected_tests)}")

for file in impact.affected_files:
    print(f"- {file['path']} ({file['impact_type']})")
```

### Remote Server Usage

```python
# Remote mode
ca = CodexAura(server_url="https://api.codex-aura.com")

# Same API, but operations happen on server
graph_id = ca.analyze(repo_path="https://github.com/user/repo")
context = ca.get_context(
    task="Add API endpoint",
    entry_points=["src/api/routes.py"]
)