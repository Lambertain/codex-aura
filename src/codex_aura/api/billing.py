"""Billing API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..billing.plans import PLAN_LIMITS, PlanTier, STRIPE_PRICES
from ..billing.stripe_client import StripeClient
from ..billing.webhook_handler import StripeWebhookHandler
from ..storage.user_storage import UserStorage
from ..models.user import User
from ..api.middleware.auth import require_auth

router = APIRouter(prefix="/billing", tags=["billing"])

class CheckoutRequest(BaseModel):
    plan_tier: PlanTier

class PortalRequest(BaseModel):
    return_url: str

@router.get("/plans")
async def get_plans():
    """Get available plans."""
    return {
        tier.value: {
            "limits": limits.model_dump(),
            "price_id": STRIPE_PRICES.get(tier)
        }
        for tier, limits in PLAN_LIMITS.items()
    }

@router.post("/checkout")
async def create_checkout_session(
    request: CheckoutRequest,
    user: User = Depends(get_current_user)
):
    """Create Stripe checkout session."""
    if request.plan_tier not in STRIPE_PRICES:
        raise HTTPException(status_code=400, detail="Invalid plan tier")

    client = StripeClient()

    # Create or get customer
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer_id = await client.create_customer(user)

    # Create checkout session
    price_id = STRIPE_PRICES[request.plan_tier]
    session_url = await client.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url="http://localhost:3000/success",
        cancel_url="http://localhost:3000/cancel"
    )

    return {"checkout_url": session_url}

@router.post("/portal")
async def create_portal_session(
    request: PortalRequest,
    user: User = Depends(get_current_user)
):
    """Create Stripe customer portal session."""
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")

    client = StripeClient()
    portal_url = await client.create_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=request.return_url
    )

    return {"portal_url": portal_url}

@router.get("/me")
async def get_current_plan(current_user=Depends(require_auth)):
    """Get current user's billing plan and limits."""
    limits = PLAN_LIMITS[current_user.plan_tier]

    return {
        "plan": current_user.plan_tier.value,
        "limits": limits.model_dump(),
        "subscription_status": current_user.subscription_status,
        "current_period_end": current_user.current_period_end,
        "stripe_customer_id": current_user.stripe_customer_id
    }

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks."""
    from ..config.settings import settings

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        # Verify webhook signature
        stripe_client = StripeClient()
        event = stripe_client.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )

        # Handle event
        user_storage = UserStorage()
        handler = StripeWebhookHandler(user_storage)

        if event.type == "invoice.payment_succeeded":
            await handler.handle_invoice_paid(event.data.object)
        elif event.type == "customer.subscription.updated":
            await handler.handle_customer_subscription_updated(event.data.object)
        elif event.type == "customer.subscription.deleted":
            await handler.handle_customer_subscription_deleted(event.data.object)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed")