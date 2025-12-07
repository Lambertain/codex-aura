"""Snapshot service for creating graph snapshots."""

import logging
import time
from typing import List, Optional
from uuid import UUID

from ..models.node import Node, BlameInfo
from ..models.edge import Edge, EdgeType
from ..storage.neo4j_client import Neo4jClient
from ..storage.postgres_snapshots import PostgresSnapshotStorage

logger = logging.getLogger(__name__)


class SnapshotService:
    """Service for creating and managing graph snapshots."""

    def __init__(
        self,
        neo4j_client: Optional[Neo4jClient] = None,
        postgres_storage: Optional[PostgresSnapshotStorage] = None
    ):
        self.neo4j_client = neo4j_client or Neo4jClient()
        self.postgres_storage = postgres_storage or PostgresSnapshotStorage()

    async def create_snapshot(self, repo_id: str, sha: str) -> str:
        """
        Create a snapshot of the current graph state for a repository.

        Args:
            repo_id: Repository identifier
            sha: Commit SHA for the snapshot

        Returns:
            Snapshot ID

        Raises:
            Exception: If snapshot creation fails
        """
        start_time = time.time()
        logger.info(f"Starting snapshot creation for repo {repo_id}, SHA {sha}")

        try:
            # Get all nodes for the repository from Neo4j
            nodes = await self._get_nodes_for_repo(repo_id)
            logger.info(f"Retrieved {len(nodes)} nodes for repo {repo_id}")

            # Get all edges for the repository from Neo4j
            edges = await self._get_edges_for_repo(repo_id)
            logger.info(f"Retrieved {len(edges)} edges for repo {repo_id}")

            # Create snapshot in PostgreSQL
            snapshot_id = await self.postgres_storage.create_snapshot(repo_id, sha, nodes, edges)

            elapsed_time = time.time() - start_time
            logger.info(f"Snapshot {snapshot_id} created successfully in {elapsed_time:.2f}s")

            return snapshot_id

        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Failed to create snapshot for repo {repo_id}, SHA {sha} after {elapsed_time:.2f}s: {e}")
            raise

    async def _get_nodes_for_repo(self, repo_id: str) -> List[Node]:
        """Get all nodes for a repository from Neo4j."""
        query = """
        MATCH (n:Node)
        WHERE n.repo_id = $repo_id
        RETURN n
        ORDER BY n.fqn
        """

        results = await self.neo4j_client.execute_query(query, {"repo_id": repo_id})
        nodes = []

        for record in results:
            node_data = dict(record["n"])

            # Convert blame data back to BlameInfo if present
            if node_data.get("blame"):
                blame_dict = node_data["blame"]
                node_data["blame"] = BlameInfo(**blame_dict)

            # Create Node object
            node = Node(**node_data)
            nodes.append(node)

        return nodes

    async def _get_edges_for_repo(self, repo_id: str) -> List[Edge]:
        """Get all edges for a repository from Neo4j."""
        query = """
        MATCH (a:Node)-[r]->(b:Node)
        WHERE a.repo_id = $repo_id
        RETURN a.fqn as source, b.fqn as target, type(r) as edge_type, r.line as line
        ORDER BY a.fqn, b.fqn
        """

        results = await self.neo4j_client.execute_query(query, {"repo_id": repo_id})
        edges = []

        for record in results:
            edge = Edge(
                source=record["source"],
                target=record["target"],
                type=EdgeType(record["edge_type"]),
                line=record["line"]
            )
            edges.append(edge)

        return edges