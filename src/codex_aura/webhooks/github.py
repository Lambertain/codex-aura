"""GitHub webhook handling."""

import hmac
import hashlib
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


def verify_github_signature(payload: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret (if None, uses GITHUB_WEBHOOK_SECRET env var)

    Returns:
        True if signature is valid
    """
    if secret is None:
        secret = os.getenv("GITHUB_WEBHOOK_SECRET")

    if not secret:
        logger.warning("No GitHub webhook secret configured")
        return False

    if not signature.startswith("sha256="):
        logger.error("Invalid signature format")
        return False

    expected_signature = signature[7:]  # Remove "sha256=" prefix

    # Create HMAC signature
    hmac_obj = hmac.new(secret.encode(), payload, hashlib.sha256)
    computed_signature = hmac_obj.hexdigest()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(computed_signature, expected_signature)


def extract_github_event(headers: Dict[str, str]) -> Optional[str]:
    """Extract event type from GitHub webhook headers."""
    return headers.get("X-GitHub-Event")


def normalize_github_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize GitHub webhook payload to internal format.

    This function converts GitHub-specific event structures to
    a common internal format used by the processor.
    """
    event_type = data.get("action", "")

    # For push events, the event type is just "push"
    if "commits" in data and "head_commit" in data:
        event_type = "push"

    # For create/delete events
    if "ref_type" in data:
        if data.get("ref_type") == "branch":
            event_type = "create" if "master_branch" in data else "delete"

    normalized = {
        "event_type": event_type,
        "repository": {
            "id": data.get("repository", {}).get("id"),
            "name": data.get("repository", {}).get("name"),
            "full_name": data.get("repository", {}).get("full_name"),
            "url": data.get("repository", {}).get("html_url"),
        },
        "sender": {
            "id": data.get("sender", {}).get("id"),
            "login": data.get("sender", {}).get("login"),
        },
        **data  # Include original data
    }

    return normalized