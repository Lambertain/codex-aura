"""Custom context plugin example for Codex Aura."""

import logging
from typing import Dict, List, Optional

from codex_aura.models.node import Node
from codex_aura.plugins.base import ContextPlugin

logger = logging.getLogger(__name__)


class CustomContextPlugin(ContextPlugin):
    """Custom context plugin with semantic ranking capabilities.

    This plugin demonstrates advanced context ranking using semantic analysis
    and task understanding to provide more relevant code context.
    """

    name = "custom_context"
    version = "0.1.0"

    def __init__(self):
        """Initialize the plugin."""
        self.semantic_model = None  # Could be initialized with ML model
        self.task_keywords = set()

    def rank_nodes(self, nodes: List[Node], task: Optional[str] = None, max_tokens: Optional[int] = None) -> List[Node]:
        """Rank nodes by semantic relevance and task context.

        Args:
            nodes: List of nodes to rank
            task: Optional task description for context understanding
            max_tokens: Optional token limit for ranking

        Returns:
            Ranked list of nodes by relevance
        """
        if not nodes:
            return []

        # Extract task keywords for semantic matching
        if task:
            self._extract_task_keywords(task)

        # Calculate relevance scores for each node
        scored_nodes = []
        for node in nodes:
            score = self._calculate_relevance_score(node, task)
            scored_nodes.append((node, score))

        # Sort by score (descending - higher score = more relevant)
        scored_nodes.sort(key=lambda x: x[1], reverse=True)

        # Apply token limit if specified
        if max_tokens:
            result_nodes = []
            total_tokens = 0
            for node, score in scored_nodes:
                node_tokens = self._estimate_tokens(node)
                if total_tokens + node_tokens <= max_tokens:
                    result_nodes.append(node)
                    total_tokens += node_tokens
                else:
                    break
            return result_nodes

        return [node for node, score in scored_nodes]

    def _extract_task_keywords(self, task: str) -> None:
        """Extract keywords from task description."""
        # Simple keyword extraction - could be enhanced with NLP
        words = task.lower().split()
        self.task_keywords = set(words)

    def _calculate_relevance_score(self, node: Node, task: Optional[str] = None) -> float:
        """Calculate relevance score for a node."""
        score = 0.0

        # Base score from node type importance
        type_weights = {
            'function': 1.0,
            'class': 0.9,
            'method': 0.8,
            'module': 0.3,
            'variable': 0.2
        }
        score += type_weights.get(getattr(node, 'type', 'unknown'), 0.1)

        # Distance penalty (closer nodes are more relevant)
        distance = getattr(node, 'distance', 0)
        score += max(0, 1.0 - distance * 0.1)

        # Task relevance bonus
        if task and self.task_keywords:
            node_content = getattr(node, 'content', '').lower()
            node_name = getattr(node, 'name', '').lower()

            keyword_matches = 0
            for keyword in self.task_keywords:
                if keyword in node_content or keyword in node_name:
                    keyword_matches += 1

            if keyword_matches > 0:
                score += min(1.0, keyword_matches * 0.5)

        return score

    def _estimate_tokens(self, node: Node) -> int:
        """Estimate token count for a node."""
        content = getattr(node, 'content', '')
        # Rough estimation: ~4 characters per token
        return len(content) // 4

    def get_capabilities(self) -> Dict[str, bool]:
        """Get plugin capabilities."""
        return {
            "semantic_ranking": True,      # Uses semantic analysis
            "token_budgeting": True,      # Supports token limits
            "task_understanding": True    # Understands task context
        }