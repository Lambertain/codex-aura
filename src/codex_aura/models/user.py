"""User model."""

from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from ..billing.plans import PlanTier


class User(BaseModel):
    """User model."""

    id: str
    email: EmailStr
    name: str
    stripe_customer_id: Optional[str] = None
    plan_tier: PlanTier = PlanTier.FREE
    subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()