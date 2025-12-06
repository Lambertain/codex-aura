from datetime import datetime, timedelta
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import secrets
import hashlib
import hmac

# Assuming these imports exist in the project
from ..models import Database, User  # Adjust path as needed
from ..auth import get_current_user  # Adjust path as needed
from ..database import get_db  # Adjust path as needed
from ..config import settings  # Adjust path as needed
from ..webhooks.queue import webhook_queue, WebhookEvent  # Adjust path as needed

router = APIRouter(prefix="/api/v1/repos/{repo_id}/webhooks", tags=["webhooks"])

class WebhookSetupRequest(BaseModel):
    platform: Literal["github", "gitlab", "bitbucket"] = "github"
    events: list[str] = ["push", "pull_request"]

class WebhookSetupResponse(BaseModel):
    webhook_url: str
    secret: str
    events: list[str]
    platform: str
    instructions: str
    curl_example: str

class WebhookStatus(BaseModel):
    is_configured: bool
    last_received: Optional[datetime] = None
    events_received_24h: int
    health: Literal["healthy", "stale", "error"]

@router.post("/setup", response_model=WebhookSetupResponse)
async def setup_webhook(
    repo_id: str,
    request: WebhookSetupRequest,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate webhook configuration for a repository.

    Returns the webhook URL, secret, and setup instructions.
    """
    # Verify repo ownership
    repo = await db.get_repo(repo_id)
    if not repo or repo.owner_id != current_user.id:
        raise HTTPException(404, "Repository not found")

    # Generate secure secret
    secret = secrets.token_urlsafe(32)
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()

    # Store secret hash (not the secret itself)
    await db.store_webhook_secret(repo_id, secret_hash, request.platform)

    # Build webhook URL
    base_url = settings.API_BASE_URL
    webhook_url = f"{base_url}/webhooks/{request.platform}/{repo_id}"

    # Generate platform-specific instructions
    instructions = _generate_instructions(request.platform, webhook_url, request.events)
    curl_example = _generate_curl_example(request.platform, webhook_url, secret)

    return WebhookSetupResponse(
        webhook_url=webhook_url,
        secret=secret,
        events=request.events,
        platform=request.platform,
        instructions=instructions,
        curl_example=curl_example
    )

@router.get("/status", response_model=WebhookStatus)
async def get_webhook_status(
    repo_id: str,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get webhook health status for a repository."""

    webhook_config = await db.get_webhook_config(repo_id)
    if not webhook_config:
        return WebhookStatus(
            is_configured=False,
            last_received=None,
            events_received_24h=0,
            health="error"
        )

    # Get recent events
    events_24h = await db.count_webhook_events(
        repo_id,
        since=datetime.utcnow() - timedelta(hours=24)
    )

    # Determine health
    if webhook_config.last_received is None:
        health = "stale"
    elif (datetime.utcnow() - webhook_config.last_received).days > 7:
        health = "stale"
    else:
        health = "healthy"

    return WebhookStatus(
        is_configured=True,
        last_received=webhook_config.last_received,
        events_received_24h=events_24h,
        health=health
    )

@router.delete("/")
async def delete_webhook(
    repo_id: str,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove webhook configuration."""
    await db.delete_webhook_config(repo_id)
    return {"status": "deleted"}

@router.post("/test")
async def test_webhook(
    repo_id: str,
    db: Database = Depends(get_db)
):
    """Send a test event to verify webhook is working."""
    # Queue a test event
    await webhook_queue.enqueue(
        WebhookEvent(
            repo_id=repo_id,
            event="ping",
            data={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
    )
    return {"status": "test_queued"}

def _generate_instructions(platform: str, url: str, events: list[str]) -> str:
    """Generate platform-specific setup instructions."""

    if platform == "github":
        return f"""
## GitHub Webhook Setup

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure:
   - **Payload URL:** `{url}`
   - **Content type:** `application/json`
   - **Secret:** (use the secret provided above)
   - **Events:** Select {', '.join(events)}
4. Click **Add webhook**

The webhook will start receiving events immediately.
"""

    elif platform == "gitlab":
        return f"""
## GitLab Webhook Setup

1. Go to your project on GitLab
2. Navigate to **Settings** → **Webhooks**
3. Configure:
   - **URL:** `{url}`
   - **Secret token:** (use the secret provided above)
   - **Trigger:** Select {', '.join(events)}
4. Click **Add webhook**
"""

    return "Platform not supported"

def _generate_curl_example(platform: str, url: str, secret: str) -> str:
    """Generate curl command to test webhook."""

    if platform == "github":
        payload = '{"ref":"refs/heads/main","commits":[{"id":"abc123","message":"test"}]}'
        signature = _compute_github_signature(payload, secret)
        return f"""
curl -X POST {url} \\
  -H "Content-Type: application/json" \\
  -H "X-GitHub-Event: push" \\
  -H "X-Hub-Signature-256: sha256={signature}" \\
  -d '{payload}'
"""
    return ""

def _compute_github_signature(payload: str, secret: str) -> str:
    """Compute GitHub webhook signature."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()