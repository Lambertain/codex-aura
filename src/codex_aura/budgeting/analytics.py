"""Budget analytics service for tracking token usage patterns."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from collections import Counter

from ..token_budget.allocator import AllocationResult


@dataclass
class BudgetAnalytics:
    """Analytics data for budget usage over a time period."""
    period: str  # "day", "week", "month"
    total_requests: int
    avg_budget_used_pct: float
    avg_nodes_included: int
    avg_nodes_excluded: int
    total_tokens_saved: int  # vs naive approach
    tokens_saved_pct: float
    strategy_distribution: Dict[str, int]  # strategy -> count


@dataclass
class BudgetEvent:
    """Single budget allocation event."""
    repo_id: str
    user_id: str
    budget_requested: int
    budget_used: int
    budget_used_pct: float
    nodes_included: int
    nodes_excluded: int
    strategy: str
    timestamp: datetime


class BudgetAnalyticsService:
    """Track and analyze token budget usage."""

    def __init__(self, db=None):
        self.db = db  # Will be injected
        self._events: List[BudgetEvent] = []  # In-memory storage for now

    async def record_allocation(
        self,
        repo_id: str,
        user_id: str,
        result: AllocationResult
    ):
        """Record allocation for analytics."""
        event = BudgetEvent(
            repo_id=repo_id,
            user_id=user_id,
            budget_requested=result.total_tokens,
            budget_used=result.total_tokens,
            budget_used_pct=result.budget_used_pct,
            nodes_included=result.nodes_included,
            nodes_excluded=result.nodes_excluded,
            strategy=result.strategy_used.value,
            timestamp=datetime.now(timezone.utc)
        )

        # Store in memory for now (in production, use database)
        self._events.append(event)

        # If db is available, also store there
        if self.db and hasattr(self.db, 'insert_budget_event'):
            await self.db.insert_budget_event(
                repo_id=repo_id,
                user_id=user_id,
                budget_requested=result.total_tokens,
                budget_used=result.total_tokens,
                budget_used_pct=result.budget_used_pct,
                nodes_included=result.nodes_included,
                nodes_excluded=result.nodes_excluded,
                strategy=result.strategy_used.value,
                timestamp=datetime.now(timezone.utc)
            )

    async def get_analytics(
        self,
        user_id: str,
        period: str = "week"
    ) -> BudgetAnalytics:
        """Get budget analytics for user."""
        since = self._get_period_start(period)
        events = self._get_budget_events(user_id, since)

        if not events:
            return BudgetAnalytics(
                period=period,
                total_requests=0,
                avg_budget_used_pct=0.0,
                avg_nodes_included=0,
                avg_nodes_excluded=0,
                total_tokens_saved=0,
                tokens_saved_pct=0.0,
                strategy_distribution={}
            )

        # Calculate naive tokens (what it would be without budgeting)
        # Assume 3x more tokens without smart selection
        naive_tokens = sum(e.budget_used * 3 for e in events)
        actual_tokens = sum(e.budget_used for e in events)
        tokens_saved = naive_tokens - actual_tokens

        return BudgetAnalytics(
            period=period,
            total_requests=len(events),
            avg_budget_used_pct=sum(e.budget_used_pct for e in events) / len(events),
            avg_nodes_included=sum(e.nodes_included for e in events) / len(events),
            avg_nodes_excluded=sum(e.nodes_excluded for e in events) / len(events),
            total_tokens_saved=tokens_saved,
            tokens_saved_pct=round(tokens_saved / naive_tokens * 100, 1) if naive_tokens > 0 else 0.0,
            strategy_distribution=dict(Counter(e.strategy for e in events))
        )

    def _get_period_start(self, period: str) -> datetime:
        """Get start datetime for the given period."""
        now = datetime.now(timezone.utc)

        if period == "day":
            return now - timedelta(days=1)
        elif period == "week":
            return now - timedelta(weeks=1)
        elif period == "month":
            return now - timedelta(days=30)
        else:
            raise ValueError(f"Invalid period: {period}")

    def _get_budget_events(self, user_id: str, since: datetime) -> List[BudgetEvent]:
        """Get budget events for user since given time."""
        # Filter in-memory events
        events = [
            e for e in self._events
            if e.user_id == user_id and e.timestamp >= since
        ]

        # If db is available, also get from there
        if self.db and hasattr(self.db, 'get_budget_events'):
            # In production, this would be async database query
            pass

        return events

    async def get_usage_summary(self, user_id: str) -> Dict[str, Any]:
        """Get overall usage summary for user."""
        all_events = [e for e in self._events if e.user_id == user_id]

        if not all_events:
            return {
                "total_requests": 0,
                "total_tokens_used": 0,
                "avg_budget_efficiency": 0.0,
                "most_used_strategy": None,
                "periods_analyzed": {}
            }

        total_tokens = sum(e.budget_used for e in all_events)
        avg_efficiency = sum(e.budget_used_pct for e in all_events) / len(all_events)
        strategy_counts = Counter(e.strategy for e in all_events)
        most_used_strategy = strategy_counts.most_common(1)[0][0] if strategy_counts else None

        # Group by periods
        periods = {}
        for period in ["day", "week", "month"]:
            since = self._get_period_start(period)
            period_events = [e for e in all_events if e.timestamp >= since]
            if period_events:
                periods[period] = await self.get_analytics(user_id, period)

        return {
            "total_requests": len(all_events),
            "total_tokens_used": total_tokens,
            "avg_budget_efficiency": round(avg_efficiency, 1),
            "most_used_strategy": most_used_strategy,
            "periods_analyzed": periods
        }