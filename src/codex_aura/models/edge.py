"""Data models for representing relationships between code entities."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class EdgeType(str, Enum):
    """Types of relationships between nodes in the dependency graph."""

    IMPORTS = "IMPORTS"


class Edge(BaseModel):
    """Represents a directed relationship between two nodes in the code graph.

    Edges represent dependencies or relationships between different code entities,
    such as import statements connecting files or modules.

    Attributes:
        source: ID of the source node.
        target: ID of the target node.
        type: Type of relationship (currently only IMPORTS).
        line: Optional line number where the relationship is defined.
    """

    source: str
    target: str
    type: EdgeType
    line: Optional[int] = None
