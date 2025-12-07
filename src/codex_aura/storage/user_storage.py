"""PostgreSQL storage for user data and billing."""

import asyncpg
from typing import Optional
from datetime import datetime

from ..models.user import User
from ..billing.plans import PlanTier
from ..config.settings import settings


class UserStorage:
    """PostgreSQL storage for users."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or settings.postgres_url

    async def create_tables(self):
        """Create user tables."""
        async with self._get_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id VARCHAR(255) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    stripe_customer_id VARCHAR(255),
                    plan_tier VARCHAR(50) DEFAULT 'free',
                    subscription_id VARCHAR(255),
                    subscription_status VARCHAR(50),
                    current_period_end TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
                CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON users (stripe_customer_id);
            """)

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        async with self._get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM users WHERE id = $1
            """, user_id)

            if row:
                return User(**row)

        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        async with self._get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM users WHERE email = $1
            """, email)

            if row:
                return User(**row)

        return None

    async def create_user(self, user: User) -> User:
        """Create new user."""
        async with self._get_connection() as conn:
            row = await conn.fetchrow("""
                INSERT INTO users
                (id, email, name, stripe_customer_id, plan_tier, subscription_id,
                 subscription_status, current_period_end, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """, user.id, user.email, user.name, user.stripe_customer_id,
                user.plan_tier.value, user.subscription_id, user.subscription_status,
                user.current_period_end, user.created_at, user.updated_at)

            return User(**row)

    async def update_user(self, user: User) -> User:
        """Update user."""
        user.updated_at = datetime.utcnow()

        async with self._get_connection() as conn:
            row = await conn.fetchrow("""
                UPDATE users SET
                    email = $2,
                    name = $3,
                    stripe_customer_id = $4,
                    plan_tier = $5,
                    subscription_id = $6,
                    subscription_status = $7,
                    current_period_end = $8,
                    updated_at = $9
                WHERE id = $1
                RETURNING *
            """, user.id, user.email, user.name, user.stripe_customer_id,
                user.plan_tier.value, user.subscription_id, user.subscription_status,
                user.current_period_end, user.updated_at)

            return User(**row)

    async def update_user_plan(
        self,
        user_id: str,
        plan_tier: PlanTier,
        subscription_id: Optional[str] = None,
        subscription_status: Optional[str] = None,
        current_period_end: Optional[datetime] = None
    ) -> Optional[User]:
        """Update user plan and subscription info."""
        async with self._get_connection() as conn:
            row = await conn.fetchrow("""
                UPDATE users SET
                    plan_tier = $2,
                    subscription_id = $3,
                    subscription_status = $4,
                    current_period_end = $5,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """, user_id, plan_tier.value, subscription_id, subscription_status, current_period_end)

            if row:
                return User(**row)

        return None

    async def update_stripe_customer(self, user_id: str, customer_id: str) -> Optional[User]:
        """Update Stripe customer ID."""
        async with self._get_connection() as conn:
            row = await conn.fetchrow("""
                UPDATE users SET
                    stripe_customer_id = $2,
                    updated_at = NOW()
                WHERE id = $1
                RETURNING *
            """, user_id, customer_id)

            if row:
                return User(**row)

        return None

    async def get_users_by_plan(self, plan_tier: PlanTier) -> list[User]:
        """Get all users with specific plan."""
        async with self._get_connection() as conn:
            rows = await conn.fetch("""
                SELECT * FROM users WHERE plan_tier = $1
            """, plan_tier.value)

            return [User(**row) for row in rows]

    async def _get_connection(self):
        """Get database connection."""
        return await asyncpg.connect(self.connection_string)