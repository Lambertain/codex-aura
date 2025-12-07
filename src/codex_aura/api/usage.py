"""Usage telemetry API."""

from fastapi import APIRouter, Depends
from typing import Dict, Any

from ..api.middleware.auth import require_auth
from ..storage.usage_storage import UsageStorage
from ..billing.plans import PLAN_LIMITS
from ..billing.usage import UsageTracker

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/me")
async def get_my_usage(current_user=Depends(require_auth)) -> Dict[str, Any]:
    """Get current user's usage statistics."""
    usage_storage = UsageStorage()

    # Get current month usage
    current_usage = await usage_storage.get_current_month_usage(current_user.id)

    # Get plan limits
    limits = PLAN_LIMITS[current_user.plan_tier]

    # Calculate usage percentages
    usage_percent = {
        "requests_daily": (current_usage.total_requests / limits.requests_per_day) * 100 if limits.requests_per_day > 0 else 0,
        "requests_monthly": (current_usage.total_requests / limits.requests_per_month) * 100 if limits.requests_per_month > 0 else 0,
        "tokens": (current_usage.total_tokens / (limits.max_tokens_per_request * 1000)) * 100 if limits.max_tokens_per_request > 0 else 0,  # Rough estimate
    }

    return {
        "current_period": {
            "total_requests": current_usage.total_requests,
            "total_tokens": current_usage.total_tokens,
            "context_requests": current_usage.context_requests,
            "semantic_searches": current_usage.semantic_searches,
            "sync_events": current_usage.sync_events,
            "repos_count": current_usage.repos_count,
            "period_start": current_usage.period_start,
            "period_end": current_usage.period_end,
        },
        "limits": {
            "requests_per_day": limits.requests_per_day,
            "requests_per_month": limits.requests_per_month,
            "max_tokens_per_request": limits.max_tokens_per_request,
            "repos": limits.repos,
        },
        "usage_percent": usage_percent,
        "plan": current_user.plan_tier.value
    }


@router.get("/stats")
async def get_usage_stats(current_user=Depends(require_auth)):
    """Get detailed usage statistics for dashboard."""
    usage_storage = UsageStorage()
    usage_tracker = UsageTracker(None, None)  # Simplified - would need proper Redis/DB setup

    # Get current usage from Redis (fast)
    daily_usage = await usage_tracker.get_usage(current_user.id, "day")
    monthly_usage = await usage_tracker.get_usage(current_user.id, "month")

    # Get aggregated data from DB
    aggregated = await usage_storage.get_current_month_usage(current_user.id)

    return {
        "daily": daily_usage,
        "monthly": monthly_usage,
        "aggregated": {
            "total_requests": aggregated.total_requests,
            "total_tokens": aggregated.total_tokens,
            "context_requests": aggregated.context_requests,
            "semantic_searches": aggregated.semantic_searches,
            "sync_events": aggregated.sync_events,
        }
    }