import ast
import pytest
from pathlib import Path
from unittest.mock import patch

from codex_aura.analyzer.python import (
    PythonAnalyzer, parse_file_node, extract_classes, extract_functions,
    extract_imports, find_python_files
)
from codex_aura.analyzer.utils import find_python_files as utils_find_python_files
from codex_aura.models.node import Node
from codex_aura.models.edge import Edge, EdgeType


class TestFindPythonFiles:
    def test_find_python_files(self, tmp_path):
        """Test finding Python files in directory."""
        # Create test files
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "utils.py").write_text("def helper(): pass")
        (tmp_path / "data.txt").write_text("not python")

        # Create subdirectory with Python file
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "module.py").write_text("class Test: pass")

        # Create ignored directory
        ignored = tmp_path / "__pycache__"
        ignored.mkdir()
        (ignored / "cache.py").write_text("cached")

        files = utils_find_python_files(tmp_path)
        file_names = {f.name for f in files}

        assert "main.py" in file_names
        assert "utils.py" in file_names
        assert "module.py" in file_names
        assert "cache.py" not in file_names  # Should be ignored
        assert len(files) == 3


class TestParseFileNode:
    def test_parse_simple_file(self, tmp_path):
        """Test parsing a simple Python file."""
        file_path = tmp_path / "simple.py"
        file_path.write_text('"""A simple module."""\nprint("hello")')

        node = parse_file_node(file_path, tmp_path)

        assert node.id == "simple.py"
        assert node.type == "file"
        assert node.name == "simple.py"
        assert node.path == "simple.py"
        assert node.docstring == "A simple module."

    def test_parse_file_without_docstring(self, tmp_path):
        """Test parsing file without docstring."""
        file_path = tmp_path / "no_doc.py"
        file_path.write_text("print('no docstring')")

        node = parse_file_node(file_path, tmp_path)
        assert node.docstring is None


class TestExtractClasses:
    def test_extract_classes(self):
        """Test extracting class nodes from AST."""
        code = '''
class User:
    """User model."""
    pass

class Admin(User):
    pass
'''
        tree = ast.parse(code)
        nodes = extract_classes(tree, "models/user.py")

        assert len(nodes) == 2
        user_class = next(n for n in nodes if n.name == "User")
        assert user_class.id == "User"
        assert user_class.type == "class"
        assert user_class.path == "models/user.py"
        assert user_class.docstring == "User model."
        assert user_class.lines == [2, 4]  # Approximate line numbers

    def test_extract_classes_no_docstring(self):
        """Test extracting classes without docstrings."""
        code = "class Simple: pass"
        tree = ast.parse(code)
        nodes = extract_classes(tree, "simple.py")

        assert len(nodes) == 1
        assert nodes[0].docstring is None


class TestExtractFunctions:
    def test_extract_functions(self):
        """Test extracting function nodes."""
        code = '''
def helper():
    """Helper function."""
    pass

class MyClass:
    def method(self):
        """Instance method."""
        pass

    @staticmethod
    def static_method():
        pass
'''
        tree = ast.parse(code)
        nodes = extract_functions(tree, "utils.py")

        assert len(nodes) == 3
        helper_func = next(n for n in nodes if n.name == "helper")
        assert helper_func.id == "helper"
        assert helper_func.docstring == "Helper function."

        method = next(n for n in nodes if n.name == "method")
        assert method.id == "MyClass::method"

    def test_extract_async_functions(self):
        """Test extracting async functions."""
        code = "async def async_func(): pass"
        tree = ast.parse(code)
        nodes = extract_functions(tree, "async.py")

        assert len(nodes) == 1
        assert nodes[0].name == "async_func"


class TestExtractImports:
    def test_extract_imports(self, tmp_path):
        """Test extracting import edges."""
        # Create test files
        (tmp_path / "utils.py").write_text("def func(): pass")
        (tmp_path / "models" / "__init__.py").mkdir(parents=True)
        (tmp_path / "models" / "user.py").write_text("class User: pass")

        code = '''
import utils
from models.user import User
from pathlib import Path  # External import, should be ignored
'''
        tree = ast.parse(code)
        file_path = tmp_path / "main.py"
        file_path.write_text(code)

        edges = extract_imports(tree, file_path, tmp_path, {tmp_path / "utils.py", tmp_path / "models/user.py"})

        assert len(edges) == 2
        utils_edge = next(e for e in edges if "utils" in e.target)
        assert utils_edge.source == "main.py"
        assert utils_edge.type == EdgeType.IMPORTS

    def test_extract_relative_imports(self, tmp_path):
        """Test extracting relative imports."""
        # Create directory structure
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "utils.py").write_text("def func(): pass")
        (tmp_path / "pkg" / "subpkg").mkdir()
        (tmp_path / "pkg" / "subpkg" / "__init__.py").write_text("")
        (tmp_path / "pkg" / "subpkg" / "main.py").write_text("from ..utils import func")

        code = "from ..utils import func"
        tree = ast.parse(code)
        file_path = tmp_path / "pkg" / "subpkg" / "main.py"

        edges = extract_imports(tree, file_path, tmp_path, {tmp_path / "pkg/utils.py"})

        assert len(edges) == 1
        assert edges[0].target == str(Path("pkg/utils.py"))


class TestSyntaxErrorHandling:
    def test_syntax_error_handling(self, tmp_path):
        """Test handling of syntax errors."""
        file_path = tmp_path / "broken.py"
        file_path.write_text("def broken syntax(")

        analyzer = PythonAnalyzer()
        nodes, edges = analyzer.analyze_file(file_path, tmp_path, set())

        # Should still create file node even with syntax error
        assert len(nodes) == 1
        assert nodes[0].type == "file"
        assert nodes[0].name == "broken.py"
        assert len(edges) == 0

    def test_encoding_error_handling(self, tmp_path):
        """Test handling of encoding errors."""
        file_path = tmp_path / "encoded.py"
        # Write some bytes that might cause encoding issues
        file_path.write_bytes(b'\xff\xfe\x00\x00def func(): pass')

        analyzer = PythonAnalyzer()
        nodes, edges = analyzer.analyze_file(file_path, tmp_path, set())

        # Should create file node despite encoding error
        assert len(nodes) == 1
        assert nodes[0].type == "file"