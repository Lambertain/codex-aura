import ast
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List

from ..models.edge import Edge, EdgeType
from ..models.git import ChangedFiles
from ..models.graph import Graph, Repository, Stats, remove_nodes_by_path, replace_nodes_for_path, rebuild_edges_for_paths
from ..models.node import Node
from .base import BaseAnalyzer, Reference
from .utils import find_python_files, get_changed_files, get_current_sha, get_file_blame, load_ignore_patterns

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

        # Load ignore patterns
        ignore_patterns = load_ignore_patterns(repo_path)
        python_files = find_python_files(repo_path, ignore_patterns)
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

        # Calculate complexity metrics
        avg_complexity, hot_spots_count = self._calculate_complexity_metrics(nodes, valid_edges)

        stats = Stats(
            total_nodes=len(nodes),
            total_edges=len(valid_edges),
            node_types=node_types,
            average_complexity=avg_complexity,
            hot_spots_count=hot_spots_count
        )

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
            sha=get_current_sha(repo_path) or "",
        )

    def update_graph_incremental(
        self, graph: Graph, repo_path: Path, from_sha: str
    ) -> Graph:
        """Update graph incrementally based on changes since a specific commit.

        Performs incremental analysis by:
        1. Getting changed files between from_sha and current HEAD
        2. Removing nodes for deleted files
        3. Re-analyzing modified and added files
        4. Rebuilding edges for affected files
        5. Updating the graph's SHA to current HEAD

        Args:
            graph: The existing Graph object to update.
            repo_path: Path to the repository root.
            from_sha: Commit SHA to compare against for changes.

        Returns:
            Updated Graph object with incremental changes applied.
        """
        logger.info(f"Starting incremental update from SHA {from_sha}")

        # Get changed files
        changes = get_changed_files(repo_path, from_sha)
        if not changes:
            logger.warning("Could not determine changed files, falling back to full analysis")
            return self.analyze(repo_path)

        logger.info(f"Found changes: +{len(changes.added)} added, ~{len(changes.modified)} modified, -{len(changes.deleted)} deleted")

        # Load ignore patterns
        ignore_patterns = load_ignore_patterns(repo_path)
        python_files = find_python_files(repo_path, ignore_patterns)
        all_files = set(python_files)

        updated_graph = graph

        # Remove deleted nodes and their edges
        for path in changes.deleted:
            logger.debug(f"Removing nodes for deleted file: {path}")
            updated_graph = remove_nodes_by_path(updated_graph, path)

        # Re-analyze modified and added files
        affected_paths = changes.added + changes.modified
        for path in affected_paths:
            file_path = repo_path / path
            if file_path.exists() and file_path in all_files:
                logger.debug(f"Re-analyzing file: {path}")
                try:
                    file_nodes, file_edges = self.analyze_file(file_path, repo_path, all_files)
                    updated_graph = replace_nodes_for_path(updated_graph, path, file_nodes)
                    # Note: In a full implementation, we'd also need to add the new edges
                    # For now, we'll rebuild all edges at the end
                except Exception as e:
                    logger.warning(f"Failed to re-analyze {file_path}: {e}")

        # Rebuild edges for affected nodes
        updated_graph = rebuild_edges_for_paths(updated_graph, affected_paths)

        # Update SHA to current HEAD
        current_sha = get_current_sha(repo_path)
        if current_sha:
            # Create new graph with updated SHA
            updated_graph = Graph(
                version=updated_graph.version,
                generated_at=datetime.now(),  # Update timestamp
                repository=updated_graph.repository,
                stats=updated_graph.stats,
                nodes=updated_graph.nodes,
                edges=updated_graph.edges,
                sha=current_sha
            )

        logger.info(f"Incremental update complete. New SHA: {current_sha}")
        return updated_graph

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

    def _calculate_complexity_metrics(self, nodes: List[Node], edges: List[Edge]) -> tuple[float, int]:
        """Calculate average complexity and hot spots count.

        Args:
            nodes: List of nodes in the graph
            edges: List of edges in the graph

        Returns:
            Tuple of (average_complexity, hot_spots_count)
        """
        if not nodes:
            return 0.0, 0

        # Calculate complexity for each node (simplified: based on lines of code)
        complexities = []
        for node in nodes:
            if node.type in ('function', 'class') and node.lines:
                # Calculate lines of code as a simple complexity metric
                if len(node.lines) >= 2:
                    loc = node.lines[1] - node.lines[0] + 1
                    complexities.append(loc)
                else:
                    complexities.append(1)  # Minimum complexity
            else:
                complexities.append(1)  # Default for files and other types

        avg_complexity = sum(complexities) / len(complexities) if complexities else 0.0

        # Calculate hot spots: nodes with high connectivity
        # Build connectivity map
        connectivity = {}
        for edge in edges:
            connectivity[edge.source] = connectivity.get(edge.source, 0) + 1
            connectivity[edge.target] = connectivity.get(edge.target, 0) + 1

        # Consider nodes with connectivity > average as hot spots
        if connectivity:
            avg_connectivity = sum(connectivity.values()) / len(connectivity)
            hot_spots_count = sum(1 for conn in connectivity.values() if conn > avg_connectivity * 1.5)
        else:
            hot_spots_count = 0

        return round(avg_complexity, 2), hot_spots_count

    def _create_file_node_only(self, file_path: Path, repo_root: Path) -> Node:
        """Create a file node without parsing content."""
        relative_path = file_path.relative_to(repo_root)
        blame_info = get_file_blame(file_path, repo_root)
        return Node(
            id=str(relative_path),
            type="file",
            name=file_path.name,
            path=str(relative_path),
            docstring=None,
            blame=blame_info,
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
            call_edges = extract_calls(tree, relative_file_path)
            extend_edges = extract_extends(tree, relative_file_path)

            nodes = [file_node] + class_nodes + function_nodes
            edges = import_edges + call_edges + extend_edges
            return nodes, edges

        except FileNotFoundError as e:
            logger.warning(f"File not found: {e}")
            raise
        except PermissionError as e:
            logger.warning(f"Permission denied: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error analyzing {file_path}: {e}")
            raise

    def resolve_references(self, node: Node) -> List[Reference]:
        """Resolve references from a node to other nodes.

        For file nodes, this analyzes imports and calls.
        For function/class nodes, this analyzes their internal references.

        Args:
            node: The node to resolve references for.

        Returns:
            List of Reference objects representing relationships.
        """
        references = []

        # For file nodes, we need to re-analyze the file
        if node.type == "file":
            file_path = Path(node.path)
            if file_path.exists():
                try:
                    # Re-analyze the file to get edges
                    _, edges = self.analyze_file(file_path, file_path.parent, {file_path})
                    for edge in edges:
                        references.append(Reference(
                            target_fqn=edge.target,
                            edge_type=edge.type
                        ))
                except Exception as e:
                    logger.warning(f"Failed to resolve references for {node.path}: {e}")

        # For function/class nodes, we could analyze their content
        # For now, return empty list as this would require more complex analysis
        # of the node's source code to find internal references

        return references


def parse_file_node(file_path: Path, repo_root: Path) -> Node:
    """Create a file node from a Python file.

    Extracts the file's docstring by parsing its AST and creates a Node
    representing the file in the dependency graph. Also includes git blame info.

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

        # Get git blame information
        blame_info = get_file_blame(file_path, repo_root)

        return Node(
            id=str(relative_path),
            type="file",
            name=file_path.name,
            path=str(relative_path),
            docstring=docstring,
            blame=blame_info,
        )
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        # Still create node but without docstring
        relative_path = file_path.relative_to(repo_root)
        blame_info = get_file_blame(file_path, repo_root)
        return Node(
            id=str(relative_path),
            type="file",
            name=file_path.name,
            path=str(relative_path),
            docstring=None,
            blame=blame_info,
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


def extract_calls(tree: ast.AST, relative_file_path: str) -> list[Edge]:
    """Extract function call relationship edges from an AST.

    Analyzes function calls and creates Edge objects for CALLS relationships
    between calling functions/methods and called functions.

    Args:
        tree: The AST to analyze.
        relative_file_path: Relative path to the file being analyzed.

    Returns:
        List of Edge objects representing function call relationships.
    """
    edges = []
    function_stack = []

    class CallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.edges = []
            self.function_stack = []
            self.class_stack = []

        def visit_ClassDef(self, node):
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

        def visit_FunctionDef(self, node):
            func_name = f"{self.class_stack[-1]}::{node.name}" if self.class_stack else node.name
            self.function_stack.append(func_name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_AsyncFunctionDef(self, node):
            func_name = f"{self.class_stack[-1]}::{node.name}" if self.class_stack else node.name
            self.function_stack.append(func_name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_Call(self, node):
            if self.function_stack:
                caller = self.function_stack[-1]
                called_func = _extract_call_target(node)
                if called_func:
                    edge = Edge(
                        source=caller,
                        target=called_func,
                        type=EdgeType.CALLS,
                        line=node.lineno,
                    )
                    self.edges.append(edge)

    visitor = CallVisitor()
    visitor.visit(tree)
    return visitor.edges


def _extract_call_target(call_node: ast.Call) -> str | None:
    """Extract the target function name from a Call node."""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    elif isinstance(call_node.func, ast.Attribute):
        # Handle method calls like obj.method() or module.func()
        parts = []
        current = call_node.func
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
        return ".".join(parts)
    return None


def extract_extends(tree: ast.AST, relative_file_path: str) -> list[Edge]:
    """Extract class inheritance relationship edges from an AST.

    Analyzes class definitions and creates Edge objects for EXTENDS relationships
    between child classes and their parent classes.

    Args:
        tree: The AST to analyze.
        relative_file_path: Relative path to the file being analyzed.

    Returns:
        List of Edge objects representing inheritance relationships.
    """
    edges = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                parent_class = _extract_base_class_name(base)
                if parent_class:
                    edge = Edge(
                        source=node.name,
                        target=parent_class,
                        type=EdgeType.EXTENDS,
                        line=node.lineno,
                    )
                    edges.append(edge)

    return edges


def _extract_base_class_name(base_node: ast.expr) -> str | None:
    """Extract the class name from a base class expression."""
    if isinstance(base_node, ast.Name):
        return base_node.id
    elif isinstance(base_node, ast.Attribute):
        # Handle qualified names like module.ClassName
        parts = []
        current = base_node
        while isinstance(current, ast.Attribute):
            parts.insert(0, current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.insert(0, current.id)
        return ".".join(parts)
    return None
