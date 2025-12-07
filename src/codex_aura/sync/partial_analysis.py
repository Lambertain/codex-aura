import ast
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..analyzer.base import BaseAnalyzer
from ..models.node import Node
from ..models.usage import UsageEvent
from ..storage.usage_storage import UsageStorage

logger = logging.getLogger(__name__)


@dataclass
class PartialAnalysisResult:
    """Result of partial analysis of changed code."""
    updated_nodes: List[Node]
    deleted_nodes: List[Node]
    unchanged_nodes: List[Node]


class PartialAnalyzer:
    """Analyze only changed portions of files."""

    def __init__(self, analyzer: BaseAnalyzer):
        self.analyzer = analyzer

    async def analyze_changes(
        self,
        file_path: Path,
        old_content: str | None,
        new_content: str,
        changed_lines: list[int]
    ) -> PartialAnalysisResult:
        """
        Smart analysis that focuses on changed code regions.

        Strategy:
        1. Parse both old and new AST
        2. Find nodes that contain changed lines
        3. Only re-analyze those nodes
        4. Keep unchanged nodes from old analysis
        """
        result = PartialAnalysisResult(
            updated_nodes=[],
            deleted_nodes=[],
            unchanged_nodes=[]
        )

        # Parse new content
        new_tree = ast.parse(new_content)
        new_nodes = self._extract_nodes(new_tree, file_path, new_content)

        if old_content is None:
            # New file - all nodes are new
            result.updated_nodes = new_nodes
            return result

        # Parse old content
        try:
            old_tree = ast.parse(old_content)
            old_nodes = self._extract_nodes(old_tree, file_path, old_content)
        except SyntaxError:
            # Old content had syntax error - treat as full update
            result.updated_nodes = new_nodes
            return result

        old_nodes_map = {n.fqn: n for n in old_nodes}
        new_nodes_map = {n.fqn: n for n in new_nodes}

        # Find affected nodes
        affected_fqns = self._find_affected_nodes(new_nodes, changed_lines)

        for fqn, node in new_nodes_map.items():
            if fqn in affected_fqns:
                # Node was changed
                result.updated_nodes.append(node)
            elif fqn in old_nodes_map:
                # Node unchanged, keep old analysis
                result.unchanged_nodes.append(old_nodes_map[fqn])
            else:
                # New node
                result.updated_nodes.append(node)

        # Find deleted nodes
        for fqn in old_nodes_map:
            if fqn not in new_nodes_map:
                result.deleted_nodes.append(old_nodes_map[fqn])

        # Log sync event
        try:
            usage_storage = UsageStorage()
            await usage_storage.insert_usage_event(UsageEvent(
                user_id="system",  # TODO: get from context
                event_type="sync_event",
                endpoint="partial_analysis",
                tokens_used=None,
                metadata={
                    "file_path": str(file_path),
                    "changed_lines_count": len(changed_lines),
                    "updated_nodes": len(result.updated_nodes),
                    "deleted_nodes": len(result.deleted_nodes),
                    "unchanged_nodes": len(result.unchanged_nodes)
                }
            ))
        except Exception as e:
            logger.warning(f"Failed to log sync event: {e}")

        return result

    def _find_affected_nodes(
        self,
        nodes: list[Node],
        changed_lines: list[int]
    ) -> set[str]:
        """Find nodes that contain any changed line."""
        affected = set()
        changed_set = set(changed_lines)

        for node in nodes:
            node_lines = set(range(node.start_line, node.end_line + 1))
            if node_lines & changed_set:
                affected.add(node.fqn)

        return affected

    def _extract_nodes(
        self,
        tree: ast.AST,
        file_path: Path,
        content: str
    ) -> list[Node]:
        """Extract all analyzable nodes from AST."""
        nodes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                nodes.append(self._node_from_ast(node, "function", file_path, content))
            elif isinstance(node, ast.ClassDef):
                nodes.append(self._node_from_ast(node, "class", file_path, content))

        return nodes

    def _node_from_ast(
        self,
        node: ast.FunctionDef | ast.ClassDef,
        node_type: str,
        file_path: Path,
        content: str
    ) -> Node:
        """Create Node from AST node."""
        lines = content.splitlines()
        start_line = node.lineno - 1  # AST uses 1-based, we use 0-based
        end_line = getattr(node, 'end_lineno', start_line + 1) - 1

        # Extract docstring
        docstring = None
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
            docstring = node.body[0].value.s

        return Node(
            id=f"{file_path}:{node.name}",
            type=node_type,
            name=node.name,
            path=str(file_path),
            lines=[start_line, end_line],
            docstring=docstring
        )