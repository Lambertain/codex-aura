"""API key management endpoints."""

import secrets
import time
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..api.middleware.auth import require_auth

router = APIRouter()

# In-memory storage for demo purposes. In production, use a database.
api_keys_store = {}


class ApiKeyCreateRequest(BaseModel):
    """Request model for creating an API key."""
    name: str


class ApiKeyResponse(BaseModel):
    """Response model for API key operations."""
    id: str
    name: str
    key: str
    created_at: str
    usage_count: int = 0
    last_used: Optional[str] = None


class ApiKeysListResponse(BaseModel):
    """Response model for listing API keys."""
    keys: List[ApiKeyResponse]


def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"ca_{secrets.token_urlsafe(32)}"


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    request: ApiKeyCreateRequest,
    current_user=Depends(require_auth)
):
    """Create a new API key."""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="API key name is required")

    key_id = secrets.token_hex(16)
    api_key = generate_api_key()

    api_keys_store[key_id] = {
        "id": key_id,
        "name": request.name.strip(),
        "key": api_key,
        "created_at": datetime.utcnow().isoformat(),
        "usage_count": 0,
        "last_used": None,
        "user_id": current_user.id
    }

    return ApiKeyResponse(**api_keys_store[key_id])


@router.get("/api-keys", response_model=ApiKeysListResponse)
async def list_api_keys(current_user=Depends(require_auth)):
    """List all API keys for the current user."""
    user_keys = [
        ApiKeyResponse(**key_data)
        for key_data in api_keys_store.values()
        if key_data["user_id"] == current_user.id
    ]

    return ApiKeysListResponse(keys=user_keys)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, current_user=Depends(require_auth)):
    """Revoke an API key."""
    if key_id not in api_keys_store:
        raise HTTPException(status_code=404, detail="API key not found")

    key_data = api_keys_store[key_id]
    if key_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    del api_keys_store[key_id]
    return {"message": "API key revoked successfully"}


@router.post("/api-keys/{key_id}/regenerate", response_model=ApiKeyResponse)
async def regenerate_api_key(key_id: str, current_user=Depends(require_auth)):
    """Regenerate an existing API key."""
    if key_id not in api_keys_store:
        raise HTTPException(status_code=404, detail="API key not found")

    key_data = api_keys_store[key_id]
    if key_data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    new_key = generate_api_key()
    key_data["key"] = new_key
    key_data["usage_count"] = 0
    key_data["last_used"] = None

    return ApiKeyResponse(**key_data)


def validate_api_key(api_key: str) -> Optional[dict]:
    """Validate an API key and return key data if valid."""
    for key_data in api_keys_store.values():
        if key_data["key"] == api_key:
            # Update usage statistics
            key_data["usage_count"] += 1
            key_data["last_used"] = datetime.utcnow().isoformat()
            return key_data
    return None


def get_api_key_data(api_key: str) -> Optional[dict]:
    """Get API key data without updating usage."""
    for key_data in api_keys_store.values():
        if key_data["key"] == api_key:
            return key_data
    return None