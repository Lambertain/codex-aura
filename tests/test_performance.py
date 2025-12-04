"""Performance tests for codex-aura."""

import pytest
import time
import tempfile
import subprocess
from pathlib import Path
import os
import shutil


@pytest.fixture
def large_test_repo(tmp_path):
    """Create a large test repository with many files."""
    repo_path = tmp_path / "large_repo"
    repo_path.mkdir()

    # Create a Python package structure with many modules
    create_large_python_package(repo_path, num_modules=50, lines_per_module=200)

    return repo_path


def create_large_python_package(base_path: Path, num_modules: int = 50, lines_per_module: int = 200):
    """Create a large Python package for performance testing."""
    # Create __init__.py
    (base_path / "__init__.py").write_text('"""Large test package."""\n')

    # Create main module
    main_content = ['"""Main module."""\n']
    for i in range(lines_per_module // 10):  # Add some substantial content
        main_content.append(f"""
def function_{i}():
    \"\"\"Function {i}.\"\"\"
    return {i}

class Class{i}(object):
    \"\"\"Class {i}.\"\"\"

    def method_{i}(self):
        \"\"\"Method {i}.\"\"\"
        return self
""")
    (base_path / "main.py").write_text("".join(main_content))

    # Create multiple modules
    for i in range(num_modules):
        module_content = [f'"""Module {i}."""\n']
        module_content.append("from main import function_0\n\n")

        # Add imports between modules to create dependencies
        if i > 0:
            module_content.append(f"from module_{i-1} import Class{i-1}\n\n")

        # Add functions and classes
        for j in range(min(10, lines_per_module // 20)):
            module_content.append(f"""
def module_{i}_function_{j}():
    \"\"\"Function {j} in module {i}.\"\"\"
    return {i * j}

class Module{i}Class{j}:
    \"\"\"Class {j} in module {i}.\"\"\"

    def __init__(self):
        self.value = {i + j}

    def get_value(self):
        return self.value
""")

        (base_path / f"module_{i}.py").write_text("".join(module_content))

    # Create subpackages
    for i in range(5):
        subpackage_path = base_path / f"subpackage_{i}"
        subpackage_path.mkdir()
        (subpackage_path / "__init__.py").write_text(f'"""Subpackage {i}."""\n')

        # Add a few modules to each subpackage
        for j in range(3):
            (subpackage_path / f"submodule_{i}_{j}.py").write_text(f'''
"""Submodule {i}.{j}."""

def sub_function_{i}_{j}():
    """Function in submodule {i}.{j}."""
    return {i + j}
''')


@pytest.mark.performance
def test_10k_loc_performance(large_test_repo, tmp_path):
    """Test performance with ~10K LOC repository."""
    # Count lines of code
    total_lines = 0
    for py_file in large_test_repo.rglob("*.py"):
        total_lines += sum(1 for line in py_file.read_text().splitlines() if line.strip())

    # Should be around 10K LOC
    assert total_lines > 5000, f"Test repo has only {total_lines} lines, need more for 10K test"

    db_path = tmp_path / "perf_10k.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    start_time = time.time()

    # Run analysis
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(large_test_repo)],
        capture_output=True,
        text=True,
        env=env,
        timeout=300  # 5 minute timeout
    )

    end_time = time.time()
    duration = end_time - start_time

    assert result.returncode == 0, f"Analysis failed: {result.stderr}"
    assert duration < 5.0, f"Analysis took {duration:.2f}s, should be < 5s for 10K LOC"

    print(f"10K LOC analysis completed in {duration:.2f}s")


@pytest.mark.performance
def test_100k_loc_performance(tmp_path):
    """Test performance with ~100K LOC repository (synthetic)."""
    # Create a very large synthetic repository
    repo_path = tmp_path / "huge_repo"
    repo_path.mkdir()

    # Create many files with substantial content
    total_lines = 0
    target_lines = 100000

    file_count = 0
    while total_lines < target_lines and file_count < 500:
        file_count += 1
        file_path = repo_path / f"large_module_{file_count}.py"

        # Create a large file
        content_lines = [f'"""Large module {file_count}. """\n']
        functions_per_file = 100

        for i in range(functions_per_file):
            content_lines.append(f"""
def function_{file_count}_{i}(param1, param2=None):
    \"\"\"Function {i} in module {file_count}.

    This is a synthetic function for performance testing.
    It has multiple parameters and some logic.
    \"\"\"
    if param2 is None:
        param2 = param1 * 2

    result = param1 + param2 + {file_count} + {i}

    # Add some complexity
    for j in range(10):
        result += j

    return result

class Class{file_count}_{i}:
    \"\"\"Class {i} in module {file_count}.\"\"\"

    def __init__(self, value={file_count + i}):
        self.value = value

    def method_{i}(self, multiplier=1):
        return self.value * multiplier * {i}
""")

        content = "".join(content_lines)
        file_path.write_text(content)

        # Count lines
        file_lines = len(content.splitlines())
        total_lines += file_lines

        if total_lines >= target_lines:
            break

    print(f"Created synthetic repo with {total_lines} lines in {file_count} files")

    db_path = tmp_path / "perf_100k.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    start_time = time.time()

    # Run analysis with timeout
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(repo_path)],
        capture_output=True,
        text=True,
        env=env,
        timeout=1800  # 30 minute timeout
    )

    end_time = time.time()
    duration = end_time - start_time

    assert result.returncode == 0, f"Analysis failed: {result.stderr}"
    assert duration < 30.0, f"Analysis took {duration:.2f}s, should be < 30s for 100K LOC"

    print(f"100K LOC analysis completed in {duration:.2f}s")


