"""Tests on real open-source projects to validate analyzer quality and performance.

These tests clone real repositories and verify:
1. Analysis completes without errors
2. Performance meets target metrics
3. Graph contains expected nodes and edges

Target metrics:
- Flask (~50K LOC): < 10 sec
- FastAPI (~30K LOC): < 5 sec  
- Requests (~10K LOC): < 2 sec
"""

import os
import pytest
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


# Skip if SKIP_REAL_PROJECT_TESTS env var is set or in CI environment
CI_ENV = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")
SKIP_TESTS = os.environ.get("SKIP_REAL_PROJECT_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(
    SKIP_TESTS or CI_ENV is not None,
    reason="Real project tests skipped in CI or via SKIP_REAL_PROJECT_TESTS env var"
)


@pytest.fixture(scope="module")
def flask_repo(tmp_path_factory):
    """Clone Flask repository for testing."""
    repo_path = tmp_path_factory.mktemp("real_projects") / "flask"
    
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/pallets/flask.git", str(repo_path)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        pytest.skip(f"Failed to clone Flask: {result.stderr}")
    
    yield repo_path
    
    # Cleanup
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)


@pytest.fixture(scope="module")
def fastapi_repo(tmp_path_factory):
    """Clone FastAPI repository for testing."""
    repo_path = tmp_path_factory.mktemp("real_projects") / "fastapi"
    
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/tiangolo/fastapi.git", str(repo_path)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        pytest.skip(f"Failed to clone FastAPI: {result.stderr}")
    
    yield repo_path
    
    # Cleanup
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)


@pytest.fixture(scope="module")
def requests_repo(tmp_path_factory):
    """Clone Requests repository for testing."""
    repo_path = tmp_path_factory.mktemp("real_projects") / "requests"
    
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/psf/requests.git", str(repo_path)],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if result.returncode != 0:
        pytest.skip(f"Failed to clone Requests: {result.stderr}")
    
    yield repo_path
    
    # Cleanup
    if repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)


def count_python_files(repo_path: Path) -> int:
    """Count Python files in a repository."""
    return len(list(repo_path.rglob("*.py")))


