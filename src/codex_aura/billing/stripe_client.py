import stripe
from pydantic import BaseModel

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeClient:
    """Stripe integration for billing."""
    
    async def create_customer(self, user: User) -> str:
        """Create Stripe customer for user."""
        customer = stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"user_id": user.id}
        )
        return customer.id
    
    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str
    ) -> str:
        """Create Checkout session for subscription."""
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            allow_promotion_codes=True
        )
        return session.url
    
    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> str:
        """Create Customer Portal session for managing subscription."""
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        return session.url
    
    async def get_subscription(self, subscription_id: str) -> dict:
        """Get subscription details."""
        return stripe.Subscription.retrieve(subscription_id)
    
    async def cancel_subscription(self, subscription_id: str):
        """Cancel subscription at period end."""
        stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )