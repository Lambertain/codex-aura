"""API integration tests for codex-aura endpoints."""

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from unittest.mock import patch, MagicMock
from datetime import datetime

from codex_aura.api.server import app
from codex_aura.models.graph import Graph, Repository, Stats
from codex_aura.models.node import Node
from codex_aura.models.edge import Edge, EdgeType


@pytest_asyncio.fixture
async def client():
    """HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    nodes = [
        Node(id="main.py", type="file", name="main.py", path="main.py"),
        Node(id="utils.py", type="file", name="utils.py", path="utils.py"),
        Node(id="main.py::main", type="function", name="main", path="main.py", lines=[1, 10]),
    ]

    edges = [
        Edge(source="main.py", target="utils.py", type=EdgeType.IMPORTS),
        Edge(source="main.py::main", target="utils.py", type=EdgeType.CALLS),
    ]

    stats = Stats(total_nodes=3, total_edges=2, node_types={"file": 2, "function": 1})
    repository = Repository(path="/test/repo", name="test-repo")

    return Graph(
        version="0.1",
        generated_at=datetime.now(),
        repository=repository,
        stats=stats,
        nodes=nodes,
        edges=edges
    )


@pytest.fixture
def sample_graph_id(sample_graph):
    """Save sample graph and return its ID."""
    from codex_aura.api.server import storage
    graph_id = "test_graph_123"
    storage.save_graph(sample_graph, graph_id)
    return graph_id


@pytest.mark.asyncio
async def test_analyze_endpoint(client, tmp_path):
    """Test the analyze endpoint."""
    # Mock the analyzer to avoid actual analysis
    with patch('codex_aura.api.server.PythonAnalyzer') as mock_analyzer_class:
        mock_analyzer = MagicMock()
        mock_analyzer_class.return_value = mock_analyzer

        # Create a mock graph
        nodes = [Node(id="test.py", type="file", name="test.py", path="test.py")]
        edges = []
        stats = Stats(total_nodes=1, total_edges=0, node_types={"file": 1})
        repository = Repository(path=str(tmp_path), name="test-repo")

        mock_graph = Graph(
            version="0.1",
            generated_at=datetime.now(),
            repository=repository,
            stats=stats,
            nodes=nodes,
            edges=edges
        )
        mock_analyzer.analyze.return_value = mock_graph

        response = await client.post("/api/v1/analyze", json={
            "repo_path": str(tmp_path)
        })

        assert response.status_code == 200
        data = response.json()
        assert "graph_id" in data
        assert data["status"] == "completed"
        assert "stats" in data
        assert data["stats"]["files"] == 1


@pytest.mark.asyncio
async def test_analyze_endpoint_invalid_path(client):
    """Test analyze endpoint with invalid path."""
    response = await client.post("/api/v1/analyze", json={
        "repo_path": "/nonexistent/path"
    })

    # Pydantic validation returns 422 for invalid paths
    assert response.status_code == 422
    # Check that error message mentions path doesn't exist
    error_detail = response.json()["detail"]
    assert any("does not exist" in str(err) or "not exist" in str(err) for err in error_detail)


@pytest.mark.asyncio
async def test_context_endpoint(client, sample_graph_id):
    """Test the context endpoint."""
    response = await client.post("/api/v1/context", json={
        "graph_id": sample_graph_id,
        "entry_points": ["main.py"],
        "depth": 2,
        "include_code": False
    })

    assert response.status_code == 200
    data = response.json()
    assert "context_nodes" in data
    assert "total_nodes" in data
    assert "truncated" in data
    assert len(data["context_nodes"]) > 0

    # Check node structure
    node = data["context_nodes"][0]
    assert "id" in node
    assert "type" in node
    assert "path" in node
    assert "relevance" in node


@pytest.mark.asyncio
async def test_context_endpoint_invalid_graph(client):
    """Test context endpoint with invalid graph ID."""
    response = await client.post("/api/v1/context", json={
        "graph_id": "nonexistent",
        "entry_points": ["main.py"]
    })

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_context_endpoint_invalid_entry_point(client, sample_graph_id):
    """Test context endpoint with invalid entry point."""
    response = await client.post("/api/v1/context", json={
        "graph_id": sample_graph_id,
        "entry_points": ["nonexistent.py"]
    })

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_graphs_endpoint(client, sample_graph_id):
    """Test the get graphs endpoint."""
    response = await client.get("/api/v1/graphs")

    assert response.status_code == 200
    data = response.json()
    assert "graphs" in data
    assert len(data["graphs"]) >= 1

    # Check graph info structure
    graph_info = data["graphs"][0]
    assert "id" in graph_info
    assert "repo_name" in graph_info
    assert "repo_path" in graph_info
    assert "created_at" in graph_info
    assert "node_count" in graph_info
    assert "edge_count" in graph_info


@pytest.mark.asyncio
async def test_get_graph_endpoint(client, sample_graph_id):
    """Test the get graph endpoint."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_graph_id
    assert "nodes" in data
    assert "edges" in data
    assert "stats" in data
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2


