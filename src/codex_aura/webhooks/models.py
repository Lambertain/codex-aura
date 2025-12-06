"""Models for webhook events."""

from typing import Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime


class WebhookEvent(BaseModel):
    """Webhook event model."""

    repo_id: str
    event: str
    data: Dict[str, Any]
    received_at: datetime = datetime.utcnow()
    processed: bool = False
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    error: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class GitHubWebhookPayload(BaseModel):
    """GitHub webhook payload model."""

    action: Optional[str] = None
    repository: Dict[str, Any]
    sender: Dict[str, Any]
    commits: Optional[list] = None
    head_commit: Optional[Dict[str, Any]] = None
    pull_request: Optional[Dict[str, Any]] = None
    ref: Optional[str] = None
    ref_type: Optional[str] = None
    master_branch: Optional[str] = None
    description: Optional[str] = None


class GitLabWebhookPayload(BaseModel):
    """GitLab webhook payload model."""

    object_kind: str
    event_name: Optional[str] = None
    before: Optional[str] = None
    after: Optional[str] = None
    ref: Optional[str] = None
    checkout_sha: Optional[str] = None
    message: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_username: Optional[str] = None
    user_email: Optional[str] = None
    user_avatar: Optional[str] = None
    project_id: Optional[int] = None
    project: Optional[Dict[str, Any]] = None
    commits: Optional[list] = None
    total_commits_count: Optional[int] = None


class SyncJob(BaseModel):
    """Sync job model for queueing sync operations."""
    repo_id: str
    target_sha: Optional[str] = None