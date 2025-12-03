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
    """

    total_nodes: int
    total_edges: int
    node_types: Dict[str, int]


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
    """

    version: str
    generated_at: datetime
    repository: Repository
    stats: Stats
    nodes: List[Node]
    edges: List[Edge]


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