@pytest.mark.performance
def test_api_response_time_cold(large_test_repo, tmp_path):
    """Test API response time for cold analysis."""
    import requests
    import threading
    import time

    # Start API server in background thread
    server_started = threading.Event()
    server_error = None

    def run_server():
        nonlocal server_error
        try:
            db_path = tmp_path / "api_perf.db"
            env = os.environ.copy()
            env["CODEX_AURA_DB_PATH"] = str(db_path)

            result = subprocess.run(
                ["python", "-m", "uvicorn", "src.codex_aura.api.server:app",
                 "--host", "127.0.0.1", "--port", "8002"],
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                server_error = result.stderr
        except Exception as e:
            server_error = str(e)
        finally:
            server_started.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start or timeout
    server_started.wait(timeout=10)

    if server_error:
        pytest.fail(f"Server failed to start: {server_error}")

    # Give server a moment to fully start
    time.sleep(2)

    try:
        # Test cold analysis (first request)
        start_time = time.time()

        response = requests.post(
            "http://127.0.0.1:8002/api/v1/analyze",
            json={"repo_path": str(large_test_repo)},
            timeout=60
        )

        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        assert duration < 500, f"Cold analysis took {duration:.0f}ms, should be < 500ms"

        print(f"Cold API analysis completed in {duration:.0f}ms")

    except requests.exceptions.RequestException as e:
        pytest.fail(f"API request failed: {e}")


@pytest.mark.performance
def test_api_response_time_cached(large_test_repo, tmp_path):
    """Test API response time for cached queries."""
    import requests
    import threading
    import time

    # First, do an analysis to populate cache
    db_path = tmp_path / "api_cached.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    # Pre-analyze the repository
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(large_test_repo)],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0

    # Extract graph ID
    lines = result.stdout.split('\n')
    graph_id_line = next((line for line in lines if "Graph ID:" in line), None)
    assert graph_id_line is not None
    graph_id = graph_id_line.split("Graph ID:")[1].strip()

    # Start API server
    server_started = threading.Event()
    server_error = None

    def run_server():
        nonlocal server_error
        try:
            result = subprocess.run(
                ["python", "-m", "uvicorn", "src.codex_aura.api.server:app",
                 "--host", "127.0.0.1", "--port", "8003"],
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                server_error = result.stderr
        except Exception as e:
            server_error = str(e)
        finally:
            server_started.set()

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    server_started.wait(timeout=10)

    if server_error:
        pytest.fail(f"Server failed to start: {server_error}")

    time.sleep(2)  # Let server fully start

    try:
        # Test cached graph retrieval
        start_time = time.time()

        response = requests.get(f"http://127.0.0.1:8003/api/v1/graph/{graph_id}", timeout=10)

        end_time = time.time()
        duration = (end_time - start_time) * 1000  # Convert to milliseconds

        assert response.status_code == 200
        assert duration < 100, f"Cached API query took {duration:.0f}ms, should be < 100ms"

        print(f"Cached API query completed in {duration:.0f}ms")

    except requests.exceptions.RequestException as e:
        pytest.fail(f"API request failed: {e}")


@pytest.mark.performance
def test_memory_usage_during_analysis(large_test_repo, tmp_path):
    """Test memory usage during analysis."""
    import psutil
    import os

    db_path = tmp_path / "memory_test.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    # Get initial memory usage
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Run analysis
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(large_test_repo)],
        capture_output=True,
        text=True,
        env=env
    )

    assert result.returncode == 0

    # Check final memory usage
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    # Memory increase should be reasonable (less than 500MB for large repo)
    assert memory_increase < 500, f"Memory usage increased by {memory_increase:.1f}MB, should be < 500MB"

    print(f"Memory usage: {initial_memory:.1f}MB -> {final_memory:.1f}MB (+{memory_increase:.1f}MB)")


@pytest.mark.performance
def test_concurrent_api_requests(large_test_repo, tmp_path):
    """Test concurrent API requests."""
    import requests
    import threading
    import time
    import concurrent.futures

    db_path = tmp_path / "concurrent_test.db"
    env = os.environ.copy()
    env["CODEX_AURA_DB_PATH"] = str(db_path)

    # Pre-analyze to have a graph
    result = subprocess.run(
        ["python", "-m", "src.codex_aura.cli.main", "analyze", str(large_test_repo)],
        capture_output=True,
        text=True,
        env=env
    )
    assert result.returncode == 0

    graph_id_line = next((line for line in result.stdout.split('\n') if "Graph ID:" in line), None)
    graph_id = graph_id_line.split("Graph ID:")[1].strip()

    # Start server
    server_thread = threading.Thread(
        target=lambda: subprocess.run(
            ["python", "-m", "uvicorn", "src.codex_aura.api.server:app",
             "--host", "127.0.0.1", "--port", "8004"],
            env=env,
            capture_output=True
        ),
        daemon=True
    )
    server_thread.start()
    time.sleep(3)  # Wait for server

    def make_request():
        try:
            response = requests.get(f"http://127.0.0.1:8004/api/v1/graph/{graph_id}", timeout=10)
            return response.status_code == 200
        except:
            return False

    # Make 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    success_count = sum(results)
    assert success_count >= 8, f"Only {success_count}/10 concurrent requests succeeded"

    print(f"Concurrent requests: {success_count}/10 succeeded")