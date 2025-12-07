"""Tests for PostgreSQL snapshot storage."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from ..src.codex_aura.storage.postgres_snapshots import PostgresSnapshotStorage, GraphSnapshot
from ..src.codex_aura.models.node import Node
from ..src.codex_aura.models.edge import Edge


class TestPostgresSnapshotStorage:
    """Test cases for PostgreSQL snapshot storage."""

    @pytest.fixture
    def mock_connection(self):
        """Mock asyncpg connection."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock()
        conn.fetch = AsyncMock()
        conn.execute = AsyncMock()
        conn.executemany = AsyncMock()
        return conn

    @pytest.fixture
    def storage(self):
        """Create storage instance with mocked connection."""
        storage = PostgresSnapshotStorage("postgresql://test:test@localhost/test")
        return storage

    @pytest.fixture
    def sample_nodes(self):
        """Sample nodes for testing."""
        return [
            Node(
                id="file1.py",
                type="file",
                name="file1.py",
                path="src/file1.py",
                lines=[1, 10],
                docstring="Test file",
                blame=None
            ),
            Node(
                id="class1",
                type="class",
                name="TestClass",
                path="src/file1.py",
                lines=[5, 15],
                docstring="Test class",
                blame=None
            )
        ]

    @pytest.fixture
    def sample_edges(self):
        """Sample edges for testing."""
        return [
            Edge(
                source="file1.py",
                target="class1",
                type="CONTAINS",
                line=5
            )
        ]

    @pytest.mark.asyncio
    async def test_create_tables(self, storage, mock_connection):
        """Test table creation."""
        # Mock the connection context manager
        storage.connection = AsyncMock(return_value=mock_connection)

        await storage.create_tables()

        # Verify table creation SQL was executed
        assert mock_connection.execute.call_count == 3  # 3 tables created

    @pytest.mark.asyncio
    async def test_create_snapshot(self, storage, mock_connection, sample_nodes, sample_edges):
        """Test snapshot creation."""
        storage.connection = AsyncMock(return_value=mock_connection)

        # Mock transaction context
        mock_transaction = AsyncMock()
        mock_connection.transaction = AsyncMock(return_value=mock_transaction)

        snapshot_id = await storage.create_snapshot("repo123", "abc123", sample_nodes, sample_edges)

        # Verify snapshot was created
        assert snapshot_id is not None
        assert len(snapshot_id) == 36  # UUID length

        # Verify database calls
        mock_connection.execute.assert_called()
        mock_connection.executemany.assert_called()

    @pytest.mark.asyncio
    async def test_get_snapshot(self, storage, mock_connection):
        """Test getting snapshot metadata."""
        storage.connection = AsyncMock(return_value=mock_connection)

        mock_connection.fetchrow.return_value = {
            'snapshot_id': 'test-id',
            'repo_id': 'repo123',
            'sha': 'abc123',
            'created_at': '2023-01-01T00:00:00Z',
            'node_count': 5,
            'edge_count': 3
        }

        snapshot = await storage.get_snapshot('test-id')

        assert snapshot is not None
        assert snapshot.snapshot_id == 'test-id'
        assert snapshot.repo_id == 'repo123'
        assert snapshot.sha == 'abc123'
        assert snapshot.node_count == 5
        assert snapshot.edge_count == 3

    @pytest.mark.asyncio
    async def test_get_snapshots_for_repo(self, storage, mock_connection):
        """Test getting snapshots for repository."""
        storage.connection = AsyncMock(return_value=mock_connection)

        mock_connection.fetch.return_value = [
            {
                'snapshot_id': 'id1',
                'repo_id': 'repo123',
                'sha': 'sha1',
                'created_at': '2023-01-02T00:00:00Z',
                'node_count': 5,
                'edge_count': 3
            },
            {
                'snapshot_id': 'id2',
                'repo_id': 'repo123',
                'sha': 'sha2',
                'created_at': '2023-01-01T00:00:00Z',
                'node_count': 10,
                'edge_count': 8
            }
        ]

        snapshots = await storage.get_snapshots_for_repo('repo123')

        assert len(snapshots) == 2
        assert snapshots[0].snapshot_id == 'id1'  # Should be ordered by created_at desc
        assert snapshots[1].snapshot_id == 'id2'

    @pytest.mark.asyncio
    async def test_get_snapshot_nodes(self, storage, mock_connection):
        """Test getting snapshot nodes."""
        storage.connection = AsyncMock(return_value=mock_connection)

        mock_connection.fetch.return_value = [
            {
                'node_id': 'file1.py',
                'node_type': 'file',
                'name': 'file1.py',
                'path': 'src/file1.py',
                'lines': [1, 10],
                'docstring': 'Test file',
                'blame': None
            }
        ]

        nodes = await storage.get_snapshot_nodes('test-snapshot-id')

        assert len(nodes) == 1
        assert nodes[0]['node_id'] == 'file1.py'
        assert nodes[0]['node_type'] == 'file'

    @pytest.mark.asyncio
    async def test_get_snapshot_edges(self, storage, mock_connection):
        """Test getting snapshot edges."""
        storage.connection = AsyncMock(return_value=mock_connection)

        mock_connection.fetch.return_value = [
            {
                'source_id': 'file1.py',
                'target_id': 'class1',
                'edge_type': 'CONTAINS',
                'line_number': 5
            }
        ]

        edges = await storage.get_snapshot_edges('test-snapshot-id')

        assert len(edges) == 1
        assert edges[0]['source_id'] == 'file1.py'
        assert edges[0]['target_id'] == 'class1'
        assert edges[0]['edge_type'] == 'CONTAINS'