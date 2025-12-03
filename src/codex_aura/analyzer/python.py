import ast
import logging
from datetime import datetime
from pathlib import Path
from typing import List

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
        for file_path in python_files:
            try:
                file_nodes = self.analyze_file(file_path)
                nodes.extend(file_nodes)
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

    def analyze_file(self, file_path: Path) -> List[Node]:
        """Analyze single Python file and return nodes."""
        return [parse_file_node(file_path, file_path.parent)]


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