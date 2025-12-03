import ast
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

from ..models.edge import Edge, EdgeType
from ..models.graph import Graph, Repository, Stats
from ..models.node import Node
from .base import BaseAnalyzer
from .utils import find_python_files

logger = logging.getLogger("codex_aura")


class PythonAnalyzer(BaseAnalyzer):
    """Analyzer for Python codebases that extracts import relationships and code structure.

    This analyzer parses Python AST to extract:
    - File nodes with docstrings
    - Class definitions with inheritance and docstrings
    - Function definitions (including methods) with signatures and docstrings
    - Import relationships between files and modules
    """

    def __init__(self, verbose: bool = False):
        """Initialize the Python analyzer.

        Args:
            verbose: If True, enable verbose logging during analysis.
        """
        self.verbose = verbose

    def analyze(self, repo_path: Path) -> Graph:
        """Perform complete analysis of a Python repository.

        Analyzes all Python files in the repository, extracts code structure
        (files, classes, functions) and import relationships, then builds
        a complete dependency graph.

        Args:
            repo_path: Path to the repository root directory.

        Returns:
            A Graph object containing all analyzed nodes and edges.
        """
        logger.info(f"Starting analysis of repository: {repo_path}")

        python_files = find_python_files(repo_path)
        all_files = set(python_files)
        logger.info(f"Found {len(python_files)} Python files to analyze")

        nodes = []
        edges = []
        processed_files = 0
        skipped_files = 0

        for i, file_path in enumerate(python_files, 1):
            logger.info(f"Processing file {i}/{len(python_files)}: {file_path.name}")
            try:
                file_nodes, file_edges = self.analyze_file(file_path, repo_path, all_files)
                nodes.extend(file_nodes)
                edges.extend(file_edges)
                processed_files += 1

                if self.verbose:
                    logger.debug(
                        f"Extracted {len(file_nodes)} nodes and "
                        f"{len(file_edges)} edges from {file_path}"
                    )

            except Exception as e:
                logger.warning(f"Skipped file {file_path}: {e}")
                skipped_files += 1
                # Still create file node for skipped files
                try:
                    file_node = self._create_file_node_only(file_path, repo_path)
                    nodes.append(file_node)
                except Exception as node_e:
                    logger.error(f"Failed to create file node for {file_path}: {node_e}")

        # Check graph integrity
        valid_edges, invalid_edges = self._check_integrity(edges, nodes)
        if invalid_edges:
            logger.warning(f"Found {len(invalid_edges)} invalid edges (dangling references)")
            if self.verbose:
                for edge in invalid_edges[:5]:  # Show first 5 invalid edges
                    logger.debug(f"Invalid edge: {edge.source} -> {edge.target}")

        # Calculate stats
        node_types = {}
        for node in nodes:
            node_types[node.type] = node_types.get(node.type, 0) + 1

        stats = Stats(total_nodes=len(nodes), total_edges=len(valid_edges), node_types=node_types)

        logger.info(
            f"Analysis complete: {processed_files} files processed, {skipped_files} skipped"
        )
        logger.info(f"Graph contains {len(nodes)} nodes and {len(valid_edges)} edges")

        repository = Repository(path=str(repo_path), name=repo_path.name)

        return Graph(
            version="0.1",
            generated_at=datetime.now(),
            repository=repository,
            stats=stats,
            nodes=nodes,
            edges=valid_edges,
        )

    def _check_integrity(
        self, edges: List[Edge], nodes: List[Node]
    ) -> tuple[List[Edge], List[Edge]]:
        """Check that all edge targets exist in nodes."""
        node_ids = {node.id for node in nodes}
        valid_edges = []
        invalid_edges = []

        for edge in edges:
            if edge.target in node_ids:
                valid_edges.append(edge)
            else:
                invalid_edges.append(edge)

        return valid_edges, invalid_edges

    def _create_file_node_only(self, file_path: Path, repo_root: Path) -> Node:
        """Create a file node without parsing content."""
        relative_path = file_path.relative_to(repo_root)
        return Node(
            id=str(relative_path),
            type="file",
            name=file_path.name,
            path=str(relative_path),
            docstring=None,
        )

    def analyze_file(
        self, file_path: Path, repo_root: Path, all_files: set[Path]
    ) -> tuple[List[Node], List[Edge]]:
        """Analyze a single Python file and extract nodes and edges.

        Parses the file's AST to extract file node, class nodes, function nodes,
        and import edges. Handles various error conditions gracefully.

        Args:
            file_path: Path to the Python file to analyze.
            repo_root: Path to the repository root.
            all_files: Set of all Python files in the repository for import resolution.

        Returns:
            A tuple of (nodes, edges) where nodes contains all extracted Node objects
            and edges contains all extracted Edge objects.
        """
        try:
            # Check if file is accessible
            if not file_path.exists():
                raise FileNotFoundError(f"File does not exist: {file_path}")

            if not os.access(file_path, os.R_OK):
                raise PermissionError(f"File is not readable: {file_path}")

            # Check file size
            file_size = file_path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                logger.warning(
                    f"Large file detected ({file_size / (1024 * 1024):.1f}MB): "
                    f"{file_path}. Processing may be slow."
                )
            elif file_size == 0:
                logger.warning(f"Empty file: {file_path}")
                file_node = self._create_file_node_only(file_path, repo_root)
                return [file_node], []

            # Read file content
            try:
                with file_path.open("r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError as e:
                logger.warning(f"Encoding error in {file_path}: {e}. Skipping file.")
                file_node = self._create_file_node_only(file_path, repo_root)
                return [file_node], []

            # Parse AST
            try:
                tree = ast.parse(content, filename=str(file_path))
            except SyntaxError as e:
                logger.warning(f"Syntax error in {file_path}: {e}")
                file_node = self._create_file_node_only(file_path, repo_root)
                return [file_node], []
            except Exception as e:
                logger.warning(f"AST parsing failed for {file_path}: {e}")
                file_node = self._create_file_node_only(file_path, repo_root)
                return [file_node], []

            # Extract nodes and edges
            relative_file_path = str(file_path.relative_to(repo_root))
            file_node = parse_file_node(file_path, repo_root)
            class_nodes = extract_classes(tree, relative_file_path)
            function_nodes = extract_functions(tree, relative_file_path)
            import_edges = extract_imports(tree, file_path, repo_root, all_files)

            nodes = [file_node] + class_nodes + function_nodes
            return nodes, import_edges

        except FileNotFoundError as e:
            logger.warning(f"File not found: {e}")
            raise
        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error analyzing {file_path}: {e}")
            raise


def parse_file_node(file_path: Path, repo_root: Path) -> Node:
    """Create a file node from a Python file.

    Extracts the file's docstring by parsing its AST and creates a Node
    representing the file in the dependency graph.

    Args:
        file_path: Path to the Python file.
        repo_root: Path to the repository root for relative path calculation.

    Returns:
        A Node object representing the file.
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
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
            docstring=docstring,
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
            docstring=None,
        )
    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {e}")
        raise


def extract_classes(tree: ast.AST, relative_file_path: str) -> list[Node]:
    """Extract class definition nodes from an AST.

    Walks through the AST and creates Node objects for all class definitions,
    including their docstrings and line ranges.

    Args:
        tree: The AST to analyze.
        relative_file_path: Relative path to the file being analyzed.

    Returns:
        List of Node objects representing class definitions.
    """
    nodes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            docstring = ast.get_docstring(node)
            lines = [node.lineno]
            if hasattr(node, "end_lineno") and node.end_lineno:
                lines.append(node.end_lineno)

            class_node = Node(
                id=node.name,
                type="class",
                name=node.name,
                path=relative_file_path,
                lines=lines,
                docstring=docstring,
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
        if hasattr(node, "end_lineno") and node.end_lineno:
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
            docstring=docstring,
        )
        self.nodes.append(func_node)


def extract_functions(tree: ast.AST, relative_file_path: str) -> list[Node]:
    """Extract function and method definition nodes from an AST.

    Walks through the AST and creates Node objects for all function definitions,
    including regular functions, async functions, and class methods. Handles
    nested class hierarchies correctly.

    Args:
        tree: The AST to analyze.
        relative_file_path: Relative path to the file being analyzed.

    Returns:
        List of Node objects representing function definitions.
    """
    visitor = FunctionVisitor(relative_file_path)
    visitor.visit(tree)
    return visitor.nodes


def extract_imports(
    tree: ast.AST, file_path: Path, repo_root: Path, all_files: set[Path]
) -> list[Edge]:
    """Extract import relationship edges from an AST.

    Analyzes import statements (both 'import' and 'from ... import') and creates
    Edge objects for internal imports within the repository. Handles both
    absolute and relative imports.

    Args:
        tree: The AST to analyze.
        file_path: Path to the file being analyzed.
        repo_root: Path to the repository root.
        all_files: Set of all Python files in the repository for import resolution.

    Returns:
        List of Edge objects representing import relationships.
    """
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
                            line=node.lineno,
                        )
                        edges.append(edge)
                    else:
                        logger.warning(f"Could not resolve import: {module_name} in {file_path}")

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module
                # Handle relative imports
                if node.level > 0:
                    module_name = _resolve_relative_import(
                        node.level, module_name, file_path, repo_root
                    )

                if module_name and _is_internal_import(module_name, repo_root, all_files, file_dir):
                    target_path = _resolve_import_path(module_name, repo_root, all_files, file_dir)
                    if target_path:
                        edge = Edge(
                            source=str(relative_path),
                            target=str(target_path),
                            type=EdgeType.IMPORTS,
                            line=node.lineno,
                        )
                        edges.append(edge)
                    else:
                        logger.warning(f"Could not resolve import: {module_name} in {file_path}")

    return edges


def _is_internal_import(
    module_name: str, repo_root: Path, all_files: set[Path], file_dir: Path
) -> bool:
    """Check if import is internal to the repository."""
    # Simple check: if we can resolve it to a file in all_files
    return _resolve_import_path(module_name, repo_root, all_files, file_dir) is not None


def _resolve_import_path(
    module_name: str, repo_root: Path, all_files: set[Path], file_dir: Path
) -> Path | None:
    """Resolve module name to file path."""
    # Convert module name to path
    module_path = module_name.replace(".", "/")

    # Try relative to file directory first (for simple cases)
    possible_paths = [
        file_dir / f"{module_path}.py",
        file_dir / module_path / "__init__.py",
        repo_root / f"{module_path}.py",
        repo_root / module_path / "__init__.py",
    ]

    for path in possible_paths:
        if path in all_files:
            return path.relative_to(repo_root)
    return None


def _resolve_relative_import(
    level: int, module_name: str, file_path: Path, repo_root: Path
) -> str | None:
    """Resolve relative import to absolute module name."""
    current_dir = file_path.parent
    for _ in range(level - 1):
        current_dir = current_dir.parent

    if module_name:
        return (
            str((current_dir / module_name).relative_to(repo_root))
            .replace("/", ".")
            .replace("\\", ".")
        )
    else:
        return str(current_dir.relative_to(repo_root)).replace("/", ".").replace("\\", ".")
