"""Authentication middleware for Clerk JWT tokens."""

import os
import time
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import requests
from pydantic import BaseModel

from ...models.user import User


class ClerkAuth:
    """Clerk authentication handler."""

    def __init__(self):
        self.clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
        self.clerk_publishable_key = os.getenv("CLERK_PUBLISHABLE_KEY")
        self.jwks_url = f"https://{self.clerk_publishable_key}.clerk.accounts.dev/.well-known/jwks.json"

        # Cache for JWKS
        self._jwks_cache = None
        self._jwks_cache_time = 0
        self._cache_ttl = 3600  # 1 hour

    def get_jwks(self):
        """Get JWKS from Clerk, with caching."""
        current_time = time.time()

        if self._jwks_cache and (current_time - self._jwks_cache_time) < self._cache_ttl:
            return self._jwks_cache

        try:
            response = requests.get(self.jwks_url, timeout=10)
            response.raise_for_status()
            self._jwks_cache = response.json()
            self._jwks_cache_time = current_time
            return self._jwks_cache
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch JWKS: {str(e)}")

    def verify_token(self, token: str) -> dict:
        """Verify JWT token from Clerk."""
        try:
            # Get the kid from the token header
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')

            if not kid:
                raise HTTPException(status_code=401, detail="Invalid token: missing kid")

            # Get the public key
            jwks = self.get_jwks()
            public_key = None

            for key in jwks['keys']:
                if key['kid'] == kid:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    break

            if not public_key:
                raise HTTPException(status_code=401, detail="Invalid token: unknown kid")

            # Verify the token
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                audience=self.clerk_publishable_key,
                issuer=f"https://{self.clerk_publishable_key}.clerk.accounts.dev"
            )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

    def get_current_user(self, token: str) -> User:
        """Extract user information from verified token."""
        payload = self.verify_token(token)

        # Clerk JWT payload structure
        user_id = payload.get('sub')
        email = payload.get('email')
        name = payload.get('name') or payload.get('first_name', 'Unknown')

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing user ID")

        return User(
            id=user_id,
            email=email,
            name=name,
            plan_tier="free"  # Default, can be enhanced with subscription data
        )


# Global auth instance
clerk_auth = ClerkAuth()

# FastAPI security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    FastAPI dependency to get current authenticated user.

    Extracts and verifies JWT token from Authorization header.
    """
    token = credentials.credentials
    return clerk_auth.get_current_user(token)


async def get_current_user_optional(
    request: Request
) -> Optional[User]:
    """
    Optional user authentication - returns None if no token provided.

    Useful for endpoints that work with or without authentication.
    """
    try:
        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        return clerk_auth.get_current_user(token)
    except HTTPException:
        return None


def require_auth(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires authentication."""
    return user


def optional_auth(user: Optional[User] = Depends(get_current_user_optional)) -> Optional[User]:
    """Dependency that allows optional authentication."""
    return user