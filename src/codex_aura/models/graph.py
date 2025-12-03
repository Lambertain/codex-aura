from datetime import datetime
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel

from .edge import Edge
from .node import Node


class Repository(BaseModel):
    path: str
    name: str


class Stats(BaseModel):
    total_nodes: int
    total_edges: int
    node_types: Dict[str, int]


class Graph(BaseModel):
    version: str
    generated_at: datetime
    repository: Repository
    stats: Stats
    nodes: List[Node]
    edges: List[Edge]


def save_graph(graph: Graph, path: Path) -> None:
    """Save graph to JSON file."""
    with path.open('w', encoding='utf-8') as f:
        f.write(graph.model_dump_json(indent=2))


def load_graph(path: Path) -> Graph:
    """Load graph from JSON file."""
    with path.open('r', encoding='utf-8') as f:
        data = f.read()
    return Graph.model_validate_json(data)