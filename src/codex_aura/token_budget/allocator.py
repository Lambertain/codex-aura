from dataclasses import dataclass
from enum import Enum
from typing import Callable

from ..models.node import Node, RankedNode
from .counter import TokenCounter, ModelName


class AllocationStrategy(str, Enum):
    GREEDY = "greedy"           # Take highest-scored until budget exhausted
    PROPORTIONAL = "proportional"  # Allocate proportionally to scores
    KNAPSACK = "knapsack"       # Optimal 0/1 knapsack
    ADAPTIVE = "adaptive"       # Smart mix based on context


@dataclass
class AllocationResult:
    selected_nodes: list[RankedNode]
    total_tokens: int
    budget_used_pct: float
    nodes_included: int
    nodes_truncated: int
    nodes_excluded: int
    strategy_used: AllocationStrategy


class BudgetAllocator:
    """
    Allocate token budget across ranked nodes.

    Implements multiple strategies for different use cases:
    - GREEDY: Fast, good for most cases
    - PROPORTIONAL: Fair distribution
    - KNAPSACK: Optimal but slower
    - ADAPTIVE: Automatically chooses best strategy
    """

    def __init__(self, token_counter: TokenCounter):
        self.counter = token_counter

    def allocate(
        self,
        nodes: list[RankedNode],
        max_tokens: int,
        strategy: AllocationStrategy = AllocationStrategy.ADAPTIVE,
        model: ModelName = "gpt-4",
        reserve_tokens: int = 500  # Reserve for prompt overhead
    ) -> AllocationResult:
        """
        Select nodes to include within token budget.

        Args:
            nodes: Ranked nodes with scores
            max_tokens: Maximum tokens allowed
            strategy: Allocation strategy to use
            model: Target LLM model
            reserve_tokens: Tokens to reserve for system prompt

        Returns:
            AllocationResult with selected nodes and stats
        """
        available_budget = max_tokens - reserve_tokens

        if not nodes:
            return AllocationResult(
                selected_nodes=[],
                total_tokens=0,
                budget_used_pct=0.0,
                nodes_included=0,
                nodes_truncated=0,
                nodes_excluded=0,
                strategy_used=strategy
            )

        # Pre-compute token counts if not already done
        for node in nodes:
            if not hasattr(node, 'tokens') or node.tokens == 0:
                node.tokens = self.counter.count_node(node, model)

        # Select strategy
        if strategy == AllocationStrategy.ADAPTIVE:
            strategy = self._select_adaptive_strategy(nodes, available_budget)

        # Execute strategy
        if strategy == AllocationStrategy.GREEDY:
            selected = self._greedy_allocate(nodes, available_budget)
        elif strategy == AllocationStrategy.PROPORTIONAL:
            selected = self._proportional_allocate(nodes, available_budget)
        elif strategy == AllocationStrategy.KNAPSACK:
            selected = self._knapsack_allocate(nodes, available_budget)
        else:
            selected = self._greedy_allocate(nodes, available_budget)

        # Calculate stats
        total_tokens = sum(n.tokens for n in selected)

        return AllocationResult(
            selected_nodes=selected,
            total_tokens=total_tokens,
            budget_used_pct=round(total_tokens / available_budget * 100, 1),
            nodes_included=len(selected),
            nodes_truncated=0,  # TODO: track truncated
            nodes_excluded=len(nodes) - len(selected),
            strategy_used=strategy
        )

    def _greedy_allocate(
        self,
        nodes: list[RankedNode],
        budget: int
    ) -> list[RankedNode]:
        """
        Greedy allocation: take highest-scored nodes until budget exhausted.

        Time: O(n log n) for sorting
        """
        # Sort by score descending
        sorted_nodes = sorted(nodes, key=lambda n: n.score, reverse=True)

        selected = []
        used_tokens = 0

        for node in sorted_nodes:
            if used_tokens + node.tokens <= budget:
                selected.append(node)
                used_tokens += node.tokens
            elif used_tokens == 0 and node.tokens > budget:
                # First node too big - must include something
                # Truncate it to fit
                truncated = self._truncate_node(node, budget)
                selected.append(truncated)
                break

        return selected

    def _proportional_allocate(
        self,
        nodes: list[RankedNode],
        budget: int
    ) -> list[RankedNode]:
        """
        Proportional allocation: distribute budget based on scores.

        Each node gets budget proportional to its score.
        """
        total_score = sum(n.score for n in nodes)
        if total_score == 0:
            return self._greedy_allocate(nodes, budget)

        selected = []

        for node in nodes:
            # Calculate proportional budget for this node
            node_budget = int(budget * (node.score / total_score))

            if node.tokens <= node_budget:
                selected.append(node)
            elif node_budget > 100:  # Minimum useful size
                truncated = self._truncate_node(node, node_budget)
                selected.append(truncated)

        return selected

    def _knapsack_allocate(
        self,
        nodes: list[RankedNode],
        budget: int
    ) -> list[RankedNode]:
        """
        0/1 Knapsack optimal allocation.

        Maximizes total score within budget.
        Time: O(n * budget) - can be slow for large budgets.
        """
        n = len(nodes)

        # Scale down budget for DP if too large
        scale = 1
        if budget > 10000:
            scale = budget // 10000
            budget = budget // scale
            for node in nodes:
                node.tokens = node.tokens // scale

        # DP table
        dp = [[0.0] * (budget + 1) for _ in range(n + 1)]

        for i in range(1, n + 1):
            node = nodes[i - 1]
            for w in range(budget + 1):
                # Don't take this node
                dp[i][w] = dp[i - 1][w]

                # Take this node (if it fits)
                if node.tokens <= w:
                    take_value = dp[i - 1][w - node.tokens] + node.score
                    dp[i][w] = max(dp[i][w], take_value)

        # Backtrack to find selected nodes
        selected = []
        w = budget
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected.append(nodes[i - 1])
                w -= nodes[i - 1].tokens

        # Restore scale
        if scale > 1:
            for node in nodes:
                node.tokens = node.tokens * scale

        return selected

    def _select_adaptive_strategy(
        self,
        nodes: list[RankedNode],
        budget: int
    ) -> AllocationStrategy:
        """Select best strategy based on input characteristics."""
        n = len(nodes)
        total_tokens = sum(n.tokens for n in nodes)

        # If total fits, greedy is fine
        if total_tokens <= budget:
            return AllocationStrategy.GREEDY

        # If many nodes and large budget, use greedy (knapsack too slow)
        if n > 100 or budget > 50000:
            return AllocationStrategy.GREEDY

        # If scores are uniform, proportional might be better
        scores = [n.score for n in nodes]
        score_variance = self._variance(scores)
        if score_variance < 0.1:
            return AllocationStrategy.PROPORTIONAL

        # Default to knapsack for optimal results
        return AllocationStrategy.KNAPSACK

    def _truncate_node(self, node: RankedNode, max_tokens: int) -> RankedNode:
        """Truncate node content to fit token budget."""
        truncated_content = self.counter.truncate_to_tokens(
            node.content or "",
            max_tokens - 50  # Reserve for metadata
        )

        # Create a copy of the node with truncated content
        truncated_node = RankedNode(
            id=node.id,
            type=node.type,
            name=node.name,
            path=node.path,
            content=truncated_content + "\n# ... truncated ...",
            lines=node.lines,
            docstring=node.docstring,
            blame=node.blame,
            score=node.score
        )
        truncated_node.tokens = max_tokens

        return truncated_node

    @staticmethod
    def _variance(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)