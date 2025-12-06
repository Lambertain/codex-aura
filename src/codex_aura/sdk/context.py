"""Context result wrapper for Codex Aura SDK."""

from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass
from ..models.edge import Edge


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
    edges: Optional[List[Edge]] = None

    def to_prompt(
        self,
        format: Literal["plain", "markdown", "xml"] = "markdown",
        include_tree: bool = False,
        include_edges: bool = False,
        max_chars: Optional[int] = None
    ) -> str:
        """Convert context to formatted prompt string.

        Args:
            format: Output format ("plain", "markdown", "xml")
            include_tree: Whether to include file tree structure
            include_edges: Whether to include edge relationships
            max_chars: Maximum character limit for output (truncates if exceeded)

        Returns:
            Formatted prompt string
        """
        if format == "xml":
            result = self._to_xml_prompt(include_tree, include_edges)
        elif format == "plain":
            result = self._to_plain_prompt(include_tree, include_edges)
        else:  # markdown
            result = self._to_markdown_prompt(include_tree, include_edges)

        # Apply truncation if max_chars is specified
        if max_chars and len(result) > max_chars:
            result = result[:max_chars - 3] + "..."

        return result

    def _to_markdown_prompt(self, include_tree: bool, include_edges: bool) -> str:
        """Convert to markdown format."""
        lines = ["## Relevant Code Context\n"]

        if include_tree:
            lines.append("### File Structure\n")
            # Group nodes by path
            path_groups = {}
            for node in self.context_nodes:
                path = node.path
                if path not in path_groups:
                    path_groups[path] = []
                path_groups[path].append(node)

            for path, nodes in path_groups.items():
                lines.append(f"#### {path}")
                for node in nodes:
                    lines.append(f"- **{node.type}**: {node.id} (relevance: {node.relevance:.2f})")
                    if node.code:
                        lines.append(f"  ```python\n{node.code}\n  ```")
                lines.append("")

        lines.append("### Context Nodes\n")
        for node in self.context_nodes:
            lines.append(f"#### {node.id}")
            lines.append(f"- **Type**: {node.type}")
            lines.append(f"- **Path**: {node.path}")
            lines.append(f"- **Relevance**: {node.relevance:.2f}")
            if node.code:
                lines.append(f"- **Code**:\n```python\n{node.code}\n```")
            lines.append("")

        if include_edges and self.edges:
            lines.append("### Dependencies\n")
            for edge in self.edges:
                source_node = next((n for n in self.context_nodes if n.id == edge.source), None)
                target_node = next((n for n in self.context_nodes if n.id == edge.target), None)
                if source_node and target_node:
                    lines.append(f"- `{source_node.path}` **{edge.type.value}** `{target_node.path}`")
                    if edge.line:
                        lines.append(f"  (line {edge.line})")
                lines.append("")

        if self.truncated:
            lines.append(f"\n*Note: Context truncated. Total nodes available: {self.total_nodes}*")

        return "\n".join(lines)

    def _to_plain_prompt(self, include_tree: bool, include_edges: bool) -> str:
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

        if include_edges and self.edges:
            lines.append("DEPENDENCIES:")
            for edge in self.edges:
                source_node = next((n for n in self.context_nodes if n.id == edge.source), None)
                target_node = next((n for n in self.context_nodes if n.id == edge.target), None)
                if source_node and target_node:
                    lines.append(f"- {source_node.path} {edge.type.value} {target_node.path}")
                    if edge.line:
                        lines.append(f"  (line {edge.line})")
                lines.append("")

        if self.truncated:
            lines.append(f"Note: Context truncated. Total nodes: {self.total_nodes}")

        return "\n".join(lines)

    def _to_xml_prompt(self, include_tree: bool, include_edges: bool) -> str:
        """Convert to XML format."""
        lines = ["<context>"]

        if include_tree:
            lines.append("  <file_structure>")
            # Group nodes by path
            path_groups = {}
            for node in self.context_nodes:
                path = node.path
                if path not in path_groups:
                    path_groups[path] = []
                path_groups[path].append(node)

            for path, nodes in path_groups.items():
                lines.append(f"    <file path=\"{path}\">")
                for node in nodes:
                    lines.append(f"      <node id=\"{node.id}\" type=\"{node.type}\" relevance=\"{node.relevance:.2f}\">")
                    if node.code:
                        # Escape XML characters in code
                        code = node.code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        lines.append(f"        <code>{code}</code>")
                    lines.append("      </node>")
                lines.append("    </file>")
            lines.append("  </file_structure>")

        lines.append("  <context_nodes>")
        for node in self.context_nodes:
            lines.append(f"    <node id=\"{node.id}\" type=\"{node.type}\" path=\"{node.path}\" relevance=\"{node.relevance:.2f}\">")
            if node.code:
                # Escape XML characters in code
                code = node.code.replace("&", "&amp;")
                code = code.replace("<", "&lt;")
                code = code.replace(">", "&gt;")
                code = code.replace('"', "&quot;")
                code = code.replace("'", "&apos;")
                lines.append(f"      <code>{code}</code>")
            lines.append("    </node>")
        lines.append("  </context_nodes>")

        if include_edges and self.edges:
            lines.append("  <dependencies>")
            for edge in self.edges:
                source_node = next((n for n in self.context_nodes if n.id == edge.source), None)
                target_node = next((n for n in self.context_nodes if n.id == edge.target), None)
                if source_node and target_node:
                    line_attr = f" line=\"{edge.line}\"" if edge.line else ""
                    lines.append(f"    <dependency type=\"{edge.type.value}\" source=\"{source_node.path}\" target=\"{target_node.path}\"{line_attr}/>")
            lines.append("  </dependencies>")

        if self.truncated:
            lines.append(f"  <note>Context truncated. Total nodes available: {self.total_nodes}</note>")

        lines.append("</context>")
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

        # Handle edges if present in response
        edges = None
        if "edges" in response_data and response_data["edges"]:
            edges = [
                Edge(
                    source=edge["source"],
                    target=edge["target"],
                    type=edge["type"],
                    line=edge.get("line")
                )
                for edge in response_data["edges"]
            ]

        return cls(
            context_nodes=context_nodes,
            total_nodes=response_data["total_nodes"],
            truncated=response_data["truncated"],
            edges=edges
        )