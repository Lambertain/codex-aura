"""GitLab webhook handling."""

import hmac
import hashlib
import base64
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


def verify_gitlab_signature(payload: bytes, signature: str, secret: Optional[str] = None) -> bool:
    """
    Verify GitLab webhook signature.

    Args:
        payload: Raw request body
        signature: X-Gitlab-Token header value
        secret: Webhook secret (if None, uses GITLAB_WEBHOOK_SECRET env var)

    Returns:
        True if signature is valid
    """
    if secret is None:
        secret = os.getenv("GITLAB_WEBHOOK_SECRET")

    if not secret:
        logger.warning("No GitLab webhook secret configured")
        return False

    # GitLab uses HMAC-SHA256 with base64 encoding
    expected_signature = base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode()

    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(signature, expected_signature)


def extract_gitlab_event(headers: Dict[str, str]) -> Optional[str]:
    """Extract event type from GitLab webhook headers."""
    return headers.get("X-Gitlab-Event")


def normalize_gitlab_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize GitLab webhook payload to internal format.

    This function converts GitLab-specific event structures to
    a common internal format used by the processor.
    """
    object_kind = data.get("object_kind", "")

    # Map GitLab events to internal event types
    event_mapping = {
        "push": "push",
        "merge_request": "pull_request",  # GitLab calls them merge requests
        "tag_push": "create",  # For tag creation
    }

    event_type = event_mapping.get(object_kind, object_kind)

    normalized = {
        "event_type": event_type,
        "repository": {
            "id": data.get("project", {}).get("id"),
            "name": data.get("project", {}).get("name"),
            "full_name": data.get("project", {}).get("path_with_namespace"),
            "url": data.get("project", {}).get("web_url"),
        },
        "sender": {
            "id": data.get("user_id"),
            "login": data.get("user_username", data.get("user_name")),
        },
        **data  # Include original data
    }

    # Normalize commits for push events
    if object_kind == "push" and "commits" in data:
        normalized["commits"] = [
            {
                "id": commit.get("id"),
                "message": commit.get("message"),
                "timestamp": commit.get("timestamp"),
                "author": commit.get("author"),
                "added": commit.get("added", []),
                "modified": commit.get("modified", []),
                "removed": commit.get("removed", []),
            }
            for commit in data["commits"]
        ]

    # Normalize merge request data
    if object_kind == "merge_request":
        mr = data.get("object_attributes", {})
        normalized["pull_request"] = {
            "id": mr.get("id"),
            "number": mr.get("iid"),
            "title": mr.get("title"),
            "body": mr.get("description"),
            "state": mr.get("state"),
            "merged": mr.get("state") == "merged",
            "head": {
                "ref": mr.get("source_branch"),
                "sha": mr.get("last_commit", {}).get("id"),
            },
            "base": {
                "ref": mr.get("target_branch"),
            },
        }
        # Map action
        if mr.get("action") == "open":
            normalized["action"] = "opened"
        elif mr.get("action") == "close":
            normalized["action"] = "closed"
        elif mr.get("action") == "merge":
            normalized["action"] = "closed"  # Treat merge as close

    return normalized