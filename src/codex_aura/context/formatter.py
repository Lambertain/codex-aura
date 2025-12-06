"""Context formatters for different output formats."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.node import RankedNode


class ContextFormatter:
    """Format code context into different output formats."""

    def __init__(self, include_metadata: bool = True, include_docs: bool = True):
        self.include_metadata = include_metadata
        self.include_docs = include_docs

    def to_markdown(self, nodes: list["RankedNode"]) -> str:
        """Format as Markdown."""
        sections = []

        for node in nodes:
            section = []

            # Header
            if self.include_metadata:
                section.append(f"## {node.node.name}")
                section.append(f"**Path:** {node.node.path}")
                if node.node.lines:
                    section.append(f"**Lines:** {node.node.lines[0]}-{node.node.lines[1]}")
                section.append("")

            # Docstring
            if self.include_docs and node.node.docstring:
                section.append(f"**Docstring:** {node.node.docstring}")
                section.append("")

            # Code
            if node.node.content:
                section.append("```python")
                section.append(node.node.content)
                section.append("```")
                section.append("")

            sections.append("\n".join(section))

        return "\n---\n\n".join(sections)

    def to_xml(self, nodes: list["RankedNode"]) -> str:
        """Format as XML."""
        xml_parts = ["<context>"]

        for node in nodes:
            xml_parts.append("  <node>")
            xml_parts.append(f"    <id>{node.node.id}</id>")
            xml_parts.append(f"    <type>{node.node.type}</type>")
            xml_parts.append(f"    <name>{node.node.name}</name>")
            xml_parts.append(f"    <path>{node.node.path}</path>")
            if node.node.lines:
                xml_parts.append(f"    <lines>{node.node.lines[0]}-{node.node.lines[1]}</lines>")
            if self.include_docs and node.node.docstring:
                xml_parts.append(f"    <docstring>{node.node.docstring}</docstring>")
            if node.node.content:
                xml_parts.append("    <code><![CDATA[")
                xml_parts.append(node.node.content)
                xml_parts.append("    ]]></code>")
            xml_parts.append("  </node>")

        xml_parts.append("</context>")
        return "\n".join(xml_parts)

    def to_json(self, nodes: list["RankedNode"]) -> str:
        """Format as JSON."""
        import json

        data = []
        for node in nodes:
            node_data = {
                "id": node.node.id,
                "type": node.node.type,
                "name": node.node.name,
                "path": node.node.path,
            }
            if node.node.lines:
                node_data["lines"] = node.node.lines
            if self.include_docs and node.node.docstring:
                node_data["docstring"] = node.node.docstring
            if node.node.content:
                node_data["content"] = node.node.content
            data.append(node_data)

        return json.dumps({"nodes": data}, indent=2)

    def to_plain(self, nodes: list["RankedNode"]) -> str:
        """Format as plain text."""
        sections = []

        for node in nodes:
            section = []

            # Header
            if self.include_metadata:
                section.append(f"=== {node.node.name} ===")
                section.append(f"Path: {node.node.path}")
                if node.node.lines:
                    section.append(f"Lines: {node.node.lines[0]}-{node.node.lines[1]}")
                section.append("")

            # Docstring
            if self.include_docs and node.node.docstring:
                section.append(f"Docstring: {node.node.docstring}")
                section.append("")

            # Code
            if node.node.content:
                section.append(node.node.content)
                section.append("")

            sections.append("\n".join(section))

        return "\n" + "="*50 + "\n\n".join(sections)