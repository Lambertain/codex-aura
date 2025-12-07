"""Tests for the impact analysis engine."""

import pytest
from pathlib import Path

from codex_aura.impact_engine import ImpactEngine, DependencyAnalyzer


class TestDependencyAnalyzer:
    def test_get_dependencies_imports(self, tmp_path):
        """Test analyzing import dependencies."""
        # Create test file
        file_path = tmp_path / "main.py"
        file_path.write_text("""
import os
from pathlib import Path
from utils.helper import func
""")

        analyzer = DependencyAnalyzer(str(tmp_path))
        deps = analyzer.get_dependencies("main.py")

        assert "os" in deps['imports']
        assert "pathlib" in deps['imports']
        assert "utils" in deps['imports']

    def test_get_dependencies_calls(self, tmp_path):
        """Test analyzing function call dependencies."""
        file_path = tmp_path / "main.py"
        file_path.write_text("""
def main():
    helper()
    obj.method()
    print("hello")
""")

        analyzer = DependencyAnalyzer(str(tmp_path))
        deps = analyzer.get_dependencies("main.py")

        assert "helper" in deps['calls']
        assert "method" in deps['calls']
        assert "print" in deps['calls']

    def test_get_dependencies_extends(self, tmp_path):
        """Test analyzing class inheritance dependencies."""
        file_path = tmp_path / "models.py"
        file_path.write_text("""
class Base:
    pass

class User(Base):
    pass

class Admin(User):
    pass
""")

        analyzer = DependencyAnalyzer(str(tmp_path))
        deps = analyzer.get_dependencies("models.py")

        assert "Base" in deps['extends']
        assert "User" in deps['extends']

    def test_get_definitions(self, tmp_path):
        """Test analyzing definitions in a file."""
        file_path = tmp_path / "utils.py"
        file_path.write_text("""
def helper():
    pass

class Service:
    pass

async def async_func():
    pass
""")

        analyzer = DependencyAnalyzer(str(tmp_path))
        defs = analyzer.get_definitions("utils.py")

        assert "helper" in defs['functions']
        assert "async_func" in defs['functions']
        assert "Service" in defs['classes']


class TestImpactEngine:
    def test_predict_no_dependencies(self, tmp_path):
        """Test prediction when file has no dependencies."""
        file_path = tmp_path / "isolated.py"
        file_path.write_text("print('isolated')")

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("isolated.py", "test-repo")

        assert impacted == []

    def test_predict_import_impact(self, tmp_path):
        """Test prediction based on import dependencies."""
        # Create module file
        (tmp_path / "utils.py").write_text("def helper(): pass")

        # Create file that imports it
        (tmp_path / "main.py").write_text("from utils import helper")

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("utils.py", "test-repo")

        assert "main.py" in impacted

    def test_predict_call_impact(self, tmp_path):
        """Test prediction based on function call dependencies."""
        # Create file with function definition
        (tmp_path / "utils.py").write_text("def helper(): pass")

        # Create file that calls it
        (tmp_path / "main.py").write_text("helper()")

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("utils.py", "test-repo")

        assert "main.py" in impacted

    def test_predict_inheritance_impact(self, tmp_path):
        """Test prediction based on class inheritance dependencies."""
        # Create base class file
        (tmp_path / "base.py").write_text("class Base: pass")

        # Create file that extends it
        (tmp_path / "models.py").write_text("class User(Base): pass")

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("base.py", "test-repo")

        assert "models.py" in impacted

    def test_predict_depth_limit(self, tmp_path):
        """Test that depth limit is respected."""
        # Create chain: a.py -> b.py -> c.py -> d.py
        (tmp_path / "a.py").write_text("def func_a(): pass")
        (tmp_path / "b.py").write_text("func_a()")
        (tmp_path / "c.py").write_text("func_b()")  # This won't be reached due to depth limit
        (tmp_path / "d.py").write_text("func_c()")  # This definitely won't be reached

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("a.py", "test-repo")

        # Should include b.py but not c.py or d.py due to depth limit
        assert "b.py" in impacted
        assert "c.py" not in impacted
        assert "d.py" not in impacted

    def test_predict_sorted_output(self, tmp_path):
        """Test that output is sorted."""
        # Create multiple dependent files
        (tmp_path / "utils.py").write_text("def helper(): pass")
        (tmp_path / "z.py").write_text("helper()")
        (tmp_path / "a.py").write_text("helper()")

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("utils.py", "test-repo")

        # Should be sorted alphabetically
        assert impacted == ["a.py", "z.py"]

    def test_predict_excludes_original_file(self, tmp_path):
        """Test that original file is not included in impacted files."""
        file_path = tmp_path / "main.py"
        file_path.write_text("print('self')")

        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("main.py", "test-repo")

        assert "main.py" not in impacted

    def test_predict_nonexistent_file(self, tmp_path):
        """Test prediction for nonexistent file."""
        engine = ImpactEngine(str(tmp_path))
        impacted = engine.predict("nonexistent.py", "test-repo")

        assert impacted == []