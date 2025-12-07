"""PostgreSQL storage for graph snapshots."""

import asyncpg
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from ..models.node import Node
from ..models.edge import Edge
from ..config.settings import settings


class GraphSnapshot:
    """Represents a graph snapshot."""

    def __init__(self, snapshot_id: str, repo_id: str, sha: str, created_at: datetime,
                 node_count: int, edge_count: int):
        self.snapshot_id = snapshot_id
        self.repo_id = repo_id
        self.sha = sha
        self.created_at = created_at
        self.node_count = node_count
        self.edge_count = edge_count


class PostgresSnapshotStorage:
    """PostgreSQL storage for graph snapshots."""

    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or settings.postgres_url

    @asynccontextmanager
    async def connection(self):
        """Get database connection."""
        conn = await asyncpg.connect(self.connection_string)
        try:
            yield conn
        finally:
            await conn.close()

    async def create_tables(self):
        """Create snapshot tables."""
        async with self.connection() as conn:
            # Graph snapshots table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS graph_snapshots (
                    snapshot_id UUID PRIMARY KEY,
                    repo_id UUID NOT NULL,
                    sha TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    node_count INTEGER NOT NULL,
                    edge_count INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_graph_snapshots_repo_sha
                ON graph_snapshots (repo_id, sha);

                CREATE INDEX IF NOT EXISTS idx_graph_snapshots_created_at
                ON graph_snapshots (created_at);
            """)

            # Snapshot nodes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_nodes (
                    snapshot_id UUID NOT NULL REFERENCES graph_snapshots(snapshot_id) ON DELETE CASCADE,
                    node_id TEXT NOT NULL,
                    node_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    lines INTEGER[],
                    docstring TEXT,
                    blame JSONB,
                    PRIMARY KEY (snapshot_id, node_id)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshot_nodes_snapshot_type
                ON snapshot_nodes (snapshot_id, node_type);

                CREATE INDEX IF NOT EXISTS idx_snapshot_nodes_snapshot_path
                ON snapshot_nodes (snapshot_id, path);
            """)

            # Snapshot edges table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_edges (
                    snapshot_id UUID NOT NULL REFERENCES graph_snapshots(snapshot_id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    line_number INTEGER,
                    PRIMARY KEY (snapshot_id, source_id, target_id, edge_type)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshot_edges_snapshot_source
                ON snapshot_edges (snapshot_id, source_id);

                CREATE INDEX IF NOT EXISTS idx_snapshot_edges_snapshot_target
                ON snapshot_edges (snapshot_id, target_id);

                CREATE INDEX IF NOT EXISTS idx_snapshot_edges_snapshot_type
                ON snapshot_edges (snapshot_id, edge_type);
            """)

    async def create_snapshot(self, repo_id: str, sha: str, nodes: List[Node], edges: List[Edge]) -> str:
        """Create a new graph snapshot."""
        snapshot_id = str(uuid.uuid4())

        async with self.connection() as conn:
            async with conn.transaction():
                # Insert snapshot metadata
                await conn.execute("""
                    INSERT INTO graph_snapshots (snapshot_id, repo_id, sha, node_count, edge_count)
                    VALUES ($1, $2, $3, $4, $5)
                """, snapshot_id, repo_id, sha, len(nodes), len(edges))

                # Batch insert nodes
                if nodes:
                    node_records = []
                    for node in nodes:
                        blame_data = None
                        if node.blame:
                            blame_data = {
                                'primary_author': node.blame.primary_author,
                                'contributors': node.blame.contributors,
                                'author_distribution': dict(node.blame.author_distribution)
                            }

                        node_records.append((
                            snapshot_id,
                            node.id,
                            node.type,
                            node.name,
                            node.path,
                            node.lines,
                            node.docstring,
                            blame_data
                        ))

                    await conn.executemany("""
                        INSERT INTO snapshot_nodes
                        (snapshot_id, node_id, node_type, name, path, lines, docstring, blame)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, node_records)

                # Batch insert edges
                if edges:
                    edge_records = []
                    for edge in edges:
                        edge_records.append((
                            snapshot_id,
                            edge.source,
                            edge.target,
                            edge.type,
                            edge.line
                        ))

                    await conn.executemany("""
                        INSERT INTO snapshot_edges
                        (snapshot_id, source_id, target_id, edge_type, line_number)
                        VALUES ($1, $2, $3, $4, $5)
                    """, edge_records)

        return snapshot_id

    async def get_snapshot(self, snapshot_id: str) -> Optional[GraphSnapshot]:
        """Get snapshot metadata by ID."""
        async with self.connection() as conn:
            row = await conn.fetchrow("""
                SELECT snapshot_id, repo_id, sha, created_at, node_count, edge_count
                FROM graph_snapshots
                WHERE snapshot_id = $1
            """, snapshot_id)

            if row:
                return GraphSnapshot(**row)
            return None

    async def get_snapshots_for_repo(self, repo_id: str) -> List[GraphSnapshot]:
        """Get all snapshots for a repository."""
        async with self.connection() as conn:
            rows = await conn.fetch("""
                SELECT snapshot_id, repo_id, sha, created_at, node_count, edge_count
                FROM graph_snapshots
                WHERE repo_id = $1
                ORDER BY created_at DESC
            """, repo_id)

            return [GraphSnapshot(**row) for row in rows]

    async def get_snapshot_for_sha(self, repo_id: str, sha: str) -> Optional[GraphSnapshot]:
        """Get snapshot for a specific SHA."""
        async with self.connection() as conn:
            row = await conn.fetchrow("""
                SELECT snapshot_id, repo_id, sha, created_at, node_count, edge_count
                FROM graph_snapshots
                WHERE repo_id = $1 AND sha = $2
            """, repo_id, sha)

            if row:
                return GraphSnapshot(**row)
            return None

    async def get_snapshot_nodes(self, snapshot_id: str) -> List[Dict[str, Any]]:
        """Get all nodes for a snapshot."""
        async with self.connection() as conn:
            rows = await conn.fetch("""
                SELECT node_id, node_type, name, path, lines, docstring, blame
                FROM snapshot_nodes
                WHERE snapshot_id = $1
                ORDER BY node_id
            """, snapshot_id)

            nodes = []
            for row in rows:
                node_data = dict(row)
                # Convert blame JSON back to object if needed
                if node_data['blame']:
                    # For now, return as dict - consumer can convert to BlameInfo if needed
                    pass
                nodes.append(node_data)
            return nodes

    async def get_snapshot_edges(self, snapshot_id: str) -> List[Dict[str, Any]]:
        """Get all edges for a snapshot."""
        async with self.connection() as conn:
            rows = await conn.fetch("""
                SELECT source_id, target_id, edge_type, line_number
                FROM snapshot_edges
                WHERE snapshot_id = $1
                ORDER BY source_id, target_id
            """, snapshot_id)

            return [dict(row) for row in rows]

    async def delete_snapshot(self, snapshot_id: str):
        """Delete a snapshot and all its data."""
        async with self.connection() as conn:
            # Due to CASCADE constraints, deleting from graph_snapshots will delete nodes and edges
            await conn.execute("""
                DELETE FROM graph_snapshots WHERE snapshot_id = $1
            """, snapshot_id)

    async def get_snapshot_stats(self, repo_id: str) -> Dict[str, Any]:
        """Get statistics about snapshots for a repository."""
        async with self.connection() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_snapshots,
                    MAX(created_at) as latest_snapshot,
                    AVG(node_count) as avg_nodes,
                    AVG(edge_count) as avg_edges,
                    SUM(node_count) as total_nodes,
                    SUM(edge_count) as total_edges
                FROM graph_snapshots
                WHERE repo_id = $1
            """, repo_id)

            return dict(row) if row else {}