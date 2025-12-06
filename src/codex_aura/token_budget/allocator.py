"""Budget allocation algorithms for token management."""

from typing import List

from ..models.node import Node, RankedNode
from .counter import TokenCounter


class BudgetAllocator:
    """Allocates tokens between nodes within budget constraints."""

    def __init__(self, counter: TokenCounter = None):
        self.counter = counter or TokenCounter()

    def allocate(
        self,
        nodes: List[RankedNode],
        max_tokens: int,
        strategy: str = "greedy"
    ) -> List[Node]:
        """Select nodes within token budget."""
        if strategy == "greedy":
            return self._greedy_allocation(nodes, max_tokens)
        elif strategy == "proportional":
            return self._proportional_allocation(nodes, max_tokens)
        elif strategy == "knapsack":
            return self._knapsack_allocation(nodes, max_tokens)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def _greedy_allocation(
        self,
        nodes: List[RankedNode],
        max_tokens: int
    ) -> List[Node]:
        """Take highest-scored nodes until budget exhausted."""
        selected = []
        used_tokens = 0

        for node in sorted(nodes, key=lambda n: n.score, reverse=True):
            node_tokens = self.counter.count_node(node)
            if used_tokens + node_tokens <= max_tokens:
                selected.append(node)
                used_tokens += node_tokens
            elif used_tokens == 0:
                # First node too big - truncate it
                selected.append(self._truncate_node(node, max_tokens))
                break

        return selected

    def _proportional_allocation(
        self,
        nodes: List[RankedNode],
        max_tokens: int
    ) -> List[Node]:
        """Allocate proportionally based on scores."""
        if not nodes:
            return []

        total_score = sum(node.score for node in nodes)
        if total_score == 0:
            return []

        selected = []
        used_tokens = 0

        # Sort by score descending for priority
        sorted_nodes = sorted(nodes, key=lambda n: n.score, reverse=True)

        for node in sorted_nodes:
            # Calculate proportional allocation
            proportion = node.score / total_score
            allocated_tokens = int(max_tokens * proportion)

            if allocated_tokens > 0:
                node_tokens = self.counter.count_node(node)
                if node_tokens <= allocated_tokens and used_tokens + node_tokens <= max_tokens:
                    selected.append(node)
                    used_tokens += node_tokens

        return selected

    def _knapsack_allocation(
        self,
        nodes: List[RankedNode],
        max_tokens: int
    ) -> List[Node]:
        """Optimal knapsack-style allocation."""
        if not nodes:
            return []

        # Dynamic programming approach
        n = len(nodes)
        dp = [[0 for _ in range(max_tokens + 1)] for _ in range(n + 1)]
        selected_items = [[[] for _ in range(max_tokens + 1)] for _ in range(n + 1)]

        for i in range(1, n + 1):
            node = nodes[i - 1]
            weight = self.counter.count_node(node)
            value = node.score

            for w in range(max_tokens + 1):
                if weight <= w:
                    if dp[i - 1][w - weight] + value > dp[i - 1][w]:
                        dp[i][w] = dp[i - 1][w - weight] + value
                        selected_items[i][w] = selected_items[i - 1][w - weight] + [node]
                    else:
                        dp[i][w] = dp[i - 1][w]
                        selected_items[i][w] = selected_items[i - 1][w]
                else:
                    dp[i][w] = dp[i - 1][w]
                    selected_items[i][w] = selected_items[i - 1][w]

        return selected_items[n][max_tokens]

    def _truncate_node(self, node: RankedNode, max_tokens: int) -> Node:
        """Truncate node content to fit within token limit."""
        # This is a simplified truncation - in practice might need more sophisticated approach
        signature = getattr(node, 'signature', '')
        content = getattr(node, 'content', '')

        # Try to fit signature first
        sig_tokens = self.counter.count(signature)
        if sig_tokens >= max_tokens:
            # Even signature is too big - truncate it
            truncated_sig = self._truncate_text(signature, max_tokens)
            # Create a new node-like object with truncated content
            truncated_node = Node(
                id=node.id,
                type=node.type,
                name=node.name,
                path=node.path,
                lines=node.lines,
                docstring=node.docstring,
                blame=node.blame
            )
            setattr(truncated_node, 'signature', truncated_sig)
            setattr(truncated_node, 'content', '')
            return truncated_node

        # Fit as much content as possible
        remaining_tokens = max_tokens - sig_tokens
        truncated_content = self._truncate_text(content, remaining_tokens)

        truncated_node = Node(
            id=node.id,
            type=node.type,
            name=node.name,
            path=node.path,
            lines=node.lines,
            docstring=node.docstring,
            blame=node.blame
        )
        setattr(truncated_node, 'signature', signature)
        setattr(truncated_node, 'content', truncated_content)
        return truncated_node

    def _truncate_text(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit."""
        if self.counter.count(text) <= max_tokens:
            return text

        # Binary search for the right length
        left, right = 0, len(text)
        while left < right:
            mid = (left + right + 1) // 2
            if self.counter.count(text[:mid]) <= max_tokens:
                left = mid
            else:
                right = mid - 1

        return text[:left]