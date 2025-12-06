"""Quota enforcement middleware for API requests."""

import asyncio
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from ...billing.usage import UsageTracker


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforce plan quotas on API requests."""

    def __init__(self, app, usage_tracker: UsageTracker):
        super().__init__(app)
        self.usage_tracker = usage_tracker

    async def dispatch(self, request: Request, call_next):
        # Skip for non-API routes
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        # Skip for public endpoints
        public_endpoints = ["/api/v1/health", "/api/v1/info", "/api/v1/billing/plans"]
        if request.url.path in public_endpoints:
            return await call_next(request)

        # Get user from auth
        user = getattr(request.state, 'user', None)
        if not user:
            return await call_next(request)

        # Check quotas
        allowed, reason = await self.usage_tracker.check_limits(user.id, user.plan)

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "quota_exceeded",
                    "message": reason,
                    "upgrade_url": "/settings/billing"
                }
            )

        # Process request
        response = await call_next(request)

        # Record usage (async, don't block response)
        tokens_used = response.headers.get("X-Tokens-Used", 0)
        asyncio.create_task(
            self.usage_tracker.record_request(user.id, request.url.path, int(tokens_used))
        )

        return response