"""Context result wrapper for Codex Aura SDK."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ContextNode:
    """Represents a context node with metadata."""

    id: str
    type: str
    path: str
    code: Optional[str] = None
    relevance: float = 0.0


@dataclass
class Context:
    """Context result wrapper with formatting capabilities."""

    context_nodes: List[ContextNode]
    total_nodes: int
    truncated: bool

    def to_prompt(self, format: str = "markdown", include_tree: bool = False) -> str:
        """Convert context to formatted prompt string.

        Args:
            format: Output format ("markdown", "json", "text")
            include_tree: Whether to include file tree structure

        Returns:
            Formatted prompt string
        """
        if format == "json":
            return self._to_json_prompt()
        elif format == "text":
            return self._to_text_prompt(include_tree)
        else:  # markdown
            return self._to_markdown_prompt(include_tree)

    def _to_markdown_prompt(self, include_tree: bool) -> str:
        """Convert to markdown format."""
        lines = ["# Code Context\n"]

        if include_tree:
            lines.append("## File Structure\n")
            # Group nodes by path
            path_groups = {}
            for node in self.context_nodes:
                path = node.path
                if path not in path_groups:
                    path_groups[path] = []
                path_groups[path].append(node)

            for path, nodes in path_groups.items():
                lines.append(f"### {path}")
                for node in nodes:
                    lines.append(f"- **{node.type}**: {node.id} (relevance: {node.relevance:.2f})")
                    if node.code:
                        lines.append(f"  ```python\n{node.code}\n  ```")
                lines.append("")

        lines.append("## Context Nodes\n")
        for node in self.context_nodes:
            lines.append(f"### {node.id}")
            lines.append(f"- **Type**: {node.type}")
            lines.append(f"- **Path**: {node.path}")
            lines.append(f"- **Relevance**: {node.relevance:.2f}")
            if node.code:
                lines.append(f"- **Code**:\n```python\n{node.code}\n```")
            lines.append("")

        if self.truncated:
            lines.append(f"\n*Note: Context truncated. Total nodes available: {self.total_nodes}*")

        return "\n".join(lines)

    def _to_text_prompt(self, include_tree: bool) -> str:
        """Convert to plain text format."""
        lines = ["CODE CONTEXT\n"]

        if include_tree:
            lines.append("FILE STRUCTURE:")
            path_groups = {}
            for node in self.context_nodes:
                path = node.path
                if path not in path_groups:
                    path_groups[path] = []
                path_groups[path].append(node)

            for path, nodes in path_groups.items():
                lines.append(f"{path}:")
                for node in nodes:
                    lines.append(f"  - {node.type}: {node.id} (rel: {node.relevance:.2f})")
                    if node.code:
                        lines.append(f"    {node.code}")
                lines.append("")

        lines.append("CONTEXT NODES:")
        for node in self.context_nodes:
            lines.append(f"{node.id} ({node.type}) - {node.path}")
            lines.append(f"Relevance: {node.relevance:.2f}")
            if node.code:
                lines.append(f"Code:\n{node.code}")
            lines.append("")

        if self.truncated:
            lines.append(f"Note: Context truncated. Total nodes: {self.total_nodes}")

        return "\n".join(lines)

    def _to_json_prompt(self) -> str:
        """Convert to JSON format."""
        import json

        data = {
            "context_nodes": [
                {
                    "id": node.id,
                    "type": node.type,
                    "path": node.path,
                    "code": node.code,
                    "relevance": node.relevance
                }
                for node in self.context_nodes
            ],
            "total_nodes": self.total_nodes,
            "truncated": self.truncated
        }

        return json.dumps(data, indent=2)

    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> "Context":
        """Create Context from API response data."""
        context_nodes = [
            ContextNode(
                id=node["id"],
                type=node["type"],
                path=node["path"],
                code=node.get("code"),
                relevance=node["relevance"]
            )
            for node in response_data["context_nodes"]
        ]

        return cls(
            context_nodes=context_nodes,
            total_nodes=response_data["total_nodes"],
            truncated=response_data["truncated"]
        )