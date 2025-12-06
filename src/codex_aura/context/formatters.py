"""Context formatters for different output formats."""

from collections import defaultdict
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.node import RankedNode


class ContextFormatter:
    """Format code nodes into different output formats."""

    def __init__(self, include_metadata: bool = True, include_docs: bool = True):
        self.include_metadata = include_metadata
        self.include_docs = include_docs

    def to_markdown(self, nodes: list[RankedNode]) -> str:
        """Format as Markdown with code blocks."""
        output = ["## Relevant Code Context\n"]

        # Group by file
        by_file = defaultdict(list)
        for rn in nodes:
            by_file[rn.node.path].append(rn)

        for file_path, file_nodes in by_file.items():
            output.append(f"### {file_path}\n")

            for rn in sorted(file_nodes, key=lambda x: x.node.start_line):
                node = rn.node

                if self.include_metadata:
                    output.append(f"**{node.type.title()}: {node.name}** (lines {node.start_line}-{node.end_line})\n")

                lang = self._detect_language(file_path)
                output.append(f"```{lang}")
                output.append(node.content)
                output.append("```\n")

        return "\n".join(output)

    def to_xml(self, nodes: list[RankedNode]) -> str:
        """Format as XML (useful for Claude prompts)."""
        output = ["<code_context>"]

        for rn in nodes:
            node = rn.node
            output.append(f'  <file path="{node.path}">')
            output.append(f'    <{node.type} name="{node.name}" lines="{node.start_line}-{node.end_line}">')
            output.append(f"      <![CDATA[{node.content}]]>")
            output.append(f"    </{node.type}>")
            output.append("  </file>")

        output.append("</code_context>")
        return "\n".join(output)

    def to_json(self, nodes: list[RankedNode]) -> str:
        """Format as JSON."""
        data = {
            "context": [
                {
                    "file_path": rn.node.path,
                    "type": rn.node.type,
                    "name": rn.node.name,
                    "start_line": rn.node.start_line,
                    "end_line": rn.node.end_line,
                    "content": rn.node.content,
                    "relevance_score": rn.score
                }
                for rn in nodes
            ]
        }
        return json.dumps(data, indent=2)

    def to_plain(self, nodes: list[RankedNode]) -> str:
        """Plain text format."""
        output = []

        for rn in nodes:
            node = rn.node
            output.append(f"# {node.path}:{node.start_line}")
            output.append(node.content)
            output.append("")  # Empty line between nodes

        return "\n".join(output)

    @staticmethod
    def _detect_language(file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = file_path.split('.')[-1].lower()
        lang_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'cs': 'csharp',
            'php': 'php',
            'rb': 'ruby',
            'go': 'go',
            'rs': 'rust',
            'swift': 'swift',
            'kt': 'kotlin',
            'scala': 'scala',
            'sh': 'bash',
            'sql': 'sql',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'xml': 'xml',
            'yaml': 'yaml',
            'yml': 'yaml',
            'md': 'markdown'
        }
        return lang_map.get(ext, 'text')