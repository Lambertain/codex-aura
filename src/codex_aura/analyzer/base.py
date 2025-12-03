from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from ..models.graph import Graph
from ..models.node import Node


class BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, repo_path: Path) -> Graph:
        """Analyze repository and return graph."""
        pass

    @abstractmethod
    def analyze_file(self, file_path: Path) -> List[Node]:
        """Analyze single file and return nodes."""
        pass