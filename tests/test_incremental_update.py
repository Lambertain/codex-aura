import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from codex_aura.sync.incremental import (
    IncrementalGraphUpdater,
    FileChange,
    ChangeType,
    IncrementalUpdateResult
)
from codex_aura.models.node import Node


@pytest.fixture
async def mock_storage():
    """Mock storage with transaction support."""
    storage = MagicMock()
    txn = MagicMock()
    storage.transaction.return_value.__aenter__ = AsyncMock(return_value=txn)
    storage.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    txn.run = AsyncMock()
    txn.upsert_node = AsyncMock()
    txn.find_node_by_fqn = AsyncMock(return_value=None)
    txn.create_edge = AsyncMock()
    return storage, txn


@pytest.fixture
async def mock_analyzer():
    """Mock analyzer."""
    analyzer = MagicMock()
    analyzer.analyze_file = AsyncMock(return_value=[
        Node(id="test.py", type="file", name="test.py", path="test.py"),
        Node(id="func", type="function", name="func", path="test.py")
    ])
    analyzer.resolve_references = MagicMock(return_value=[])
    return analyzer


@pytest.fixture
async def mock_vector_store():
    """Mock vector store."""
    vs = MagicMock()
    vs.delete_by_filter = AsyncMock()
    vs.upsert_chunks = AsyncMock()
    return vs


@pytest.fixture
async def mock_embeddings():
    """Mock embedding service."""
    emb = MagicMock()
    emb.embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    return emb


@pytest.fixture
async def updater(mock_storage, mock_analyzer, mock_vector_store, mock_embeddings):
    """Create updater with mocked dependencies."""
    storage, _ = mock_storage
    return IncrementalGraphUpdater(
        storage, mock_analyzer, mock_vector_store, mock_embeddings
    )


@pytest.fixture
def sample_repo(tmp_path):
    """Create a sample repo structure."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    # Create a sample Python file
    test_file = repo_path / "test.py"
    test_file.write_text("""
def func():
    pass

class MyClass:
    pass
""")

    return MagicMock(
        id="test_repo",
        path=repo_path
    )


async def test_delete_file_removes_nodes(updater, mock_storage, sample_repo):
    """Deleting a file should remove all its nodes."""
    storage, txn = mock_storage

    # Mock the delete query result
    txn.run.return_value = [{"cnt": 2}]

    changes = [FileChange(path="src/utils.py", change_type=ChangeType.DELETED)]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)

    assert result.nodes_deleted == 2
    assert result.nodes_added == 0
    assert result.nodes_updated == 0


async def test_modify_file_updates_nodes(updater, mock_storage, mock_analyzer, sample_repo):
    """Modifying a file should update its nodes."""
    storage, txn = mock_storage

    # Mock the delete query result
    txn.run.return_value = [{"cnt": 1}]

    # Mock file exists
    test_file = sample_repo.path / "src" / "main.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def new_function(): pass")

    changes = [FileChange(path="src/main.py", change_type=ChangeType.MODIFIED)]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)

    assert result.nodes_added == 2  # file node + function node
    assert result.nodes_deleted == 1  # old nodes deleted


async def test_add_file_creates_nodes(updater, mock_storage, sample_repo):
    """Adding a file should create new nodes."""
    storage, txn = mock_storage

    # Create a new file
    new_file = sample_repo.path / "new_file.py"
    new_file.write_text("def hello(): pass")

    changes = [FileChange(path="new_file.py", change_type=ChangeType.ADDED)]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)

    assert result.nodes_added == 2  # file node + function node
    assert result.nodes_deleted == 0


async def test_rename_file_handling(updater, mock_storage, sample_repo):
    """Renaming a file should delete old nodes and create new ones."""
    storage, txn = mock_storage

    # Mock the delete query result
    txn.run.return_value = [{"cnt": 1}]

    # Create the new file (renamed)
    new_file = sample_repo.path / "renamed.py"
    new_file.write_text("def renamed_func(): pass")

    changes = [FileChange(
        path="renamed.py",
        change_type=ChangeType.RENAMED,
        old_path="old.py"
    )]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)

    assert result.nodes_added == 2  # new file and function
    assert result.nodes_deleted == 1  # old file deleted


async def test_incremental_update_performance(updater, sample_repo):
    """Incremental update should complete within time limits."""
    import time

    changes = [FileChange(path="test.py", change_type=ChangeType.MODIFIED)]

    start = time.time()
    result = await updater.update(sample_repo.id, changes, sample_repo.path)
    duration = time.time() - start

    # Should be very fast for small changes
    assert duration < 1.0, f"Update took {duration}s"
    assert result.duration_ms < 1000


async def test_error_handling(updater, mock_analyzer, sample_repo):
    """Errors in file analysis should be recorded."""
    # Make analyzer raise an exception
    mock_analyzer.analyze_file.side_effect = Exception("Analysis failed")

    changes = [FileChange(path="bad_file.py", change_type=ChangeType.ADDED)]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)

    assert len(result.errors) == 1
    assert "Analysis failed" in result.errors[0]


async def test_batch_updater(updater, sample_repo):
    """Batch updater should process changes in batches."""
    from codex_aura.sync.incremental import BatchIncrementalUpdater

    batch_updater = BatchIncrementalUpdater(
        updater.storage, updater.analyzer, updater.vectors, updater.embeddings
    )

    # Create many changes
    changes = [
        FileChange(path=f"file_{i}.py", change_type=ChangeType.ADDED)
        for i in range(10)
    ]

    result = await batch_updater.update_batch(
        sample_repo.id, changes, sample_repo.path, batch_size=3
    )

    # Should process all changes
    assert result.nodes_added > 0


async def test_vector_index_update(updater, mock_vector_store, sample_repo):
    """Vector index should be updated for changed files."""
    # Create a file with content
    test_file = sample_repo.path / "vector_test.py"
    test_file.write_text("def test_func(): return 'hello'")

    changes = [FileChange(path="vector_test.py", change_type=ChangeType.MODIFIED)]

    await updater.update(sample_repo.id, changes, sample_repo.path)

    # Should have called vector operations
    mock_vector_store.delete_by_filter.assert_called()
    mock_vector_store.upsert_chunks.assert_called()