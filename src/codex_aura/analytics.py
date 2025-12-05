"""Usage analytics for codex-aura (opt-in)."""

import hashlib
import json
import os
import platform
import time
from typing import Dict, Any, Optional
import uuid

from .logging import get_logger

logger = get_logger(__name__)


class UsageAnalytics:
    """Collects anonymous usage analytics when enabled."""

    def __init__(self):
        self.enabled = os.getenv("ANALYTICS_ENABLED", "false").lower() == "true"
        self.installation_id = self._get_installation_id()
        self.session_id = str(uuid.uuid4())

    def _get_installation_id(self) -> str:
        """Get or create anonymous installation ID."""
        id_file = os.path.join(os.path.dirname(__file__), ".installation_id")

        if os.path.exists(id_file):
            with open(id_file, "r") as f:
                return f.read().strip()

        # Create new anonymous ID
        installation_id = str(uuid.uuid4())
        try:
            with open(id_file, "w") as f:
                f.write(installation_id)
        except Exception:
            # If we can't write, use a session-based ID
            pass

        return installation_id

    def _anonymize_path(self, path: str) -> str:
        """Anonymize file/directory paths."""
        if not path:
            return ""

        # Hash the full path for anonymity
        return hashlib.sha256(path.encode()).hexdigest()[:16]

    def _get_system_info(self) -> Dict[str, Any]:
        """Get anonymized system information."""
        return {
            "os": platform.system(),
            "python_version": platform.python_version(),
            "architecture": platform.machine(),
        }

    def track_event(self, event_name: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Track a usage event if analytics is enabled."""
        if not self.enabled:
            return

        event = {
            "event": event_name,
            "timestamp": int(time.time()),
            "installation_id": self.installation_id,
            "session_id": self.session_id,
            "system": self._get_system_info(),
            "properties": properties or {}
        }

        # Anonymize sensitive data
        if "repo_path" in event["properties"]:
            event["properties"]["repo_path_hash"] = self._anonymize_path(event["properties"]["repo_path"])
            del event["properties"]["repo_path"]

        if "graph_id" in event["properties"]:
            # Keep graph_id as it's already anonymous
            pass

        # Log the event (could be sent to analytics service in production)
        logger.info("analytics_event", **event)

    def track_analysis(self, repo_path: str, graph_id: str, stats: Dict[str, Any], duration_ms: int) -> None:
        """Track repository analysis event."""
        self.track_event("analysis_completed", {
            "repo_path": repo_path,
            "graph_id": graph_id,
            "files_count": stats.get("files", 0),
            "classes_count": stats.get("classes", 0),
            "functions_count": stats.get("functions", 0),
            "edges_count": sum(stats.get("edges", {}).values()),
            "duration_ms": duration_ms
        })

    def track_context_request(self, graph_id: str, entry_points_count: int, depth: int, max_nodes: int, nodes_returned: int, truncated: bool) -> None:
        """Track context retrieval event."""
        self.track_event("context_requested", {
            "graph_id": graph_id,
            "entry_points_count": entry_points_count,
            "depth": depth,
            "max_nodes": max_nodes,
            "nodes_returned": nodes_returned,
            "truncated": truncated
        })

    def track_api_request(self, endpoint: str, method: str, status_code: int, duration_ms: int) -> None:
        """Track API request event."""
        self.track_event("api_request", {
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms
        })

    def track_error(self, error_type: str, endpoint: str) -> None:
        """Track error event."""
        self.track_event("error_occurred", {
            "error_type": error_type,
            "endpoint": endpoint
        })


# Global analytics instance
analytics = UsageAnalytics()