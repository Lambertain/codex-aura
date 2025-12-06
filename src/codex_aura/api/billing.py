"""Billing API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..billing.plans import PLAN_LIMITS, PlanTier, STRIPE_PRICES
from ..billing.stripe_client import StripeClient
from ..models.user import User

router = APIRouter(prefix="/billing", tags=["billing"])

# Mock user dependency - in real app this would come from auth
def get_current_user() -> User:
    """Get current user (mock implementation)."""
    return User(id="user_123", email="user@example.com", name="Test User")

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