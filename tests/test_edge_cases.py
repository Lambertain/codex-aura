import pytest
from pathlib import Path

from codex_aura.analyzer.python import PythonAnalyzer


class TestEdgeCases:
    def test_empty_repository(self, tmp_path):
        """Test analysis of empty repository."""
        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should handle gracefully
        assert graph.stats.total_nodes == 0
        assert graph.stats.total_edges == 0

    def test_single_file_no_imports(self, tmp_path):
        """Test single file without any imports."""
        (tmp_path / "standalone.py").write_text('''
"""Standalone module."""

def main():
    """Main function."""
    print("Hello, World!")

class Config:
    """Configuration class."""
    DEBUG = True

if __name__ == "__main__":
    main()
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 3  # file + function + class
        assert graph.stats.total_edges == 0  # No imports

    def test_circular_imports(self, tmp_path):
        """Test handling of circular imports."""
        (tmp_path / "a.py").write_text("from b import func_b\ndef func_a(): pass")
        (tmp_path / "b.py").write_text("from a import func_a\ndef func_b(): pass")

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should handle circular imports gracefully
        assert graph.stats.total_nodes >= 2  # Both files
        # Edges might be created for both directions, but integrity check should handle it

    def test_file_with_only_comments(self, tmp_path):
        """Test file containing only comments."""
        (tmp_path / "comments.py").write_text('''
# This is a comment
# Another comment
"""
This is a docstring but no code.
"""
# More comments
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 1  # At least the file node
        assert graph.stats.total_edges == 0

    def test_file_with_encoding_declaration(self, tmp_path):
        """Test file with encoding declaration."""
        content = '''# -*- coding: utf-8 -*-
"""Module with encoding declaration."""

def func():
    """Function with unicode."""
    pass
'''
        (tmp_path / "encoded.py").write_text(content, encoding='utf-8')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 2  # file + function

    def test_large_file(self, tmp_path):
        """Test file larger than 10KB."""
        functions = []
        for i in range(1000):
            functions.extend([
                f'def func_{i}():',
                f'    """Function {i}."""',
                f'    return {i}',
                ''
            ])
        large_content = '"""Large file."""\n' + '\n'.join(functions)

        (tmp_path / "large.py").write_text(large_content)

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should still process the file
        assert graph.stats.total_nodes >= 1  # At least file node
        # Large files should be processed but might generate warnings

    def test_file_with_syntax_errors(self, tmp_path):
        """Test file with syntax errors."""
        (tmp_path / "broken.py").write_text('''
def broken_function(
    """Broken syntax."""
    pass
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should create file node but no other nodes
        assert graph.stats.total_nodes >= 1
        file_nodes = [n for n in graph.nodes if n.type == "file"]
        assert len(file_nodes) == 1
        assert file_nodes[0].name == "broken.py"

    def test_empty_file(self, tmp_path):
        """Test empty Python file."""
        (tmp_path / "empty.py").touch()  # Create empty file

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 1  # File node
        assert graph.stats.total_edges == 0

    def test_file_with_only_pass(self, tmp_path):
        """Test file with only 'pass' statement."""
        (tmp_path / "pass_only.py").write_text("pass")

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 1  # File node
        assert graph.stats.total_edges == 0

    def test_nested_directory_structure(self, tmp_path):
        """Test deeply nested directory structure."""
        # Create nested structure
        deep_path = tmp_path / "a" / "b" / "c" / "d"
        deep_path.mkdir(parents=True)

        (deep_path / "__init__.py").write_text("")
        (deep_path / "deep_module.py").write_text("def deep_func(): pass")

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 2  # Both files
        # Should handle deep nesting correctly

    def test_mixed_file_types(self, tmp_path):
        """Test repository with mixed file types."""
        (tmp_path / "script.py").write_text("print('script')")
        (tmp_path / "module.py").write_text("def func(): pass")
        (tmp_path / "data.json").write_text('{"key": "value"}')
        (tmp_path / "README.md").write_text("# README")

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should only process Python files
        python_files = [n for n in graph.nodes if n.type == "file"]
        assert len(python_files) == 2  # Only .py files

    def test_unicode_in_code(self, tmp_path):
        """Test file with unicode characters in code."""
        (tmp_path / "unicode.py").write_text('''# -*- coding: utf-8 -*-
"""Модуль с юникодом."""

def приветствие():
    """Функция приветствия."""
    return "Привет мир! 你好世界 🌍"

class Données:
    """Classe avec caractères spéciaux."""
    pass
''', encoding='utf-8')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 3  # file + function + class

    def test_very_long_lines(self, tmp_path):
        """Test file with very long lines."""
        long_string = "x" * 10000
        (tmp_path / "longlines.py").write_text(f'''
def long_func():
    """Function with very long string."""
    return "{long_string}"
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 2  # file + function

    def test_self_import(self, tmp_path):
        """Test file that imports itself (edge case)."""
        (tmp_path / "self_import.py").write_text('''
import self_import

def func():
    pass
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should handle self-import gracefully
        assert graph.stats.total_nodes >= 1

    def test_star_imports(self, tmp_path):
        """Test star imports (from module import *)."""
        (tmp_path / "base.py").write_text('''
def func1(): pass
def func2(): pass
__all__ = ["func1", "func2"]
''')
        (tmp_path / "consumer.py").write_text('''
from base import *

def use_all():
    func1()
    func2()
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should create import edge even with star import
        assert graph.stats.total_edges >= 1

    def test_relative_imports_various_levels(self, tmp_path):
        """Test various levels of relative imports."""
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")

        sub = pkg / "sub"
        sub.mkdir()
        (sub / "__init__.py").write_text("")

        (pkg / "base.py").write_text("BASE = 1")
        (sub / "module.py").write_text('''
from .. import base
from ..base import BASE
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should resolve relative imports
        assert graph.stats.total_nodes >= 3

    def test_conditional_imports(self, tmp_path):
        """Test conditional imports."""
        (tmp_path / "conditional.py").write_text('''
import sys

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

def func() -> "Self":
    pass
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should handle conditional imports
        assert graph.stats.total_nodes >= 2

    def test_try_except_imports(self, tmp_path):
        """Test imports inside try/except blocks."""
        (tmp_path / "try_import.py").write_text('''
try:
    import optional_module
except ImportError:
    optional_module = None

def func():
    if optional_module:
        return optional_module.something()
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 2

    def test_async_code(self, tmp_path):
        """Test async functions and classes."""
        (tmp_path / "async_module.py").write_text('''
"""Async module."""
import asyncio

async def async_func():
    """Async function."""
    await asyncio.sleep(1)
    return True

class AsyncClass:
    async def async_method(self):
        """Async method."""
        await asyncio.sleep(0)
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should detect async functions
        func_nodes = [n for n in graph.nodes if n.type == "function"]
        assert len(func_nodes) >= 2

    def test_decorators(self, tmp_path):
        """Test functions and classes with decorators."""
        (tmp_path / "decorated.py").write_text('''
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_func(x):
    """Cached function."""
    return x * 2

@staticmethod
def static_func():
    pass

class MyClass:
    @property
    def my_prop(self):
        return self._value

    @classmethod
    def from_string(cls, s):
        return cls()
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        # Should detect decorated functions
        assert graph.stats.total_nodes >= 4

    def test_dataclass(self, tmp_path):
        """Test dataclass parsing."""
        (tmp_path / "dataclasses_module.py").write_text('''
from dataclasses import dataclass, field

@dataclass
class Person:
    """Person dataclass."""
    name: str
    age: int = 0
    tags: list = field(default_factory=list)

    def greet(self):
        return f"Hello, {self.name}"
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        class_nodes = [n for n in graph.nodes if n.type == "class"]
        assert len(class_nodes) >= 1

    def test_type_hints_complex(self, tmp_path):
        """Test complex type hints."""
        (tmp_path / "typed.py").write_text('''
from typing import Dict, List, Optional, Union, Callable, TypeVar

T = TypeVar("T")

def complex_func(
    items: List[Dict[str, Union[int, str]]],
    callback: Optional[Callable[[T], T]] = None
) -> Dict[str, List[int]]:
    """Function with complex type hints."""
    return {}
''')

        analyzer = PythonAnalyzer()
        graph = analyzer.analyze(tmp_path)

        assert graph.stats.total_nodes >= 2