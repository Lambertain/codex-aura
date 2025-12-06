from pydantic import BaseModel, Field
from typing import Literal

from ...token_budget.allocator import AllocationStrategy
from ...models.node import Node


class NodeSummary(BaseModel):
    """Summary of a node for context response."""

    id: str
    type: str
    name: str
    path: str
    lines: list[int] | None = None
    docstring: str | None = None

    @classmethod
    def from_node(cls, node: "Node") -> "NodeSummary":
        return cls(
            id=node.id,
            type=node.type,
            name=node.name,
            path=node.path,
            lines=node.lines,
            docstring=node.docstring
        )


class ContextRequest(BaseModel):
    """Request for intelligent code context."""

    repo_id: str = Field(..., description="Repository identifier")
    task: str = Field(..., description="Task description for semantic relevance")

    # Entry points
    entry_points: list[str] = Field(
        default=[],
        description="Starting points for graph traversal (file paths, FQNs, or globs)"
    )

    # Graph traversal
    depth: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum depth for dependency traversal"
    )

    # Token budget
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens for context (uses preset if not specified)"
    )
    model: str = Field(
        default="gpt-4",
        description="Target LLM model for token counting"
    )
    budget_strategy: AllocationStrategy = Field(
        default=AllocationStrategy.ADAPTIVE,
        description="Token allocation strategy"
    )

    # Filters
    include_tests: bool = Field(default=False, description="Include test files")
    include_docs: bool = Field(default=True, description="Include docstrings")
    file_patterns: list[str] = Field(
        default=[],
        description="Glob patterns to filter files (e.g., ['*.py', '!*_test.py'])"
    )

    # Output format
    format: Literal["plain", "markdown", "xml", "json"] = Field(
        default="markdown",
        description="Output format for context"
    )
    include_metadata: bool = Field(
        default=True,
        description="Include file paths, line numbers in output"
    )


class ContextResponse(BaseModel):
    """Response with code context."""

    context: str = Field(..., description="Formatted code context")

    nodes: list[NodeSummary] = Field(
        ...,
        description="Summary of included nodes"
    )

    stats: "ContextStats" = Field(..., description="Context statistics")

    # For debugging/transparency
    search_scores: dict[str, float] | None = Field(
        default=None,
        description="Semantic search scores for each node (if requested)"
    )


class ContextStats(BaseModel):
    total_tokens: int
    budget_used_pct: float
    nodes_included: int
    nodes_excluded: int
    nodes_truncated: int
    search_mode: str  # "graph", "semantic", "hybrid"
    allocation_strategy: str
    generation_time_ms: int