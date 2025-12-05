"""Data models for representing complete code dependency graphs."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from .edge import Edge
from .node import Node


class Repository(BaseModel):
    """Information about the analyzed repository.

    Attributes:
        path: Absolute path to the repository root.
        name: Name of the repository (basename of the path).
    """

    path: str
    name: str


class Stats(BaseModel):
    """Statistics about the analyzed codebase.

    Attributes:
        total_nodes: Total number of nodes in the graph.
        total_edges: Total number of edges in the graph.
        node_types: Count of nodes by type (file, class, function).
        average_complexity: Average complexity score across all nodes.
        hot_spots_count: Number of high-complexity or high-connectivity nodes.
    """

    total_nodes: int
    total_edges: int
    node_types: Dict[str, int]
    average_complexity: float = 0.0
    hot_spots_count: int = 0


class Graph(BaseModel):
    """Complete representation of a code dependency graph.

    Contains all nodes, edges, and metadata about an analyzed codebase.

    Attributes:
        version: Version of the graph format.
        generated_at: Timestamp when the graph was generated.
        repository: Information about the analyzed repository.
        stats: Statistics about the graph contents.
        nodes: List of all nodes in the graph.
        edges: List of all edges in the graph.
        sha: Current commit SHA of the analyzed repository.
    """

    version: str
    generated_at: datetime
    repository: Repository
    stats: Stats
    nodes: List[Node]
    edges: List[Edge]
    sha: str = ""


def save_graph(graph: Graph, path: Path) -> None:
    """Save a graph to a JSON file.

    Args:
        graph: The Graph object to save.
        path: Path where to save the JSON file.
    """
    with path.open("w", encoding="utf-8") as f:
        f.write(graph.model_dump_json(indent=2))


def load_graph(path: Path) -> Graph:
    """Load a graph from a JSON file.

    Args:
        path: Path to the JSON file to load.

    Returns:
        The loaded Graph object.
    """
    with path.open("r", encoding="utf-8") as f:
        data = f.read()
    return Graph.model_validate_json(data)


def remove_nodes_by_path(graph: Graph, path: str) -> Graph:
    """Remove all nodes associated with a specific file path.

    Args:
        graph: The Graph object to modify.
        path: File path to remove nodes for.

    Returns:
        Modified Graph object with nodes removed.
    """
    # Remove nodes with matching path
    filtered_nodes = [node for node in graph.nodes if node.path != path]

    # Remove edges that reference removed nodes
    node_ids = {node.id for node in filtered_nodes}
    filtered_edges = [
        edge for edge in graph.edges
        if edge.source in node_ids and edge.target in node_ids
    ]

    # Update stats
    node_types = {}
    for node in filtered_nodes:
        node_types[node.type] = node_types.get(node.type, 0) + 1

    updated_stats = Stats(
        total_nodes=len(filtered_nodes),
        total_edges=len(filtered_edges),
        node_types=node_types
    )

    return Graph(
        version=graph.version,
        generated_at=graph.generated_at,
        repository=graph.repository,
        stats=updated_stats,
        nodes=filtered_nodes,
        edges=filtered_edges,
        sha=graph.sha
    )


def replace_nodes_for_path(graph: Graph, path: str, new_nodes: List[Node]) -> Graph:
    """Replace all nodes for a specific file path with new nodes.

    Args:
        graph: The Graph object to modify.
        path: File path to replace nodes for.
        new_nodes: List of new nodes to add.

    Returns:
        Modified Graph object with nodes replaced.
    """
    # Remove old nodes for this path
    filtered_nodes = [node for node in graph.nodes if node.path != path]

    # Add new nodes
    filtered_nodes.extend(new_nodes)

    # Remove edges that reference removed nodes
    old_node_ids = {node.id for node in graph.nodes if node.path == path}
    node_ids = {node.id for node in filtered_nodes}
    filtered_edges = [
        edge for edge in graph.edges
        if edge.source in node_ids and edge.target in node_ids
    ]

    # Update stats
    node_types = {}
    for node in filtered_nodes:
        node_types[node.type] = node_types.get(node.type, 0) + 1

    updated_stats = Stats(
        total_nodes=len(filtered_nodes),
        total_edges=len(filtered_edges),
        node_types=node_types
    )

    return Graph(
        version=graph.version,
        generated_at=graph.generated_at,
        repository=graph.repository,
        stats=updated_stats,
        nodes=filtered_nodes,
        edges=filtered_edges,
        sha=graph.sha
    )


def rebuild_edges_for_paths(graph: Graph, paths: List[str]) -> Graph:
    """Rebuild edges for nodes in specified paths.

    This is a simplified implementation that rebuilds all edges.
    In a full implementation, this would only rebuild edges for affected nodes.

    Args:
        graph: The Graph object to modify.
        paths: List of file paths to rebuild edges for.

    Returns:
        Modified Graph object with edges rebuilt.
    """
    # For now, return the graph as-is since full edge rebuilding
    # would require re-analyzing the codebase
    # In a complete implementation, this would:
    # 1. Identify all nodes that could be affected by changes in the given paths
    # 2. Re-analyze imports, calls, and inheritance relationships
    # 3. Update the edges accordingly

    return graph
