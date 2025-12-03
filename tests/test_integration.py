import subprocess
import sys
import time
from pathlib import Path
import pytest

from codex_aura.analyzer.python import PythonAnalyzer


class TestIntegration:
    def test_analyze_simple_project(self, tmp_path):
        """Test full analysis of simple project."""
        # Create simple project structure
        (tmp_path / "main.py").write_text('''
"""Main module."""
from utils import helper
from models.user import User

if __name__ == "__main__":
    user = User("test")
    helper()
''')

        (tmp_path / "utils.py").write_text('''
"""Utility functions."""

def helper():
    """Helper function."""
    print("Helper called")
''')

        (tmp_path / "models" / "__init__.py").mkdir(parents=True)
        (tmp_path / "models" / "user.py").write_text('''
"""User model."""

class User:
    """User class."""
    def __init__(self, name):
        self.name = name
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Verify graph structure
        assert graph.stats.total_nodes >= 4  # At least 3 files + 1 class
        assert graph.stats.total_edges >= 2  # Imports

        # Check node types
        node_types = graph.stats.node_types
        assert node_types.get("file", 0) >= 3
        assert node_types.get("class", 0) >= 1
        assert node_types.get("function", 0) >= 1

        # Verify repository info
        assert graph.repository.name == tmp_path.name

    def test_analyze_flask_mini(self):
        """Test analysis of flask_mini example."""
        flask_path = Path("examples/flask_mini")
        if not flask_path.exists():
            pytest.skip("flask_mini example not found")

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(flask_path)

        assert graph.stats.total_nodes > 0
        assert "file" in graph.stats.node_types

    def test_cli_analyze(self, tmp_path, capsys):
        """Test CLI analyze command."""
        # Create a simple Python file
        (tmp_path / "test.py").write_text("print('hello')")

        # Run CLI command
        cmd = [
            sys.executable, "-m", "codex_aura.cli.main",
            "analyze", str(tmp_path),
            "--format", "pretty"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())

        # Should succeed
        assert result.returncode == 0

        # Check output contains expected elements
        output = result.stdout
        # The pretty format should contain some output
        assert len(output.strip()) > 0

    def test_cli_analyze_json_output(self, tmp_path, capsys):
        """Test CLI analyze with JSON output."""
        (tmp_path / "test.py").write_text("print('hello')")

        cmd = [
            sys.executable, "-m", "codex_aura.cli.main",
            "analyze", str(tmp_path),
            "--format", "json"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path.cwd())

        assert result.returncode == 0
        # Should output valid JSON
        import json
        data = json.loads(result.stdout)
        assert "version" in data
        assert "nodes" in data
        assert "edges" in data


class TestRealProjects:
    """Test analysis on real open-source projects."""

    @pytest.mark.slow
    def test_analyze_requests_repo(self):
        """Test analysis of requests library."""
        # This would require cloning the repo first
        # For now, skip if not available
        requests_path = Path("/tmp/requests")  # Would need to be cloned
        if not requests_path.exists():
            pytest.skip("Requests repo not cloned")

        start_time = time.time()
        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(requests_path)
        elapsed = time.time() - start_time

        # Should complete within 2 seconds
        assert elapsed < 2.0
        assert graph.stats.total_nodes > 0

    @pytest.mark.slow
    def test_analyze_flask_repo(self):
        """Test analysis of Flask repo."""
        flask_path = Path("/tmp/flask")
        if not flask_path.exists():
            pytest.skip("Flask repo not cloned")

        start_time = time.time()
        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(flask_path)
        elapsed = time.time() - start_time

        # Should complete within 10 seconds
        assert elapsed < 10.0
        assert graph.stats.total_nodes > 0

    @pytest.mark.slow
    def test_analyze_fastapi_repo(self):
        """Test analysis of FastAPI repo."""
        fastapi_path = Path("/tmp/fastapi")
        if not fastapi_path.exists():
            pytest.skip("FastAPI repo not cloned")

        start_time = time.time()
        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(fastapi_path)
        elapsed = time.time() - start_time

        # Should complete within 5 seconds
        assert elapsed < 5.0
        assert graph.stats.total_nodes > 0