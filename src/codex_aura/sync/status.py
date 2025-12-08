"""Sync status tracking for repositories."""

from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum
import json
from typing import Optional

from ..storage.sqlite import SQLiteStorage
from ..webhooks.models import SyncJob


class SyncState(str, Enum):
    SYNCED = "synced"          # Up to date
    SYNCING = "syncing"        # Currently processing
    STALE = "stale"            # Behind by commits
    ERROR = "error"            # Last sync failed
    PENDING = "pending"        # Queued for sync


class SyncStatus(BaseModel):
    repo_id: str
    state: SyncState
    current_sha: Optional[str] = None
    target_sha: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    last_sync_duration_ms: Optional[int] = None
    commits_behind: int = 0
    error_message: Optional[str] = None
    retry_count: int = 0


class SyncStatusTracker:
    """Track and manage sync status for repositories."""

    def __init__(self, db: SQLiteStorage, redis_pool):
        self.db = db
        self.redis_pool = redis_pool

    async def acquire_sync_lock(self, repo_id: str, timeout: int = 300) -> bool:
        """
        Try to acquire exclusive sync lock for repository.
        Returns True if lock acquired, False if already locked or Redis unavailable.
        """
        if not self.redis_pool:
            return True  # No redis -> assume single instance

        lock_key = f"sync_lock:{repo_id}"
        try:
            acquired = await self.redis_pool.set(
                lock_key,
                datetime.utcnow().isoformat(),
                ex=timeout,
                nx=True
            )
            return bool(acquired)
        except Exception:
            # Fallback to optimistic proceed without redis
            return True

    async def release_sync_lock(self, repo_id: str) -> None:
        """Release sync lock if it exists."""
        if not self.redis_pool:
            return
        try:
            await self.redis_pool.delete(f"sync_lock:{repo_id}")
        except Exception:
            pass

    async def is_sync_locked(self, repo_id: str) -> bool:
        """Check if sync is currently locked."""
        if not self.redis_pool:
            return False
        try:
            value = await self.redis_pool.get(f"sync_lock:{repo_id}")
            return value is not None
        except Exception:
            return False

    async def get_status(self, repo_id: str) -> SyncStatus:
        """Get current sync status for a repository."""
        # Check if currently syncing (in Redis)
        if self.redis_pool:
            try:
                syncing_data = await self.redis_pool.get(f"syncing:{repo_id}")
                if syncing_data:
                    status_data = json.loads(syncing_data)
                    return SyncStatus(
                        repo_id=repo_id,
                        state=SyncState.SYNCING,
                        **status_data
                    )
            except Exception:
                pass  # Redis might not be available

        # Get from database
        record = self._get_sync_status_from_db(repo_id)
        if record:
            return SyncStatus(**record)

        return SyncStatus(
            repo_id=repo_id,
            state=SyncState.PENDING
        )

    async def start_sync(
        self,
        repo_id: str,
        target_sha: Optional[str]
    ):
        """Mark repository as syncing."""
        status = {
            "target_sha": target_sha,
            "started_at": datetime.utcnow().isoformat()
        }
        if self.redis_pool:
            try:
                await self.redis_pool.setex(
                    f"syncing:{repo_id}",
                    300,  # 5 min TTL
                    json.dumps(status)
                )
            except Exception:
                pass  # Redis might not be available

    async def complete_sync(
        self,
        repo_id: str,
        new_sha: str,
        duration_ms: int,
        success: bool,
        error: Optional[str] = None
    ):
        """Mark sync as complete."""
        # Remove syncing flag
        if self.redis_pool:
            try:
                await self.redis_pool.delete(f"syncing:{repo_id}")
            except Exception:
                pass

        # Update database
        if success:
            self._update_sync_status_in_db(
                repo_id=repo_id,
                state=SyncState.SYNCED,
                current_sha=new_sha,
                last_sync_at=datetime.utcnow(),
                last_sync_duration_ms=duration_ms,
                error_message=None,
                retry_count=0
            )
        else:
            current = self._get_sync_status_from_db(repo_id)
            retry_count = (current.get('retry_count', 0) if current else 0) + 1
            self._update_sync_status_in_db(
                repo_id=repo_id,
                state=SyncState.ERROR,
                error_message=error,
                retry_count=retry_count
            )

    async def get_stale_repos(
        self,
        threshold: timedelta = timedelta(hours=1)
    ) -> list[str]:
        """Find repositories that haven't synced recently."""
        cutoff = datetime.utcnow() - threshold
        return self._find_repos_synced_before(cutoff)

    def _get_sync_status_from_db(self, repo_id: str) -> Optional[dict]:
        """Get sync status from database."""
        with self.db._get_connection() as conn:
            cursor = conn.execute("""
                SELECT repo_id, state, current_sha, target_sha,
                       last_sync_at, last_sync_duration_ms,
                       commits_behind, error_message, retry_count
                FROM sync_status WHERE repo_id = ?
            """, (repo_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'repo_id': row[0],
                    'state': row[1],
                    'current_sha': row[2],
                    'target_sha': row[3],
                    'last_sync_at': datetime.fromisoformat(row[4]) if row[4] else None,
                    'last_sync_duration_ms': row[5],
                    'commits_behind': row[6],
                    'error_message': row[7],
                    'retry_count': row[8]
                }
        return None

    def _update_sync_status_in_db(
        self,
        repo_id: str,
        state: SyncState,
        current_sha: Optional[str] = None,
        target_sha: Optional[str] = None,
        last_sync_at: Optional[datetime] = None,
        last_sync_duration_ms: Optional[int] = None,
        commits_behind: int = 0,
        error_message: Optional[str] = None,
        retry_count: int = 0
    ):
        """Update sync status in database."""
        with self.db._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sync_status
                (repo_id, state, current_sha, target_sha, last_sync_at,
                 last_sync_duration_ms, commits_behind, error_message, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                repo_id,
                state.value,
                current_sha,
                target_sha,
                last_sync_at.isoformat() if last_sync_at else None,
                last_sync_duration_ms,
                commits_behind,
                error_message,
                retry_count
            ))
            conn.commit()

    def _find_repos_synced_before(self, cutoff: datetime) -> list[str]:
        """Find repos synced before cutoff."""
        with self.db._get_connection() as conn:
            cursor = conn.execute("""
                SELECT repo_id FROM sync_status
                WHERE last_sync_at < ? OR last_sync_at IS NULL
            """, (cutoff.isoformat(),))
            return [row[0] for row in cursor.fetchall()]


# Initialize sync status table
def init_sync_status_table(db: SQLiteStorage):
    """Initialize sync_status table in database."""
    with db._get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_status (
                repo_id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                current_sha TEXT,
                target_sha TEXT,
                last_sync_at TEXT,
                last_sync_duration_ms INTEGER,
                commits_behind INTEGER DEFAULT 0,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
