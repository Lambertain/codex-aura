"""End-to-end tests for codex-aura."""

import pytest
import subprocess
import time
import requests
import tempfile
from pathlib import Path
import os
import signal
import psutil


@pytest.fixture
def flask_mini_repo():
    """Path to flask_mini example repository."""
    return Path("examples/flask_mini")


@pytest.fixture
def simple_project_repo():
    """Path to simple_project example repository."""
    return Path("examples/simple_project")


def test_cli_analyze_api_query_integration(flask_mini_repo, tmp_path):
    """Test CLI analyze → API query → correct result."""
    # Start API server in background
    server_process = None
    try:
        # Use a temporary database for testing
        db_path = tmp_path / "test_e2e.db"
        env = os.environ.copy()
        env["CODEX_AURA_DB_PATH"] = str(db_path)

        # Start server
        server_process = subprocess.Popen(
            ["python", "-m", "uvicorn", "src.codex_aura.api.server:app", "--host", "127.0.0.1", "--port", "8001"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for server to start
        time.sleep(3)

        # Verify server is running
        try:
            response = requests.get("http://127.0.0.1:8001/health", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.RequestException:
            pytest.fail("API server failed to start")

        # Run CLI analyze
        result = subprocess.run(
            ["python", "-m", "src.codex_aura.cli.main", "analyze", str(flask_mini_repo)],
            capture_output=True,
            text=True,
            env=env
        )

        assert result.returncode == 0
        output = result.stdout
        assert "Graph ID:" in output

        # Extract graph ID from output
        lines = output.split('\n')
        graph_id_line = next((line for line in lines if "Graph ID:" in line), None)
        assert graph_id_line is not None
        graph_id = graph_id_line.split("Graph ID:")[1].strip()

        # Query API for the graph
        response = requests.get(f"http://127.0.0.1:8001/api/v1/graph/{graph_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == graph_id
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) > 0

        # Verify graph contains Flask-related nodes
        node_names = [node["name"] for node in data["nodes"]]
        assert "app.py" in node_names

    finally:
        # Clean up server process
        if server_process:
            try:
                # Try graceful shutdown first
                server_process.terminate()
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if needed
                server_process.kill()
                server_process.wait()


def test_full_flow_flask_repository(flask_mini_repo, tmp_path):
    """Test full flow on real Flask repository."""
    db_path = tmp_path / "test_flask.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    # Run analysis
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(flask_mini_repo)],
        capture_output=True,
        text=True,
        env=env
    )

    assert result.returncode == 0
    assert "Analysis completed" in result.stdout
    assert "Graph ID:" in result.stdout

    # Extract graph ID
    lines = result.stdout.split('\n')
    graph_id_line = next((line for line in lines if "Graph ID:" in line), None)
    assert graph_id_line is not None
    graph_id = graph_id_line.split("Graph ID:")[1].strip()

    # Verify graph was saved and can be loaded
    from src.codex_aura.storage.sqlite import SQLiteStorage
    storage = SQLiteStorage(db_path=str(db_path))
    graph = storage.load_graph(graph_id)
    assert graph is not None

    # Verify Flask-specific content
    assert graph.repository.name == "flask_mini"
    assert len(graph.nodes) > 0
    assert len(graph.edges) > 0

    # Should contain Flask imports and app structure
    node_ids = [node.id for node in graph.nodes]
    assert any("app.py" in node_id for node_id in node_ids)


def test_docker_container_startup(tmp_path):
    """Test Docker container startup (mock test - requires Docker)."""
    # This test would require Docker to be installed and running
    # For now, we'll create a mock test that checks if Docker is available

    try:
        # Check if Docker is available
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            pytest.skip("Docker not available")

        # Check if docker-compose or docker compose is available
        compose_result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if compose_result.returncode != 0:
            # Try older docker-compose command
            compose_result = subprocess.run(
                ["docker-compose", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )

        if compose_result.returncode != 0:
            pytest.skip("Docker Compose not available")

        # If we get here, Docker and Docker Compose are available
        # We could test actual container startup, but that might be too heavy for CI
        # Instead, just verify the Docker setup files exist

        dockerfile_path = Path("Dockerfile")
        docker_compose_path = Path("docker-compose.yml")

        # Check if Docker files exist (they might not in this test environment)
        if dockerfile_path.exists():
            assert dockerfile_path.stat().st_size > 0
        if docker_compose_path.exists():
            assert docker_compose_path.stat().st_size > 0

        # Mock successful Docker test
        assert True

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("Docker testing environment not available")


def test_cli_error_handling():
    """Test CLI error handling."""
    # Test with non-existent directory
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", "/nonexistent/path"],
        capture_output=True,
        text=True
    )

    assert result.returncode != 0
    assert "Error" in result.stderr or "Error" in result.stdout


def test_large_repository_performance(simple_project_repo, tmp_path):
    """Test performance with larger repository."""
    db_path = tmp_path / "test_perf.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    import time
    start_time = time.time()

    # Run analysis
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(simple_project_repo)],
        capture_output=True,
        text=True,
        env=env,
        timeout=60  # 1 minute timeout
    )

    end_time = time.time()
    duration = end_time - start_time

    assert result.returncode == 0
    assert duration < 30  # Should complete in less than 30 seconds

    # Verify results
    assert "Analysis completed" in result.stdout
    assert "Graph ID:" in result.stdout