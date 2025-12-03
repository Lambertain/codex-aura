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