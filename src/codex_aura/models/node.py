"""Data models for representing code structure nodes."""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, field_validator


class BlameInfo(BaseModel):
    """Git blame information for a file.

    Contains authorship information extracted from git blame,
    including the primary author, list of contributors, and
    distribution of authorship across the file.
    """

    primary_author: str
    contributors: List[str]
    author_distribution: Dict[str, int]


class Node(BaseModel):
    """Represents a node in the code dependency graph.

    A node can represent a file, class, or function in the analyzed codebase.

    Attributes:
        id: Unique identifier for the node.
        type: Type of the node - "file", "class", or "function".
        name: Name of the entity (filename, class name, or function name).
        path: Relative path to the file containing this node.
        lines: Optional line range [start, end] where the entity is defined.
        docstring: Optional documentation string extracted from the code.
    """

    id: str
    type: Literal["file", "class", "function"]
    name: str
    path: str
    lines: Optional[List[int]] = None
    docstring: Optional[str] = None
    blame: Optional[BlameInfo] = None

    @field_validator("lines")
    @classmethod
    def validate_lines(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        """Validate that lines is either None or a list of exactly 2 integers.

        Args:
            v: The lines value to validate.

        Returns:
            The validated lines value.

        Raises:
            ValueError: If lines is not None and doesn't contain exactly 2 integers.
        """
        if v is not None and len(v) != 2:
            raise ValueError("lines must be a list of exactly 2 integers or None")
        return v
