"""Basic impact analysis plugin."""

from typing import List

from ..base import ImpactPlugin, ImpactReport
from ..registry import PluginRegistry
from ...models.graph import Graph


@PluginRegistry.register_impact("basic")
class BasicImpactPlugin(ImpactPlugin):
    """Basic impact plugin that finds affected files by dependency traversal."""

    def analyze_impact(self, changed_files: List[str], graph: Graph, depth: int = 3) -> ImpactReport:
        """Analyze impact of changes to specified files.

        Finds all files that depend on the changed files up to the specified depth.

        Args:
            changed_files: List of changed file paths
            graph: Dependency graph
            depth: Maximum depth for impact analysis

        Returns:
            Impact analysis report
        """
        affected = set()

        for file_path in changed_files:
            # Find all nodes in the changed file
            changed_file_nodes = [n for n in graph.nodes if n.path == file_path]

            for node in changed_file_nodes:
                # Find incoming edges (who depends on this node)
                incoming_edges = [e for e in graph.edges if e.target == node.id]

                for edge in incoming_edges:
                    # Find the file containing the dependent node
                    dependent_node = next((n for n in graph.nodes if n.id == edge.source), None)
                    if dependent_node and dependent_node.path not in affected and dependent_node.path not in changed_files:
                        affected.add(dependent_node.path)

        # Calculate risk level based on number of affected files
        risk_level = self._calculate_risk(affected)

        return ImpactReport(
            affected_files=list(affected),
            risk_level=risk_level
        )

    def _calculate_risk(self, affected_files: set) -> str:
        """Calculate risk level based on number of affected files."""
        count = len(affected_files)
        if count == 0:
            return "low"
        elif count == 1:
            return "low"
        elif count <= 5:
            return "medium"
        else:
            return "high"