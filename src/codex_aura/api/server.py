"""FastAPI server for codex-aura."""

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..analyzer.python import PythonAnalyzer
from ..models.graph import Graph, save_graph
from ..storage.sqlite import SQLiteStorage
from collections import deque

app = FastAPI(title="Codex Aura API", version="0.1.0")

# Initialize storage
storage = SQLiteStorage()


class AnalyzeRequest(BaseModel):
    """Request model for analyze endpoint."""

    repo_path: str
    edge_types: list[str]
    options: dict = {}


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
    """Analyze a repository and store the graph."""
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
    """Get complete graph with optional filtering."""
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