#!/usr/bin/env python3
"""Simple test for sync status functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from codex_aura.storage.sqlite import SQLiteStorage
from codex_aura.sync.status import SyncStatusTracker, SyncStatus, SyncState, init_sync_status_table

def test_sync_status():
    """Test sync status tracking."""
    # Create in-memory database for testing
    db = SQLiteStorage(":memory:")
    init_sync_status_table(db)

    # Create tracker (without Redis for simplicity)
    tracker = SyncStatusTracker(db, None)

    # Test getting status for non-existent repo
    status = tracker.get_status("test-repo")
    assert status.state == SyncState.PENDING
    assert status.repo_id == "test-repo"
    print("✓ Get status for new repo works")

    # Test starting sync
    import asyncio
    asyncio.run(tracker.start_sync("test-repo", "abc123"))
    print("✓ Start sync works")

    # Test getting status after start (should still be pending since no Redis)
    status = tracker.get_status("test-repo")
    assert status.state == SyncState.PENDING
    print("✓ Get status after start works")

    # Test completing sync successfully
    asyncio.run(tracker.complete_sync("test-repo", "abc123", 1000, True))
    status = tracker.get_status("test-repo")
    assert status.state == SyncState.SYNCED
    assert status.current_sha == "abc123"
    assert status.last_sync_duration_ms == 1000
    print("✓ Complete sync successfully works")

    # Test completing sync with error
    asyncio.run(tracker.start_sync("test-repo", "def456"))
    asyncio.run(tracker.complete_sync("test-repo", "def456", 500, False, "Test error"))
    status = tracker.get_status("test-repo")
    assert status.state == SyncState.ERROR
    assert status.error_message == "Test error"
    assert status.retry_count == 1
    print("✓ Complete sync with error works")

    # Test stale repos
    stale = asyncio.run(tracker.get_stale_repos())
    assert "test-repo" in stale  # Since we don't have recent sync
    print("✓ Get stale repos works")

    print("All tests passed!")

if __name__ == "__main__":
    test_sync_status()