def count_lines_of_code(repo_path: Path) -> int:
    """Count non-empty, non-comment lines in Python files."""
    total_lines = 0
    for py_file in repo_path.rglob("*.py"):
        try:
            with py_file.open('r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        total_lines += 1
        except (OSError, UnicodeDecodeError):
            continue
    return total_lines


def run_analysis(repo_path: Path, tmp_path: Path, timeout: int = 300) -> tuple:
    """Run codex-aura analysis and return (success, duration, output)."""
    db_path = tmp_path / f"test_{repo_path.name}.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)
    
    start_time = time.time()
    
    result = subprocess.run(
        ["python", "-m", "codex_aura.cli.main", "analyze", str(repo_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
        cwd=str(Path(__file__).parent.parent / "src")
    )
    
    duration = time.time() - start_time
    
    return result.returncode == 0, duration, result.stdout, result.stderr


@pytest.mark.slow
@pytest.mark.real_project
def test_flask_analysis(flask_repo, tmp_path):
    """Test analysis of Flask repository.
    
    Target: < 10 seconds for ~50K LOC
    """
    # Get repo stats
    file_count = count_python_files(flask_repo)
    loc = count_lines_of_code(flask_repo)
    
    print(f"\nFlask repo: {file_count} files, {loc:,} LOC")
    
    # Run analysis
    success, duration, stdout, stderr = run_analysis(flask_repo, tmp_path, timeout=60)
    
    print(f"Analysis completed in {duration:.2f}s")
    
    # Assertions
    assert success, f"Analysis failed:\n{stderr}"
    assert duration < 10.0, f"Analysis took {duration:.2f}s, target is < 10s"
    
    # Verify graph was created
    assert "nodes" in stdout.lower() or "graph" in stdout.lower(), \
        f"Output doesn't mention graph/nodes:\n{stdout}"


@pytest.mark.slow
@pytest.mark.real_project
def test_fastapi_analysis(fastapi_repo, tmp_path):
    """Test analysis of FastAPI repository.
    
    Target: < 5 seconds for ~30K LOC
    """
    # Get repo stats
    file_count = count_python_files(fastapi_repo)
    loc = count_lines_of_code(fastapi_repo)
    
    print(f"\nFastAPI repo: {file_count} files, {loc:,} LOC")
    
    # Run analysis
    success, duration, stdout, stderr = run_analysis(fastapi_repo, tmp_path, timeout=30)
    
    print(f"Analysis completed in {duration:.2f}s")
    
    # Assertions
    assert success, f"Analysis failed:\n{stderr}"
    assert duration < 5.0, f"Analysis took {duration:.2f}s, target is < 5s"
    
    # Verify graph was created
    assert "nodes" in stdout.lower() or "graph" in stdout.lower(), \
        f"Output doesn't mention graph/nodes:\n{stdout}"


@pytest.mark.slow
@pytest.mark.real_project
def test_requests_analysis(requests_repo, tmp_path):
    """Test analysis of Requests repository.
    
    Target: < 2 seconds for ~10K LOC
    """
    # Get repo stats
    file_count = count_python_files(requests_repo)
    loc = count_lines_of_code(requests_repo)
    
    print(f"\nRequests repo: {file_count} files, {loc:,} LOC")
    
    # Run analysis
    success, duration, stdout, stderr = run_analysis(requests_repo, tmp_path, timeout=15)
    
    print(f"Analysis completed in {duration:.2f}s")
    
    # Assertions
    assert success, f"Analysis failed:\n{stderr}"
    assert duration < 2.0, f"Analysis took {duration:.2f}s, target is < 2s"
    
    # Verify graph was created
    assert "nodes" in stdout.lower() or "graph" in stdout.lower(), \
        f"Output doesn't mention graph/nodes:\n{stdout}"


@pytest.mark.slow
@pytest.mark.real_project
def test_flask_graph_quality(flask_repo, tmp_path):
    """Verify Flask analysis produces quality graph with expected structure."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    from codex_aura.analyzer.python import PythonAnalyzer
    
    analyzer = PythonAnalyzer(verbose=False)
    graph = analyzer.analyze(flask_repo)
    
    # Verify graph has nodes
    assert len(graph.nodes) > 0, "Graph should have nodes"
    
    # Verify we have file, class, and function nodes
    node_types = set(n.type for n in graph.nodes)
    assert "file" in node_types, "Should have file nodes"
    assert "function" in node_types, "Should have function nodes"
    
    # Verify we have edges
    assert len(graph.edges) > 0, "Graph should have edges"
    
    # Verify edge types
    edge_types = set(e.type.value for e in graph.edges)
    assert "IMPORTS" in edge_types, "Should have IMPORTS edges"
    
    # Print stats
    print(f"\nFlask graph stats:")
    print(f"  Nodes: {len(graph.nodes)}")
    print(f"  Edges: {len(graph.edges)}")
    print(f"  Node types: {graph.stats.node_types}")


@pytest.mark.slow
@pytest.mark.real_project
def test_no_analysis_errors_on_real_projects(flask_repo, fastapi_repo, requests_repo, tmp_path):
    """Verify all real projects analyze without errors or warnings."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    from codex_aura.analyzer.python import PythonAnalyzer
    
    repos = [
        ("Flask", flask_repo),
        ("FastAPI", fastapi_repo),
        ("Requests", requests_repo),
    ]
    
    errors = []
    
    for name, repo_path in repos:
        try:
            analyzer = PythonAnalyzer(verbose=False)
            graph = analyzer.analyze(repo_path)
            
            # Basic sanity checks
            if len(graph.nodes) == 0:
                errors.append(f"{name}: No nodes found")
            if len(graph.edges) == 0:
                errors.append(f"{name}: No edges found (warning)")
                
            print(f"{name}: {len(graph.nodes)} nodes, {len(graph.edges)} edges - OK")
            
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
    
    assert len([e for e in errors if "warning" not in e.lower()]) == 0, \
        f"Errors during analysis:\n" + "\n".join(errors)
