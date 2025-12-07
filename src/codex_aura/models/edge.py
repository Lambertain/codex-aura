"""Data models for representing relationships between code entities."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


class EdgeType(str, Enum):
    """Types of relationships between nodes in the dependency graph."""

    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    EXTENDS = "EXTENDS"
    SERVICE_CALLS = "SERVICE_CALLS"  # Межсервисные вызовы

    @classmethod
    def _missing_(cls, value):
        """Allow custom edge types that start with CUSTOM_."""
        if isinstance(value, str) and value.startswith("CUSTOM_"):
            # Create a new pseudo-member for custom types
            # Instead of calling cls(value) which causes recursion,
            # we create an object that behaves like an enum member
            obj = str.__new__(cls, value)
            obj._value_ = value
            obj._name_ = value
            return obj
        return None


class Edge(BaseModel):
    """Represents a directed relationship between two nodes in the code graph.

    Edges represent dependencies or relationships between different code entities,
    such as import statements connecting files or modules.

    Attributes:
        source: ID of the source node.
        target: ID of the target node.
        type: Type of relationship (IMPORTS, CALLS, EXTENDS, or CUSTOM_*).
        line: Optional line number where the relationship is defined.

    Extension fields starting with 'x-' are allowed for custom extensions.
    """

    source: str
    target: str
    type: EdgeType
    line: Optional[int] = None

    class Config:
        """Pydantic configuration to allow extension fields."""
        extra = "allow"  # Allow additional fields not defined in the model
