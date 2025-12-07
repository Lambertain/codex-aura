"""Tests for snapshot service."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from ..src.codex_aura.snapshot.snapshot_service import SnapshotService
from ..src.codex_aura.models.node import Node, BlameInfo
from ..src.codex_aura.models.edge import Edge, EdgeType


class TestSnapshotService:
    """Test cases for SnapshotService."""

    @pytest.fixture
    def mock_neo4j_client(self):
        """Mock Neo4j client."""
        client = AsyncMock()
        client.execute_query = AsyncMock()
        return client

    @pytest.fixture
    def mock_postgres_storage(self):
        """Mock PostgreSQL storage."""
        storage = AsyncMock()
        storage.create_snapshot = AsyncMock(return_value="test-snapshot-id")
        return storage

    @pytest.fixture
    def snapshot_service(self, mock_neo4j_client, mock_postgres_storage):
        """Create snapshot service with mocked dependencies."""
        service = SnapshotService(
            neo4j_client=mock_neo4j_client,
            postgres_storage=mock_postgres_storage
        )
        return service

    @pytest.fixture
    def sample_neo4j_nodes(self):
        """Sample Neo4j node data."""
        return [
            {
                "n": {
                    "id": "file1.py",
                    "type": "file",
                    "name": "file1.py",
                    "path": "src/file1.py",
                    "lines": [1, 10],
                    "docstring": "Test file",
                    "repo_id": "test-repo",
                    "blame": None
                }
            },
            {
                "n": {
                    "id": "class1",
                    "type": "class",
                    "name": "TestClass",
                    "path": "src/file1.py",
                    "lines": [5, 15],
                    "docstring": "Test class",
                    "repo_id": "test-repo",
                    "blame": {
                        "primary_author": "test@example.com",
                        "contributors": ["test@example.com"],
                        "author_distribution": {"test@example.com": 10}
                    }
                }
            }
        ]

    @pytest.fixture
    def sample_neo4j_edges(self):
        """Sample Neo4j edge data."""
        return [
            {
                "source": "src/file1.py",
                "target": "class1",
                "edge_type": "CONTAINS",
                "line": 5
            }
        ]

    @pytest.mark.asyncio
    async def test_create_snapshot_success(self, snapshot_service, mock_neo4j_client, mock_postgres_storage, sample_neo4j_nodes, sample_neo4j_edges):
        """Test successful snapshot creation."""
        # Mock Neo4j queries
        mock_neo4j_client.execute_query.side_effect = [sample_neo4j_nodes, sample_neo4j_edges]

        # Create snapshot
        snapshot_id = await snapshot_service.create_snapshot("test-repo", "abc123")

        # Verify result
        assert snapshot_id == "test-snapshot-id"

        # Verify Neo4j queries were called
        assert mock_neo4j_client.execute_query.call_count == 2

        # Verify PostgreSQL storage was called with correct data
        mock_postgres_storage.create_snapshot.assert_called_once()
        call_args = mock_postgres_storage.create_snapshot.call_args
        assert call_args[0][0] == "test-repo"  # repo_id
        assert call_args[0][1] == "abc123"     # sha
        nodes = call_args[0][2]  # nodes
        edges = call_args[0][3]  # edges

        assert len(nodes) == 2
        assert isinstance(nodes[0], Node)
        assert nodes[0].id == "file1.py"
        assert nodes[1].id == "class1"
        assert isinstance(nodes[1].blame, BlameInfo)

        assert len(edges) == 1
        assert isinstance(edges[0], Edge)
        assert edges[0].source == "src/file1.py"
        assert edges[0].target == "class1"
        assert edges[0].type == EdgeType.CONTAINS

    @pytest.mark.asyncio
    async def test_create_snapshot_neo4j_error(self, snapshot_service, mock_neo4j_client):
        """Test snapshot creation with Neo4j error."""
        # Mock Neo4j to raise exception
        mock_neo4j_client.execute_query.side_effect = Exception("Neo4j connection failed")

        # Attempt to create snapshot
        with pytest.raises(Exception, match="Neo4j connection failed"):
            await snapshot_service.create_snapshot("test-repo", "abc123")

    @pytest.mark.asyncio
    async def test_create_snapshot_postgres_error(self, snapshot_service, mock_neo4j_client, mock_postgres_storage, sample_neo4j_nodes, sample_neo4j_edges):
        """Test snapshot creation with PostgreSQL error."""
        # Mock Neo4j queries
        mock_neo4j_client.execute_query.side_effect = [sample_neo4j_nodes, sample_neo4j_edges]

        # Mock PostgreSQL to raise exception
        mock_postgres_storage.create_snapshot.side_effect = Exception("PostgreSQL connection failed")

        # Attempt to create snapshot
        with pytest.raises(Exception, match="PostgreSQL connection failed"):
            await snapshot_service.create_snapshot("test-repo", "abc123")

    @pytest.mark.asyncio
    async def test_get_nodes_for_repo(self, snapshot_service, mock_neo4j_client, sample_neo4j_nodes):
        """Test getting nodes for repository."""
        mock_neo4j_client.execute_query.return_value = sample_neo4j_nodes

        nodes = await snapshot_service._get_nodes_for_repo("test-repo")

        assert len(nodes) == 2
        assert nodes[0].id == "file1.py"
        assert nodes[0].type == "file"
        assert nodes[1].id == "class1"
        assert nodes[1].type == "class"
        assert isinstance(nodes[1].blame, BlameInfo)
        assert nodes[1].blame.primary_author == "test@example.com"

        # Verify query
        mock_neo4j_client.execute_query.assert_called_once()
        call_args = mock_neo4j_client.execute_query.call_args
        assert "MATCH (n:Node)" in call_args[0][0]
        assert call_args[0][1] == {"repo_id": "test-repo"}

    @pytest.mark.asyncio
    async def test_get_edges_for_repo(self, snapshot_service, mock_neo4j_client, sample_neo4j_edges):
        """Test getting edges for repository."""
        mock_neo4j_client.execute_query.return_value = sample_neo4j_edges

        edges = await snapshot_service._get_edges_for_repo("test-repo")

        assert len(edges) == 1
        assert edges[0].source == "src/file1.py"
        assert edges[0].target == "class1"
        assert edges[0].type == EdgeType.CONTAINS
        assert edges[0].line == 5

        # Verify query
        mock_neo4j_client.execute_query.assert_called_once()
        call_args = mock_neo4j_client.execute_query.call_args
        assert "MATCH (a:Node)-[r]->(b:Node)" in call_args[0][0]
        assert call_args[0][1] == {"repo_id": "test-repo"}

    @pytest.mark.asyncio
    async def test_empty_repo(self, snapshot_service, mock_neo4j_client, mock_postgres_storage):
        """Test snapshot creation for empty repository."""
        # Mock empty results
        mock_neo4j_client.execute_query.side_effect = [[], []]

        snapshot_id = await snapshot_service.create_snapshot("empty-repo", "def456")

        assert snapshot_id == "test-snapshot-id"

        # Verify PostgreSQL was called with empty lists
        mock_postgres_storage.create_snapshot.assert_called_once()
        call_args = mock_postgres_storage.create_snapshot.call_args
        assert call_args[0][2] == []  # empty nodes
        assert call_args[0][3] == []  # empty edges

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_performance_large_snapshot(self, snapshot_service, mock_neo4j_client, mock_postgres_storage):
        """Test performance with large number of nodes and edges (5K nodes)."""
        import time

        # Generate 5000 nodes
        large_nodes = []
        for i in range(5000):
            large_nodes.append({
                "n": {
                    "id": f"node_{i}",
                    "type": "function" if i % 2 == 0 else "class",
                    "name": f"entity_{i}",
                    "path": f"src/file_{i % 100}.py",
                    "lines": [i % 100, (i % 100) + 10],
                    "docstring": f"Docstring for entity {i}",
                    "repo_id": "large-repo",
                    "blame": None
                }
            })

        # Generate edges (roughly 2 edges per node on average)
        large_edges = []
        for i in range(10000):
            source_idx = i % 5000
            target_idx = (i * 7) % 5000  # Pseudo-random distribution
            large_edges.append({
                "source": f"src/file_{source_idx % 100}.py",
                "target": f"node_{target_idx}",
                "edge_type": "CALLS" if i % 3 == 0 else "IMPORTS",
                "line": i % 100
            })

        # Mock Neo4j queries
        mock_neo4j_client.execute_query.side_effect = [large_nodes, large_edges]

        # Measure time
        start_time = time.time()
        snapshot_id = await snapshot_service.create_snapshot("large-repo", "large-sha")
        end_time = time.time()

        elapsed = end_time - start_time

        # Verify performance requirement: < 3 seconds for 5K nodes
        assert elapsed < 3.0, f"Snapshot creation took {elapsed:.2f}s, expected < 3.0s"

        # Verify result
        assert snapshot_id == "test-snapshot-id"

        # Verify data was processed correctly
        call_args = mock_postgres_storage.create_snapshot.call_args
        nodes = call_args[0][2]
        edges = call_args[0][3]
        assert len(nodes) == 5000
        assert len(edges) == 10000