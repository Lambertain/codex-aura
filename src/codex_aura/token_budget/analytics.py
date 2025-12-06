"""Budget analytics for token usage tracking."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from statistics import mean, median

from ..models.node import Node, RankedNode
from .counter import TokenCounter


@dataclass
class BudgetStats:
    """Statistics for budget allocation and usage."""

    total_tokens: int
    budget_used_pct: float
    nodes_included: int
    nodes_truncated: int
    nodes_excluded: int
    avg_node_tokens: float
    median_node_tokens: float
    token_savings: int  # Tokens saved vs naive approach
    truncation_rate: float  # Percentage of nodes that were truncated


class BudgetAnalytics:
    """Analytics for token budget usage and optimization."""

    def __init__(self, counter: TokenCounter = None):
        self.counter = counter or TokenCounter()
        self.usage_history: List[Dict[str, Any]] = []

    def analyze_allocation(
        self,
        original_nodes: List[RankedNode],
        selected_nodes: List[Node],
        max_tokens: int,
        strategy: str
    ) -> BudgetStats:
        """Analyze the results of budget allocation.

        Args:
            original_nodes: All available nodes before allocation
            selected_nodes: Nodes selected by the allocator
            max_tokens: Maximum token budget
            strategy: Allocation strategy used

        Returns:
            BudgetStats with comprehensive analytics
        """
        # Calculate token counts
        selected_tokens = sum(self.counter.count_node(node) for node in selected_nodes)
        original_tokens = sum(self.counter.count_node(node) for node in original_nodes)

        # Count different node types
        nodes_included = len(selected_nodes)
        nodes_excluded = len(original_nodes) - nodes_included

        # Count truncated nodes (simplified - nodes that are shorter than expected)
        nodes_truncated = 0
        node_token_counts = []

        for node in selected_nodes:
            tokens = self.counter.count_node(node)
            node_token_counts.append(tokens)

            # Consider node truncated if it's significantly shorter than average
            # This is a heuristic - in practice might need more sophisticated detection
            if tokens < 50:  # Very small nodes might be truncated
                nodes_truncated += 1

        # Calculate statistics
        budget_used_pct = (selected_tokens / max_tokens) * 100 if max_tokens > 0 else 0
        avg_node_tokens = mean(node_token_counts) if node_token_counts else 0
        median_node_tokens = median(node_token_counts) if node_token_counts else 0
        token_savings = original_tokens - selected_tokens
        truncation_rate = (nodes_truncated / nodes_included) * 100 if nodes_included > 0 else 0

        stats = BudgetStats(
            total_tokens=selected_tokens,
            budget_used_pct=round(budget_used_pct, 1),
            nodes_included=nodes_included,
            nodes_truncated=nodes_truncated,
            nodes_excluded=nodes_excluded,
            avg_node_tokens=round(avg_node_tokens, 1),
            median_node_tokens=round(median_node_tokens, 1),
            token_savings=token_savings,
            truncation_rate=round(truncation_rate, 1)
        )

        # Record in history
        self.usage_history.append({
            "strategy": strategy,
            "max_tokens": max_tokens,
            "stats": stats,
            "original_nodes": len(original_nodes),
            "selected_nodes": len(selected_nodes)
        })

        return stats

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get summary of budget usage across all allocations."""
        if not self.usage_history:
            return {
                "total_allocations": 0,
                "avg_budget_used_pct": 0,
                "avg_token_savings": 0,
                "total_truncated_nodes": 0,
                "strategies_used": []
            }

        total_allocations = len(self.usage_history)
        avg_budget_used = mean(h["stats"].budget_used_pct for h in self.usage_history)
        avg_savings = mean(h["stats"].token_savings for h in self.usage_history)
        total_truncated = sum(h["stats"].nodes_truncated for h in self.usage_history)
        strategies = list(set(h["strategy"] for h in self.usage_history))

        return {
            "total_allocations": total_allocations,
            "avg_budget_used_pct": round(avg_budget_used, 1),
            "avg_token_savings": round(avg_savings, 1),
            "total_truncated_nodes": total_truncated,
            "strategies_used": strategies
        }

    def get_strategy_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare performance across different allocation strategies."""
        strategy_stats = {}

        for history_item in self.usage_history:
            strategy = history_item["strategy"]
            stats = history_item["stats"]

            if strategy not in strategy_stats:
                strategy_stats[strategy] = {
                    "allocations": 0,
                    "avg_budget_used_pct": 0,
                    "avg_token_savings": 0,
                    "total_truncated": 0
                }

            s = strategy_stats[strategy]
            s["allocations"] += 1
            s["avg_budget_used_pct"] += stats.budget_used_pct
            s["avg_token_savings"] += stats.token_savings
            s["total_truncated"] += stats.nodes_truncated

        # Calculate averages
        for strategy, stats in strategy_stats.items():
            count = stats["allocations"]
            stats["avg_budget_used_pct"] = round(stats["avg_budget_used_pct"] / count, 1)
            stats["avg_token_savings"] = round(stats["avg_token_savings"] / count, 1)

        return strategy_stats

    def clear_history(self) -> None:
        """Clear usage history."""
        self.usage_history.clear()