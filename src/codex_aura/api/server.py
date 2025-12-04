"""FastAPI server for codex-aura."""

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..analyzer.python import PythonAnalyzer
from ..models.graph import Graph, save_graph
from ..storage.sqlite import SQLiteStorage

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