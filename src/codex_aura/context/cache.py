import hashlib
import json
from typing import TYPE_CHECKING

from redis import Redis

if TYPE_CHECKING:
    from ..api.models.context import ContextRequest, ContextResponse


class ContextCache:
    """Cache context responses for repeated requests."""

    def __init__(self, redis: Redis, ttl: int = 300):
        self.redis = redis
        self.ttl = ttl

    def _cache_key(self, request: "ContextRequest", graph_version: str) -> str:
        """Generate cache key from request."""
        # Include graph version to invalidate on updates
        key_data = {
            "repo_id": request.repo_id,
            "task": request.task,
            "entry_points": sorted(request.entry_points),
            "depth": request.depth,
            "max_tokens": request.max_tokens,
            "model": request.model,
            "graph_version": graph_version
        }
        key_hash = hashlib.sha256(json.dumps(key_data).encode()).hexdigest()[:16]
        return f"ctx:{request.repo_id}:{key_hash}"

    async def get(
        self,
        request: "ContextRequest",
        graph_version: str
    ) -> "ContextResponse | None":
        """Get cached context if available."""
        key = self._cache_key(request, graph_version)
        cached = await self.redis.get(key)

        if cached:
            return ContextResponse.parse_raw(cached)
        return None

    async def set(
        self,
        request: "ContextRequest",
        graph_version: str,
        response: "ContextResponse"
    ):
        """Cache context response."""
        key = self._cache_key(request, graph_version)
        await self.redis.setex(key, self.ttl, response.json())

    async def invalidate_repo(self, repo_id: str):
        """Invalidate all cached contexts for a repo."""
        pattern = f"ctx:{repo_id}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)