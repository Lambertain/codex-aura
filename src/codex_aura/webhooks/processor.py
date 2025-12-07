"""Webhook event processor."""

import logging
from typing import Dict, Any, Callable, Awaitable
from datetime import datetime

from .models import WebhookEvent

logger = logging.getLogger(__name__)


class WebhookProcessor:
    """Processes webhook events from Git hosting services."""

    def __init__(self, graph_updater=None):
        self.graph_updater = graph_updater
        self.handlers: Dict[str, Callable[[str, Dict[str, Any]], Awaitable[None]]] = {
            "push": self.handle_push,
            "pull_request": self.handle_pull_request,
            "create": self.handle_branch_create,
            "delete": self.handle_branch_delete,
        }

    async def process_event(self, event: WebhookEvent) -> None:
        """Process a webhook event."""
        try:
            event.processing_started_at = datetime.utcnow()

            handler = self.handlers.get(event.event)
            if handler:
                await handler(event.repo_id, event.data)
                logger.info(f"Successfully processed {event.event} event for repo {event.repo_id}")
            else:
                logger.warning(f"No handler found for event type: {event.event}")

        except Exception as e:
            logger.error(f"Error processing webhook event {event.event}: {e}")
            event.error = str(e)
            raise

    async def handle_push(self, repo_id: str, data: Dict[str, Any]) -> None:
        """Handle push event - save graph snapshot for each commit."""
        commits = data.get("commits", [])
        if not commits:
            logger.info(f"No commits in push event for repo {repo_id}")
            return

        # Save graph snapshot for each commit
        for commit in commits:
            commit_sha = commit.get("id")
            if not commit_sha:
                continue

            # Collect changed files for this commit
            changed_files = set()
            changed_files.update(commit.get("added", []))
            changed_files.update(commit.get("modified", []))
            changed_files.update(commit.get("removed", []))

            if changed_files and self.graph_updater:
                logger.info(f"Saving graph snapshot for commit {commit_sha[:8]} in repo {repo_id}")
                await self.graph_updater.save_commit_snapshot(repo_id, commit_sha, list(changed_files))
            else:
                logger.info(f"No files changed in commit {commit_sha[:8]} for repo {repo_id}")

    async def handle_pull_request(self, repo_id: str, data: Dict[str, Any]) -> None:
        """Handle pull request event."""
        action = data.get("action")
        pr = data.get("pull_request", {})

        logger.info(f"Processing PR {action} for repo {repo_id}")

        # For now, just log the event
        # In the future, this could trigger analysis of PR changes
        if action in ["opened", "synchronize", "reopened"]:
            # Could analyze PR diff and update graph incrementally
            pass
        elif action in ["closed"]:
            # Could clean up temporary graph data
            pass

    async def handle_branch_create(self, repo_id: str, data: Dict[str, Any]) -> None:
        """Handle branch creation event."""
        ref_type = data.get("ref_type")
        ref = data.get("ref")

        if ref_type == "branch":
            logger.info(f"Branch {ref} created in repo {repo_id}")
            # Could trigger initial analysis for new branch
        else:
            logger.info(f"Tag {ref} created in repo {repo_id}")

    async def handle_branch_delete(self, repo_id: str, data: Dict[str, Any]) -> None:
        """Handle branch deletion event."""
        ref_type = data.get("ref_type")
        ref = data.get("ref")

        if ref_type == "branch":
            logger.info(f"Branch {ref} deleted in repo {repo_id}")
            # Could clean up branch-specific graph data
        else:
            logger.info(f"Tag {ref} deleted in repo {repo_id}")

    def register_handler(self, event_type: str, handler: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        """Register a custom event handler."""
        self.handlers[event_type] = handler
        logger.info(f"Registered custom handler for event: {event_type}")

    def unregister_handler(self, event_type: str) -> None:
        """Unregister an event handler."""
        if event_type in self.handlers:
            del self.handlers[event_type]
            logger.info(f"Unregistered handler for event: {event_type}")