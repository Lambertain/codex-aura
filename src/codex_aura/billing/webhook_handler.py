"""Stripe webhook handlers for billing events."""

import logging
from datetime import datetime
from typing import Optional

from ..billing.plans import STRIPE_PRICES, PlanTier
from ..storage.user_storage import UserStorage
from ..models.user import User

logger = logging.getLogger(__name__)


class StripeWebhookHandler:
    """Handle Stripe webhook events."""

    def __init__(self, user_storage: UserStorage):
        self.user_storage = user_storage

    async def handle_invoice_paid(self, event_data: dict):
        """Handle invoice.paid webhook."""
        invoice = event_data
        customer_id = invoice.get("customer")

        if not customer_id:
            logger.error("Invoice paid event missing customer ID")
            return

        # Find user by Stripe customer ID
        user = await self._get_user_by_customer_id(customer_id)
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        # Update subscription status if needed
        subscription_id = invoice.get("subscription")
        if subscription_id:
            await self._update_subscription_status(user.id, subscription_id, "active")

        logger.info(f"Processed invoice payment for user {user.id}")

    async def handle_customer_subscription_updated(self, event_data: dict):
        """Handle customer.subscription.updated webhook."""
        subscription = event_data
        customer_id = subscription.get("customer")
        subscription_id = subscription.get("id")
        status = subscription.get("status")

        if not customer_id:
            logger.error("Subscription updated event missing customer ID")
            return

        # Find user by Stripe customer ID
        user = await self._get_user_by_customer_id(customer_id)
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        # Determine plan tier from price ID
        plan_tier = await self._get_plan_from_subscription(subscription)

        # Update user subscription
        current_period_end = None
        if subscription.get("current_period_end"):
            current_period_end = datetime.fromtimestamp(subscription["current_period_end"])

        await self.user_storage.update_user_plan(
            user_id=user.id,
            plan_tier=plan_tier,
            subscription_id=subscription_id,
            subscription_status=status,
            current_period_end=current_period_end
        )

        logger.info(f"Updated subscription for user {user.id} to plan {plan_tier.value}")

    async def handle_customer_subscription_deleted(self, event_data: dict):
        """Handle customer.subscription.deleted webhook."""
        subscription = event_data
        customer_id = subscription.get("customer")

        if not customer_id:
            logger.error("Subscription deleted event missing customer ID")
            return

        # Find user by Stripe customer ID
        user = await self._get_user_by_customer_id(customer_id)
        if not user:
            logger.error(f"User not found for customer {customer_id}")
            return

        # Downgrade to free plan
        await self.user_storage.update_user_plan(
            user_id=user.id,
            plan_tier=PlanTier.FREE,
            subscription_id=None,
            subscription_status=None,
            current_period_end=None
        )

        logger.info(f"Downgraded user {user.id} to free plan due to subscription cancellation")

    async def _get_user_by_customer_id(self, customer_id: str) -> Optional[User]:
        """Find user by Stripe customer ID."""
        # This would need to be implemented in UserStorage
        # For now, we'll assume we have a method to find by customer ID
        # In practice, you might need to add this method to UserStorage
        async with self.user_storage._get_connection() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM users WHERE stripe_customer_id = $1
            """, customer_id)

            if row:
                return User(**row)

        return None

    async def _get_plan_from_subscription(self, subscription: dict) -> PlanTier:
        """Determine plan tier from subscription price ID."""
        items = subscription.get("items", {}).get("data", [])
        if not items:
            return PlanTier.FREE

        price_id = items[0].get("price", {}).get("id")
        if not price_id:
            return PlanTier.FREE

        # Reverse lookup from STRIPE_PRICES
        for plan_tier, stripe_price_id in STRIPE_PRICES.items():
            if stripe_price_id == price_id:
                return plan_tier

        return PlanTier.FREE

    async def _update_subscription_status(
        self,
        user_id: str,
        subscription_id: str,
        status: str
    ):
        """Update subscription status for user."""
        # This could be added to UserStorage if needed
        async with self.user_storage._get_connection() as conn:
            await conn.execute("""
                UPDATE users SET
                    subscription_status = $2,
                    updated_at = NOW()
                WHERE id = $1
            """, user_id, status)