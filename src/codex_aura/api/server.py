"""FastAPI server for codex-aura."""

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

from ..analyzer.python import PythonAnalyzer
from ..models.graph import Graph, save_graph
from ..storage.sqlite import SQLiteStorage
from collections import deque

app = FastAPI(
    title="Codex Aura API",
    description="REST API for code analysis and dependency graph generation",
    version="0.1.0",
    contact={
        "name": "Codex Aura Team",
        "url": "https://github.com/codex-aura/codex-aura",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Initialize storage
storage = SQLiteStorage()


class AnalyzeRequest(BaseModel):
    """Request model for analyze endpoint."""

    repo_path: str = "."
    edge_types: list[str] = ["imports", "calls", "extends"]
    options: dict = {}

    class Config:
        json_schema_extra = {
            "example": {
                "repo_path": "./my-python-project",
                "edge_types": ["imports", "calls"],
                "options": {"exclude_patterns": ["test_*"]}
            }
        }


class AnalyzeResponse(BaseModel):
    """Response model for analyze endpoint."""

    graph_id: str
    status: str
    stats: dict
    duration_ms: int


class GraphInfo(BaseModel):
    """Graph information model."""

    id: str
    repo_name: str
    repo_path: str
    sha: str | None = None
    created_at: datetime
    node_count: int
    edge_count: int


class GraphsResponse(BaseModel):
    """Response model for graphs endpoint."""

    graphs: list[GraphInfo]


class GraphResponse(BaseModel):
    """Response model for graph endpoint."""

    id: str
    repo_name: str
    created_at: str
    nodes: list
    edges: list
    stats: dict


class NodeResponse(BaseModel):
    """Response model for node endpoint."""

    node: dict
    edges: dict


class DependenciesResponse(BaseModel):
    """Response model for dependencies endpoint."""

    root: str
    depth: int
    nodes: list
    edges: list


class ContextRequest(BaseModel):
    """Request model for context endpoint."""

    graph_id: str
    entry_points: list[str]
    depth: int = 2
    include_code: bool = True
    max_nodes: int = 50

    class Config:
        json_schema_extra = {
            "example": {
                "graph_id": "g_abc123def456",
                "entry_points": ["module.main", "module.utils.Helper"],
                "depth": 3,
                "include_code": False,
                "max_nodes": 25
            }
        }

    @field_validator("depth")
    @classmethod
    def validate_depth(cls, v: int) -> int:
        """Validate depth is between 1 and 5."""
        if v < 1 or v > 5:
            raise ValueError("depth must be between 1 and 5")
        return v

    @field_validator("max_nodes")
    @classmethod
    def validate_max_nodes(cls, v: int) -> int:
        """Validate max_nodes is between 1 and 100."""
        if v < 1 or v > 100:
            raise ValueError("max_nodes must be between 1 and 100")
        return v


class ContextNode(BaseModel):
    """Context node model."""

    id: str
    type: str
    path: str
    code: str | None = None
    relevance: float


class ContextResponse(BaseModel):
    """Response model for context endpoint."""

    context_nodes: list[ContextNode]
    total_nodes: int
    truncated: bool


class AffectedFile(BaseModel):
    """Affected file model for impact analysis."""

    path: str
    impact_type: str  # "direct" or "transitive"
    edges: list[str] | None = None  # For direct impact
    distance: int | None = None  # For transitive impact


class ImpactResponse(BaseModel):
    """Response model for impact analysis endpoint."""

    changed_files: list[str]
    affected_files: list[AffectedFile]
    affected_tests: list[str]


class DeleteGraphResponse(BaseModel):
    """Response model for delete graph endpoint."""

    deleted: bool
    graph_id: str


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness check endpoint."""
    return {"status": "ready"}




@app.get("/api/v1/info")
async def info():
    """Server information endpoint."""
    return {
        "version": "0.1.0",
        "supported_languages": ["python"],
        "supported_edge_types": ["IMPORTS", "CALLS", "EXTENDS"],
        "storage_backend": "sqlite"
    }


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """
    Analyze a repository and generate a dependency graph.

    This endpoint performs static code analysis on a Python repository
    and generates a comprehensive dependency graph showing relationships
    between modules, classes, and functions.

    The analysis includes:
    - Import relationships between modules
    - Function/method calls
    - Class inheritance hierarchies
    - File dependencies

    The generated graph is stored and can be retrieved using the returned graph_id.
    """
    import time
    import uuid

    start_time = time.time()

    # Validate repo path
    repo_path = Path(request.repo_path)
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail="Repository path does not exist")
    if not repo_path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    try:
        # Analyze repository
        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(repo_path)

        # Generate graph ID
        graph_id = f"g_{uuid.uuid4().hex[:12]}"

        # Save graph to storage
        storage.save_graph(graph, graph_id)

        duration_ms = int((time.time() - start_time) * 1000)

        return AnalyzeResponse(
            graph_id=graph_id,
            status="completed",
            stats={
                "files": graph.stats.node_types.get("file", 0),
                "classes": graph.stats.node_types.get("class", 0),
                "functions": graph.stats.node_types.get("function", 0),
                "edges": {
                    "IMPORTS": sum(1 for edge in graph.edges if edge.type == "IMPORTS"),
                    "CALLS": sum(1 for edge in graph.edges if edge.type == "CALLS"),
                    "EXTENDS": sum(1 for edge in graph.edges if edge.type == "EXTENDS"),
                }
            },
            duration_ms=duration_ms
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/v1/graphs", response_model=GraphsResponse)
async def get_graphs(repo_path: str | None = None):
    """Get list of stored graphs."""
    graphs = storage.list_graphs(repo_path)
    return GraphsResponse(graphs=graphs)


@app.get("/api/v1/graph/{graph_id}", response_model=GraphResponse)
async def get_graph(
    graph_id: str,
    include_code: bool = False,
    node_types: str | None = None,
    edge_types: str | None = None
):
    """
    Retrieve a complete dependency graph.

    Returns the full graph data including all nodes and edges.
    Supports optional filtering by node types and edge types.

    Use include_code=true to include source code in node data (increases response size).
    """
    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Apply node type filtering
    filtered_nodes = graph.nodes
    if node_types:
        node_type_list = [t.strip() for t in node_types.split(",")]
        filtered_nodes = [n for n in graph.nodes if n.type in node_type_list]

    # Apply edge type filtering
    filtered_edges = graph.edges
    if edge_types:
        edge_type_list = [t.strip() for t in edge_types.split(",")]
        filtered_edges = [e for e in graph.edges if e.type.value in edge_type_list]

    # Convert nodes to dict format
    nodes_data = []
    for node in filtered_nodes:
        node_dict = node.model_dump()
        if not include_code and "code" in node_dict:
            del node_dict["code"]
        nodes_data.append(node_dict)

    # Convert edges to dict format
    edges_data = [edge.model_dump() for edge in filtered_edges]

    return GraphResponse(
        id=graph_id,
        repo_name=graph.repository.name,
        created_at=graph.generated_at.isoformat(),
        nodes=nodes_data,
        edges=edges_data,
        stats=graph.stats.model_dump()
    )


@app.get("/api/v1/graph/{graph_id}/node/{node_id}", response_model=NodeResponse)
async def get_node(graph_id: str, node_id: str):
    """Get information about a specific node."""
    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Find the node
    node = next((n for n in graph.nodes if n.id == node_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # Get incoming and outgoing edges
    incoming = [e for e in graph.edges if e.target == node_id]
    outgoing = [e for e in graph.edges if e.source == node_id]

    # Convert node to dict
    node_data = node.model_dump()

    # Add signature field for functions
    if node.type == "function" and hasattr(node, 'signature'):
        # Try to extract signature from docstring or code if available
        node_data["signature"] = f"def {node.name}(...)"  # Placeholder

    edges_data = {
        "incoming": [{"source": e.source, "type": e.type.value} for e in incoming],
        "outgoing": [{"target": e.target, "type": e.type.value} for e in outgoing]
    }

    return NodeResponse(node=node_data, edges=edges_data)


def traverse_dependencies(
    graph: Graph,
    start_node_id: str,
    max_depth: int,
    direction: str,
    edge_types: list[str] | None = None
) -> tuple[set[str], set[tuple[str, str, str]]]:
    """Traverse graph dependencies using BFS.

    Returns:
        Tuple of (node_ids, edges)
    """
    visited = set([start_node_id])
    edges = set()
    queue = deque([(start_node_id, 0)])  # (node_id, depth)

    while queue:
        current_node_id, depth = queue.popleft()

        if depth >= max_depth:
            continue

        # Get edges based on direction
        if direction in ["outgoing", "both"]:
            outgoing = [e for e in graph.edges if e.source == current_node_id]
            if edge_types:
                outgoing = [e for e in outgoing if e.type.value in edge_types]

            for edge in outgoing:
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, depth + 1))
                edges.add((edge.source, edge.target, edge.type.value))

        if direction in ["incoming", "both"]:
            incoming = [e for e in graph.edges if e.target == current_node_id]
            if edge_types:
                incoming = [e for e in incoming if e.type.value in edge_types]

            for edge in incoming:
                if edge.source not in visited:
                    visited.add(edge.source)
                    queue.append((edge.source, depth + 1))
                edges.add((edge.source, edge.target, edge.type.value))

    return visited, edges


@app.get("/api/v1/graph/{graph_id}/dependencies", response_model=DependenciesResponse)
async def get_dependencies(
    graph_id: str,
    node_id: str,
    depth: int = 2,
    direction: str = "both",
    edge_types: str | None = None
):
    """Get dependencies for a node with traversal options."""
    if depth < 1 or depth > 5:
        raise HTTPException(status_code=400, detail="Depth must be between 1 and 5")

    if direction not in ["incoming", "outgoing", "both"]:
        raise HTTPException(status_code=400, detail="Direction must be 'incoming', 'outgoing', or 'both'")

    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Check if node exists
    if not any(n.id == node_id for n in graph.nodes):
        raise HTTPException(status_code=404, detail="Node not found")

    # Parse edge types filter
    edge_type_list = None
    if edge_types:
        edge_type_list = [t.strip() for t in edge_types.split(",")]

    # Traverse dependencies
    node_ids, edge_tuples = traverse_dependencies(
        graph, node_id, depth, direction, edge_type_list
    )

    # Get nodes data
    nodes_data = [n.model_dump() for n in graph.nodes if n.id in node_ids]

    # Convert edges to dict format
    edges_data = [
        {"source": src, "target": tgt, "type": typ}
        for src, tgt, typ in edge_tuples
    ]

    return DependenciesResponse(
        root=node_id,
        depth=depth,
        nodes=nodes_data,
        edges=edges_data
    )


@app.post("/api/v1/context", response_model=ContextResponse)
async def get_context(request: ContextRequest):
    """
    Get contextual nodes around entry points.

    Performs breadth-first search traversal from specified entry points
    to gather relevant context nodes within the specified depth.

    Useful for understanding the code context around specific functions
    or classes, with relevance scoring based on distance from entry points.
    """
    # Validate depth
    if request.depth < 1 or request.depth > 5:
        raise HTTPException(status_code=400, detail="Depth must be between 1 and 5")

    # Validate max_nodes
    if request.max_nodes < 1 or request.max_nodes > 100:
        raise HTTPException(status_code=400, detail="max_nodes must be between 1 and 100")

    # Load graph
    graph = storage.load_graph(request.graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Validate entry points exist
    for entry_point in request.entry_points:
        if not any(n.id == entry_point for n in graph.nodes):
            raise HTTPException(status_code=404, detail=f"Entry point '{entry_point}' not found")

    # Collect all reachable nodes using BFS from all entry points
    all_visited = set()
    node_distances = {}  # node_id -> min_distance

    for entry_point in request.entry_points:
        visited, _ = traverse_dependencies(graph, entry_point, request.depth, "outgoing")
        for node_id in visited:
            if node_id not in all_visited:
                # Calculate distance from nearest entry point
                min_distance = float('inf')
                for ep in request.entry_points:
                    if ep == node_id:
                        min_distance = 0
                        break
                    # BFS to find distance
                    dist = _calculate_distance(graph, ep, node_id, request.depth)
                    if dist is not None:
                        min_distance = min(min_distance, dist)

                if min_distance != float('inf'):
                    node_distances[node_id] = min_distance
                    all_visited.add(node_id)

    # Sort nodes by distance (ascending)
    sorted_nodes = sorted(all_visited, key=lambda n: node_distances.get(n, float('inf')))

    # Apply max_nodes limit
    truncated = len(sorted_nodes) > request.max_nodes
    if truncated:
        sorted_nodes = sorted_nodes[:request.max_nodes]

    # Build context nodes
    context_nodes = []
    for node_id in sorted_nodes:
        node = next(n for n in graph.nodes if n.id == node_id)
        node_dict = node.model_dump()

        context_node = ContextNode(
            id=node.id,
            type=node.type,
            path=node.path,
            code=node_dict.get("code") if request.include_code else None,
            relevance=1.0 / (1 + node_distances.get(node_id, 0))  # Higher relevance for closer nodes
        )
        context_nodes.append(context_node)

    return ContextResponse(
        context_nodes=context_nodes,
        total_nodes=len(all_visited),
        truncated=truncated
    )


@app.get("/api/v1/graph/{graph_id}/impact", response_model=ImpactResponse)
async def get_impact_analysis(graph_id: str, files: str):
    """Analyze impact of changes to specified files."""
    # Parse changed files
    changed_files = [f.strip() for f in files.split(",") if f.strip()]

    if not changed_files:
        raise HTTPException(status_code=400, detail="No files specified")

    # Load graph
    graph = storage.load_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Validate changed files exist in graph
    graph_file_paths = {node.path for node in graph.nodes if node.type == "file"}
    for changed_file in changed_files:
        if changed_file not in graph_file_paths:
            raise HTTPException(status_code=404, detail=f"File '{changed_file}' not found in graph")

    # Find all affected files
    affected_files = []
    affected_file_paths = set()

    # Direct impact: files that directly import/use the changed files
    for changed_file in changed_files:
        # Find all nodes in the changed file
        changed_file_nodes = [n for n in graph.nodes if n.path == changed_file]

        for node in changed_file_nodes:
            # Find incoming edges (who imports/calls this node)
            incoming_edges = [e for e in graph.edges if e.target == node.id]

            for edge in incoming_edges:
                # Find the file containing the source node
                source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                if source_node and source_node.path not in affected_file_paths and source_node.path not in changed_files:
                    affected_file_paths.add(source_node.path)

                    # Collect edge types for this file
                    file_edges = set()
                    for e in incoming_edges:
                        src_node = next((n for n in graph.nodes if n.id == e.source), None)
                        if src_node and src_node.path == source_node.path:
                            file_edges.add(e.type.value)

                    affected_files.append(AffectedFile(
                        path=source_node.path,
                        impact_type="direct",
                        edges=list(file_edges)
                    ))

    # Transitive impact: files affected by the directly affected files (up to depth 3)
    max_transitive_depth = 3
    visited_transitive = set(affected_file_paths)

    for depth in range(1, max_transitive_depth + 1):
        new_affected = set()

        for affected_path in affected_file_paths - set(changed_files):
            if affected_path in visited_transitive:
                # Find nodes in this affected file
                affected_file_nodes = [n for n in graph.nodes if n.path == affected_path]

                for node in affected_file_nodes:
                    # Find incoming edges
                    incoming_edges = [e for e in graph.edges if e.target == node.id]

                    for edge in incoming_edges:
                        source_node = next((n for n in graph.nodes if n.id == edge.source), None)
                        if (source_node and
                            source_node.path not in visited_transitive and
                            source_node.path not in changed_files):

                            new_affected.add(source_node.path)

        # Add new transitive affected files
        for new_path in new_affected:
            affected_files.append(AffectedFile(
                path=new_path,
                impact_type="transitive",
                distance=depth + 1  # +1 because direct is depth 1
            ))

        affected_file_paths.update(new_affected)
        visited_transitive.update(new_affected)

        if not new_affected:
            break

    # Find affected tests
    affected_tests = []
    test_prefixes = ["test_", "tests/", "test/"]

    for affected_path in affected_file_paths:
        # Generate potential test file names
        test_candidates = []

        # Same directory with test_ prefix
        import os
        dir_name = os.path.dirname(affected_path)
        base_name = os.path.basename(affected_path)
        name_without_ext = os.path.splitext(base_name)[0]

        test_candidates.append(os.path.join(dir_name, f"test_{base_name}"))
        test_candidates.append(os.path.join(dir_name, f"test_{name_without_ext}.py"))

        # tests/ directory
        test_candidates.append(os.path.join("tests", base_name))
        test_candidates.append(os.path.join("tests", f"test_{base_name}"))
        test_candidates.append(os.path.join("tests", f"test_{name_without_ext}.py"))

        # Check if any test candidates exist in the graph
        for candidate in test_candidates:
            if any(n.path == candidate for n in graph.nodes if n.type == "file"):
                affected_tests.append(candidate)
                break

    return ImpactResponse(
        changed_files=changed_files,
        affected_files=affected_files,
        affected_tests=affected_tests
    )


def _calculate_distance(graph: Graph, start_node: str, target_node: str, max_depth: int) -> int | None:
    """Calculate shortest path distance between two nodes using BFS."""
    if start_node == target_node:
        return 0

    visited = set([start_node])
    queue = deque([(start_node, 0)])  # (node_id, depth)

    while queue:
        current_node_id, depth = queue.popleft()

        if depth >= max_depth:
            continue

        # Get outgoing edges
        outgoing = [e for e in graph.edges if e.source == current_node_id]

        for edge in outgoing:
            if edge.target == target_node:
                return depth + 1

            if edge.target not in visited:
                visited.add(edge.target)
                queue.append((edge.target, depth + 1))

    return None


@app.delete("/api/v1/graph/{graph_id}", response_model=DeleteGraphResponse)
async def delete_graph(graph_id: str):
    """Delete a graph from storage."""
    deleted = storage.delete_graph(graph_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Graph not found")

    return DeleteGraphResponse(deleted=True, graph_id=graph_id)