"""Base classes for code analyzers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models.graph import Graph
from ..models.node import Node


class BaseAnalyzer(ABC):
    """Abstract base class for code analyzers.

    Provides the interface that all code analyzers must implement.
    """

    @abstractmethod
    def analyze(self, repo_path: Path) -> Graph:
        """Analyze a repository and return a complete dependency graph.

        Args:
            repo_path: Path to the repository root directory.

        Returns:
            A Graph object containing all nodes and edges found in the repository.
        """
        pass

    @abstractmethod
    def analyze_file(self, file_path: Path) -> List[Node]:
        """Analyze a single file and return the nodes it contains.

        Args:
            file_path: Path to the file to analyze.

        Returns:
            List of Node objects representing entities found in the file.
        """
        pass

    @abstractmethod
    def resolve_references(self, node: Node) -> List["Reference"]:
        """Resolve references from a node to other nodes.

        Args:
            node: The node to resolve references for.

        Returns:
            List of Reference objects representing relationships.
        """
        pass
