"""Base classes for plugins."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..models.graph import Graph
from ..models.node import Node


class ContextPlugin(ABC):
    """Base class for context ranking plugins."""

    name: str
    version: str

    @abstractmethod
    def rank_nodes(self, nodes: List[Node], task: Optional[str] = None, max_tokens: Optional[int] = None) -> List[Node]:
        """Rank nodes by relevance for context.

        Args:
            nodes: List of nodes to rank
            task: Optional task description for context
            max_tokens: Optional token limit for ranking

        Returns:
            Ranked list of nodes
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """Get plugin capabilities.

        Returns:
            Dict of capability flags
        """
        pass


class ImpactPlugin(ABC):
    """Base class for impact analysis plugins."""

    @abstractmethod
    def analyze_impact(self, changed_files: List[str], graph: Graph, depth: int = 3) -> 'ImpactReport':
        """Analyze impact of changes to files.

        Args:
            changed_files: List of changed file paths
            graph: Dependency graph
            depth: Maximum depth for impact analysis

        Returns:
            Impact analysis report
        """
        pass


class ImpactReport:
    """Report for impact analysis."""

    def __init__(self, affected_files: List[str], risk_level: str):
        self.affected_files = affected_files
        self.risk_level = risk_level