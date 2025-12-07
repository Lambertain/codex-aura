"""Usage models for telemetry and billing."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class UsageEvent(BaseModel):
    """Individual usage event."""

    user_id: str
    event_type: str  # 'context_request', 'semantic_search', 'sync_event'
    endpoint: Optional[str] = None
    tokens_used: Optional[int] = None
    metadata: Optional[dict] = None
    timestamp: datetime = datetime.utcnow()


class AggregatedUsage(BaseModel):
    """Aggregated usage for a user in a time period."""

    user_id: str
    period_start: datetime
    period_end: datetime
    total_requests: int = 0
    total_tokens: int = 0
    context_requests: int = 0
    semantic_searches: int = 0
    sync_events: int = 0
    repos_count: int = 0
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()


class UsageStats(BaseModel):
    """Usage statistics for API response."""

    current_period: AggregatedUsage
    previous_period: Optional[AggregatedUsage] = None
    limits: dict
    usage_percent: dict  # percentage of limits used