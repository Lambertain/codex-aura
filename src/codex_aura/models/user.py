"""User model."""

from pydantic import BaseModel, EmailStr
from typing import Optional


class User(BaseModel):
    """User model."""

    id: str
    email: EmailStr
    name: str
    stripe_customer_id: Optional[str] = None
    plan_tier: str = "free"