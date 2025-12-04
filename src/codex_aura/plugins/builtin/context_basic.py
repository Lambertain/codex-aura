"""Basic context ranking plugin."""

from typing import Dict, List, Optional

from ..base import ContextPlugin
from ..registry import PluginRegistry
from ...models.node import Node


@PluginRegistry.register_context("basic")
class BasicContextPlugin(ContextPlugin):
    """Basic context plugin that ranks nodes by graph distance."""

    name = "basic"
    version = "1.0.0"

    def rank_nodes(self, nodes: List[Node], task: Optional[str] = None, max_tokens: Optional[int] = None) -> List[Node]:
        """Rank nodes by graph distance.

        Sorts nodes by their distance attribute (ascending).
        If max_tokens is provided, performs simple truncation.

        Args:
            nodes: List of nodes to rank
            task: Optional task description (ignored in basic plugin)
            max_tokens: Optional token limit for truncation

        Returns:
            Ranked list of nodes
        """
        # Sort by distance (assuming nodes have distance attribute)
        # If no distance, assume distance 0
        sorted_nodes = sorted(nodes, key=lambda n: getattr(n, 'distance', 0))

        if max_tokens:
            # Simple truncation based on estimated token count
            return sorted_nodes[:self._estimate_count(max_tokens)]
        return sorted_nodes

    def _estimate_count(self, max_tokens: int) -> int:
        """Estimate how many nodes fit within token limit.

        Very basic estimation - assumes average of 100 tokens per node.
        """
        return max(1, max_tokens // 100)

    def get_capabilities(self) -> Dict[str, bool]:
        """Get plugin capabilities."""
        return {
            "semantic_ranking": False,
            "token_budgeting": False,
            "task_understanding": False
        }