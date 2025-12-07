"""PostgreSQL storage for usage telemetry."""

import asyncpg
from typing import List, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from ..models.usage import UsageEvent, AggregatedUsage
from ..config.settings import settings


class UsageStorage:
    """PostgreSQL storage for usage data."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or settings.postgres_url

    @asynccontextmanager
    async def connection(self):
        """Get database connection."""
        conn = await asyncpg.connect(self.connection_string)
        try:
            yield conn
        finally:
            await conn.close()

    async def create_tables(self):
        """Create usage tables."""
        async with self.connection() as conn:
            # Usage events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    endpoint VARCHAR(255),
                    tokens_used INTEGER,
                    metadata JSONB,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_usage_events_user_timestamp
                ON usage_events (user_id, timestamp);

                CREATE INDEX IF NOT EXISTS idx_usage_events_type
                ON usage_events (event_type);
            """)

            # Aggregated usage table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_usage (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
                    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
                    total_requests INTEGER DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    context_requests INTEGER DEFAULT 0,
                    semantic_searches INTEGER DEFAULT 0,
                    sync_events INTEGER DEFAULT 0,
                    repos_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(user_id, period_start, period_end)
                );

                CREATE INDEX IF NOT EXISTS idx_aggregated_usage_user_period
                ON aggregated_usage (user_id, period_start, period_end);
            """)

    async def insert_usage_event(self, event: UsageEvent):
        """Insert usage event."""
        async with self.connection() as conn:
            await conn.execute("""
                INSERT INTO usage_events
                (user_id, event_type, endpoint, tokens_used, metadata, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, event.user_id, event.event_type, event.endpoint,
                event.tokens_used, event.metadata, event.timestamp)

    async def get_aggregated_usage(
        self,
        user_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[AggregatedUsage]:
        """Get aggregated usage for period."""
        async with self.connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM aggregated_usage
                WHERE user_id = $1 AND period_start = $2 AND period_end = $3
            """, user_id, period_start, period_end)

            if row:
                return AggregatedUsage(**row)

        return None

    async def upsert_aggregated_usage(self, usage: AggregatedUsage):
        """Insert or update aggregated usage."""
        async with self.connection() as conn:
            await conn.execute("""
                INSERT INTO aggregated_usage
                (user_id, period_start, period_end, total_requests, total_tokens,
                 context_requests, semantic_searches, sync_events, repos_count, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                ON CONFLICT (user_id, period_start, period_end)
                DO UPDATE SET
                    total_requests = EXCLUDED.total_requests,
                    total_tokens = EXCLUDED.total_tokens,
                    context_requests = EXCLUDED.context_requests,
                    semantic_searches = EXCLUDED.semantic_searches,
                    sync_events = EXCLUDED.sync_events,
                    repos_count = EXCLUDED.repos_count,
                    updated_at = NOW()
            """, usage.user_id, usage.period_start, usage.period_end,
                usage.total_requests, usage.total_tokens, usage.context_requests,
                usage.semantic_searches, usage.sync_events, usage.repos_count)

    async def aggregate_usage_for_period(
        self,
        user_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> AggregatedUsage:
        """Aggregate usage events for a period."""
        async with self.connection() as conn:
            # Get aggregated data from events
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_requests,
                    COALESCE(SUM(tokens_used), 0) as total_tokens,
                    COUNT(CASE WHEN event_type = 'context_request' THEN 1 END) as context_requests,
                    COUNT(CASE WHEN event_type = 'semantic_search' THEN 1 END) as semantic_searches,
                    COUNT(CASE WHEN event_type = 'sync_event' THEN 1 END) as sync_events
                FROM usage_events
                WHERE user_id = $1 AND timestamp >= $2 AND timestamp < $3
            """, user_id, period_start, period_end)

            # Get current repos count (simplified - would need actual repo counting logic)
            repos_count = 0  # TODO: implement repo counting

            usage = AggregatedUsage(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
                total_requests=row['total_requests'],
                total_tokens=row['total_tokens'],
                context_requests=row['context_requests'],
                semantic_searches=row['semantic_searches'],
                sync_events=row['sync_events'],
                repos_count=repos_count
            )

            # Save aggregated data
            await self.upsert_aggregated_usage(usage)

            return usage

    async def get_current_month_usage(self, user_id: str) -> AggregatedUsage:
        """Get current month aggregated usage."""
        now = datetime.utcnow()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = (period_start + timedelta(days=32)).replace(day=1)

        # Try to get existing aggregated data
        usage = await self.get_aggregated_usage(user_id, period_start, period_end)
        if usage:
            return usage

        # Aggregate from events if not exists
        return await self.aggregate_usage_for_period(user_id, period_start, period_end)