import ast
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from ..models.edge import Edge, EdgeType
from ..models.graph import Graph, Repository, Stats
from ..models.node import Node
from .base import BaseAnalyzer
from .utils import find_python_files

logger = logging.getLogger(__name__)


class PythonAnalyzer(BaseAnalyzer):
    def analyze(self, repo_path: Path) -> Graph:
        """Analyze Python repository and return graph."""
        nodes = []
        edges = []

        python_files = find_python_files(repo_path)
        all_files = set(python_files)
        for file_path in python_files:
            try:
                file_nodes, file_edges = self.analyze_file(file_path, repo_path, all_files)
                nodes.extend(file_nodes)
                edges.extend(file_edges)
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")

        # Calculate stats
        node_types = {}
        for node in nodes:
            node_types[node.type] = node_types.get(node.type, 0) + 1

        stats = Stats(
            total_nodes=len(nodes),
            total_edges=len(edges),
            node_types=node_types
        )

        repository = Repository(
            path=str(repo_path),
            name=repo_path.name
        )

        return Graph(
            version="0.1",
            generated_at=datetime.now(),
            repository=repository,
            stats=stats,
            nodes=nodes,
            edges=edges
        )

    def analyze_file(self, file_path: Path, repo_root: Path, all_files: set[Path]) -> tuple[List[Node], List[Edge]]:
        """Analyze single Python file and return nodes and edges."""
        try:
            with file_path.open('r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))

            relative_file_path = str(file_path.relative_to(repo_root))
            file_node = parse_file_node(file_path, repo_root)
            class_nodes = extract_classes(tree, relative_file_path)
            function_nodes = extract_functions(tree, relative_file_path)
            import_edges = extract_imports(tree, file_path, repo_root, all_files)

            nodes = [file_node] + class_nodes + function_nodes
            return nodes, import_edges
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            # Still create file node
            file_node = parse_file_node(file_path, repo_root)
            return [file_node], []
        except Exception as e:
            logger.error(f"Failed to parse {file_path}: {e}")
            raise


def parse_file_node(file_path: Path, repo_root: Path) -> Node:
    """Create file node from Python file."""
    try:
        with file_path.open('r', encoding='utf-8') as f:
            content = f.read()

        # Parse AST to extract docstring
        tree = ast.parse(content, filename=str(file_path))
        docstring = ast.get_docstring(tree)

        # Calculate relative path
        relative_path = file_path.relative_to(repo_root)

        return Node(
            id=str(relative_path),
            type="file",
            name=file_path.name,
            path=str(relative_path),
            docstring=docstring
        )
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        # Still create node but without docstring
        relative_path = file_path.relative_to(repo_root)
        return Node(
            id=str(relative_path),
            type="file",
            name=file_path.name,
            path=str(relative_path),
            docstring=None
        )
    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {e}")
        raise


def extract_classes(tree: ast.AST, relative_file_path: str) -> list[Node]:
    """Extract class nodes from AST."""
    nodes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            lines = [node.lineno]
            if hasattr(node, 'end_lineno') and node.end_lineno:
                lines.append(node.end_lineno)

            class_node = Node(
                id=node.name,
                type="class",
                name=node.name,
                path=relative_file_path,
                lines=lines,
                docstring=docstring
            )
            nodes.append(class_node)

    return nodes


class FunctionVisitor(ast.NodeVisitor):
    def __init__(self, relative_file_path: str):
        self.relative_file_path = relative_file_path
        self.nodes = []
        self.class_stack = []

    def visit_ClassDef(self, node):
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node):
        self._add_function(node)

    def visit_AsyncFunctionDef(self, node):
        self._add_function(node)

    def _add_function(self, node):
        docstring = ast.get_docstring(node)
        lines = [node.lineno]
        if hasattr(node, 'end_lineno') and node.end_lineno:
            lines.append(node.end_lineno)

        if self.class_stack:
            func_id = f"{self.class_stack[-1]}::{node.name}"
        else:
            func_id = node.name

        func_node = Node(
            id=func_id,
            type="function",
            name=node.name,
            path=self.relative_file_path,
            lines=lines,
            docstring=docstring
        )
        self.nodes.append(func_node)


def extract_functions(tree: ast.AST, relative_file_path: str) -> list[Node]:
    """Extract function nodes from AST."""
    visitor = FunctionVisitor(relative_file_path)
    visitor.visit(tree)
    return visitor.nodes


def extract_imports(
    tree: ast.AST,
    file_path: Path,
    repo_root: Path,
    all_files: set[Path]
) -> list[Edge]:
    """Extract import edges from AST."""
    edges = []
    relative_path = file_path.relative_to(repo_root)
    file_dir = file_path.parent

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                # Skip standard library and external packages
                if _is_internal_import(module_name, repo_root, all_files, file_dir):
                    target_path = _resolve_import_path(module_name, repo_root, all_files, file_dir)
                    if target_path:
                        edge = Edge(
                            source=str(relative_path),
                            target=str(target_path),
                            type=EdgeType.IMPORTS,
                            line=node.lineno
                        )
                        edges.append(edge)
                    else:
                        logger.warning(f"Could not resolve import: {module_name} in {file_path}")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module
                # Handle relative imports
                if node.level > 0:
                    module_name = _resolve_relative_import(node.level, module_name, file_path, repo_root)

                if module_name and _is_internal_import(module_name, repo_root, all_files, file_dir):
                    target_path = _resolve_import_path(module_name, repo_root, all_files, file_dir)
                    if target_path:
                        edge = Edge(
                            source=str(relative_path),
                            target=str(target_path),
                            type=EdgeType.IMPORTS,
                            line=node.lineno
                        )
                        edges.append(edge)
                    else:
                        logger.warning(f"Could not resolve import: {module_name} in {file_path}")

    return edges


def _is_internal_import(module_name: str, repo_root: Path, all_files: set[Path], file_dir: Path) -> bool:
    """Check if import is internal to the repository."""
    # Simple check: if we can resolve it to a file in all_files
    return _resolve_import_path(module_name, repo_root, all_files, file_dir) is not None


def _resolve_import_path(module_name: str, repo_root: Path, all_files: set[Path], file_dir: Path) -> Path | None:
    """Resolve module name to file path."""
    # Convert module name to path
    module_path = module_name.replace('.', '/')

    # Try relative to file directory first (for simple cases)
    possible_paths = [
        file_dir / f"{module_path}.py",
        file_dir / module_path / "__init__.py",
        repo_root / f"{module_path}.py",
        repo_root / module_path / "__init__.py"
    ]

    for path in possible_paths:
        if path in all_files:
            return path.relative_to(repo_root)
    return None


def _resolve_relative_import(level: int, module_name: str, file_path: Path, repo_root: Path) -> str | None:
    """Resolve relative import to absolute module name."""
    current_dir = file_path.parent
    for _ in range(level - 1):
        current_dir = current_dir.parent

    if module_name:
        return str((current_dir / module_name).relative_to(repo_root)).replace('/', '.').replace('\\', '.')
    else:
        return str(current_dir.relative_to(repo_root)).replace('/', '.').replace('\\', '.')