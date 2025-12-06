"""Usage metering and tracking for billing."""

from datetime import datetime, timedelta
from typing import Optional
from redis.asyncio import Redis

from ..billing.plans import PLAN_LIMITS, PlanTier
from ..storage.sqlite import SQLiteStorage


class UsageTracker:
    """Track API usage for billing and rate limiting."""

    def __init__(self, redis: Redis, db: SQLiteStorage):
        self.redis = redis
        self.db = db

    async def record_request(
        self,
        user_id: str,
        endpoint: str,
        tokens_used: int
    ):
        """Record API request for usage tracking."""
        now = datetime.utcnow()
        day_key = f"usage:{user_id}:{now.strftime('%Y-%m-%d')}"
        month_key = f"usage:{user_id}:{now.strftime('%Y-%m')}"

        # Increment daily counter
        await self.redis.hincrby(day_key, "requests", 1)
        await self.redis.hincrby(day_key, "tokens", tokens_used)
        await self.redis.expire(day_key, 86400 * 7)  # Keep 7 days

        # Increment monthly counter
        await self.redis.hincrby(month_key, "requests", 1)
        await self.redis.hincrby(month_key, "tokens", tokens_used)
        await self.redis.expire(month_key, 86400 * 35)  # Keep 35 days

        # Async write to DB for permanent storage
        await self.db.insert_usage_event(
            user_id=user_id,
            endpoint=endpoint,
            tokens_used=tokens_used,
            timestamp=now
        )

    async def get_usage(self, user_id: str, period: str = "day") -> dict:
        """Get usage for period."""
        now = datetime.utcnow()

        if period == "day":
            key = f"usage:{user_id}:{now.strftime('%Y-%m-%d')}"
        else:
            key = f"usage:{user_id}:{now.strftime('%Y-%m')}"

        data = await self.redis.hgetall(key)
        return {
            "requests": int(data.get("requests", 0)),
            "tokens": int(data.get("tokens", 0))
        }

    async def check_limits(self, user_id: str, plan: PlanTier) -> tuple[bool, str]:
        """Check if user is within plan limits."""
        limits = PLAN_LIMITS[plan]

        daily_usage = await self.get_usage(user_id, "day")
        monthly_usage = await self.get_usage(user_id, "month")

        if limits.requests_per_day != -1 and daily_usage["requests"] >= limits.requests_per_day:
            return False, "Daily request limit reached"

        if limits.requests_per_month != -1 and monthly_usage["requests"] >= limits.requests_per_month:
            return False, "Monthly request limit reached"

        return True, ""