"""Rate limiting middleware for API endpoints."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Different limits by plan
RATE_LIMITS = {
    "free": "100/day",
    "pro": "10000/day",
    "team": "50000/day",
    "enterprise": "unlimited"
}

limiter = Limiter(key_func=get_remote_address)

def get_rate_limit(user) -> str:
    """Get rate limit string for user's plan."""
    return RATE_LIMITS.get(user.plan, RATE_LIMITS["free"])