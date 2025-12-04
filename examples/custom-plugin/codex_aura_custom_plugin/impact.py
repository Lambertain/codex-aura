"""Custom impact plugin example for Codex Aura."""

import logging
from typing import Dict, List

from codex_aura.models.graph import Graph
from codex_aura.plugins.base import ImpactPlugin, ImpactReport

logger = logging.getLogger(__name__)


class CustomImpactPlugin(ImpactPlugin):
    """Custom impact plugin with risk assessment capabilities.

    This plugin performs deep analysis of code changes and assesses
    their potential impact and risk level on the codebase.
    """

    name = "custom_impact"
    version = "0.1.0"

    def __init__(self):
        """Initialize the plugin."""
        self.risk_thresholds = {
            'low': 5,
            'medium': 15,
            'high': 30
        }

    def analyze_impact(self, changed_files: List[str], graph: Graph, depth: int = 3) -> ImpactReport:
        """Analyze impact of changes with risk assessment.

        Args:
            changed_files: List of changed file paths
            graph: Dependency graph
            depth: Maximum depth for impact analysis

        Returns:
            Impact analysis report with risk assessment
        """
        affected_files = set()
        impact_score = 0

        for file_path in changed_files:
            # Find the node corresponding to the changed file
            changed_node = self._find_node_by_file(graph, file_path)
            if not changed_node:
                logger.warning(f"Could not find node for file: {file_path}")
                continue

            # Analyze direct dependencies
            direct_deps = graph.get_neighbors(changed_node.id, depth=1)
            affected_files.update(self._extract_file_paths(direct_deps))

            # Analyze indirect dependencies based on depth
            if depth > 1:
                indirect_deps = graph.get_neighbors(changed_node.id, depth=depth)
                affected_files.update(self._extract_file_paths(indirect_deps))

            # Calculate impact score based on node type and dependencies
            impact_score += self._calculate_node_impact(changed_node, direct_deps, indirect_deps)

        # Remove the changed files themselves from affected files
        affected_files -= set(changed_files)

        # Determine risk level based on impact score
        risk_level = self._assess_risk_level(impact_score, len(affected_files))

        return ImpactReport(list(affected_files), risk_level)

    def _find_node_by_file(self, graph: Graph, file_path: str):
        """Find graph node by file path."""
        # This is a simplified implementation - real implementation would
        # need to match file paths properly
        for node_id, node in graph.nodes.items():
            if getattr(node, 'file_path', None) == file_path:
                return node
        return None

    def _extract_file_paths(self, nodes: List) -> List[str]:
        """Extract file paths from nodes."""
        return [getattr(node, 'file_path', '') for node in nodes if hasattr(node, 'file_path')]

    def _calculate_node_impact(self, node, direct_deps: List, indirect_deps: List) -> int:
        """Calculate impact score for a node."""
        score = 0

        # Base score by node type
        node_type = getattr(node, 'type', 'unknown')
        type_scores = {
            'function': 3,
            'class': 5,
            'module': 8,
            'interface': 4,
            'method': 2
        }
        score += type_scores.get(node_type, 1)

        # Score based on number of dependencies
        score += len(direct_deps) * 2
        score += len(indirect_deps) * 1

        # Bonus for critical files (could be enhanced with heuristics)
        file_path = getattr(node, 'file_path', '')
        if any(keyword in file_path.lower() for keyword in ['core', 'main', 'config', 'api']):
            score += 5

        return score

    def _assess_risk_level(self, impact_score: int, affected_count: int) -> str:
        """Assess risk level based on impact metrics."""
        # Combine impact score and affected file count
        total_risk = impact_score + affected_count

        if total_risk <= self.risk_thresholds['low']:
            return 'low'
        elif total_risk <= self.risk_thresholds['medium']:
            return 'medium'
        else:
            return 'high'

    def get_capabilities(self) -> Dict[str, bool]:
        """Get plugin capabilities."""
        return {
            "deep_analysis": True,         # Performs deep dependency analysis
            "performance_tracking": False, # Could be added in future
            "risk_assessment": True       # Assesses risk levels
        }