@pytest.mark.asyncio
async def test_get_graph_endpoint_invalid_id(client):
    """Test get graph endpoint with invalid ID."""
    response = await client.get("/api/v1/graph/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_graph_endpoint_with_filters(client, sample_graph_id):
    """Test get graph endpoint with node and edge type filters."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}?node_types=file,function")

    assert response.status_code == 200
    data = response.json()
    # Should only include file and function nodes
    node_types = {node["type"] for node in data["nodes"]}
    assert node_types == {"file", "function"}


@pytest.mark.asyncio
async def test_get_node_endpoint(client, sample_graph_id):
    """Test the get node endpoint."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}/node/main.py")

    assert response.status_code == 200
    data = response.json()
    assert "node" in data
    assert "edges" in data
    assert data["node"]["id"] == "main.py"
    assert data["node"]["type"] == "file"

    # Check edges structure
    assert "incoming" in data["edges"]
    assert "outgoing" in data["edges"]


@pytest.mark.asyncio
async def test_get_node_endpoint_invalid_node(client, sample_graph_id):
    """Test get node endpoint with invalid node ID."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}/node/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_dependencies_endpoint(client, sample_graph_id):
    """Test the get dependencies endpoint."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}/dependencies?node_id=main.py&depth=2&direction=outgoing")

    assert response.status_code == 200
    data = response.json()
    assert data["root"] == "main.py"
    assert data["depth"] == 2
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 1
    assert len(data["edges"]) >= 1


@pytest.mark.asyncio
async def test_get_dependencies_endpoint_invalid_depth(client, sample_graph_id):
    """Test get dependencies endpoint with invalid depth."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}/dependencies?node_id=main.py&depth=10")

    assert response.status_code == 400
    assert "must be between 1 and 5" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_dependencies_endpoint_invalid_direction(client, sample_graph_id):
    """Test get dependencies endpoint with invalid direction."""
    response = await client.get(f"/api/v1/graph/{sample_graph_id}/dependencies?node_id=main.py&direction=invalid")

    assert response.status_code == 400
    assert "must be 'incoming', 'outgoing', or 'both'" in response.json()["detail"]


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Test the health endpoint."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data


@pytest.mark.asyncio
async def test_ready_endpoint(client):
    """Test the ready endpoint."""
    response = await client.get("/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "version" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_info_endpoint(client):
    """Test the info endpoint."""
    response = await client.get("/api/v1/info")

    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "supported_languages" in data
    assert "supported_edge_types" in data
    assert "storage_backend" in data
    assert data["storage_backend"] == "sqlite"


@pytest.mark.asyncio
async def test_delete_graph_endpoint(client, sample_graph_id):
    """Test the delete graph endpoint."""
    response = await client.delete(f"/api/v1/graph/{sample_graph_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["graph_id"] == sample_graph_id

    # Verify graph is gone
    response = await client.get(f"/api/v1/graph/{sample_graph_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_graph_endpoint_invalid_id(client):
    """Test delete graph endpoint with invalid ID."""
    response = await client.delete("/api/v1/graph/nonexistent")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
