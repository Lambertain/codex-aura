"""Storage backend abstraction for codex-aura."""

import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict
from contextlib import asynccontextmanager

from ..models.graph import Graph
from ..models.node import Node
from ..models.edge import Edge
from .neo4j_client import Neo4jClient, GraphQueries
from .sqlite import SQLiteStorage
from .postgres_snapshots import PostgresSnapshotStorage, GraphSnapshot


class StorageBackend(str, Enum):
    """Storage backend types."""
    SQLITE = "sqlite"
    NEO4J = "neo4j"
    POSTGRES = "postgres"


class GraphStorage(ABC):
    """Abstract base class for graph storage backends."""

    @abstractmethod
    async def save_graph(self, graph: Graph) -> str:
        """
        Save a graph to storage.

        Args:
            graph: The graph to save

        Returns:
            Graph ID
        """
        pass

    @abstractmethod
    async def load_graph(self, graph_id: str) -> Optional[Graph]:
        """
        Load a graph from storage.

        Args:
            graph_id: Unique identifier for the graph

        Returns:
            The loaded graph or None if not found
        """
        pass

    @abstractmethod
    async def query_dependencies(self, fqn: str, depth: int = 2) -> List[Node]:
        """
        Query dependencies for a node.

        Args:
            fqn: Fully qualified name of the node
            depth: Maximum depth to traverse

        Returns:
            List of dependent nodes
        """
        pass

    @abstractmethod
    async def query_dependencies_weighted(
        self,
        fqn: str,
        edge_weights: Dict[str, float],
        weight_threshold: float = 0.1
    ) -> List[Node]:
        """
        Query dependencies using weighted expansion.

        Args:
            fqn: Fully qualified name of the node
            edge_weights: Dictionary mapping edge types to weights
            weight_threshold: Stop expansion when edge weight < threshold

        Returns:
            List of dependent nodes ordered by cumulative weight
        """
        pass

    async def get_dependencies_weighted(
        self,
        repo_id: str,
        fqn: str,
        edge_weights: Dict[str, float],
        weight_threshold: float = 0.1
    ) -> List[Node]:
        """
        Get dependencies using weighted expansion for a specific repo.

        This is a convenience method that calls query_dependencies_weighted.
        """
        return await self.query_dependencies_weighted(fqn, edge_weights, weight_threshold)

    @abstractmethod
    async def get_all_nodes(self, repo_id: str) -> List[Node]:
        """
        Get all nodes for a repository.

        Args:
            repo_id: Repository identifier

        Returns:
            List of all nodes
        """
        pass

    @abstractmethod
    @asynccontextmanager
    async def transaction(self, repo_id: str):
        """
        Context manager for database transactions.

        Args:
            repo_id: Repository identifier for the transaction

        Yields:
            Transaction object for performing operations
        """
        pass

    @abstractmethod
    async def create_snapshot(self, repo_id: str, sha: str, nodes: List[Node], edges: List[Edge]) -> str:
        """
        Create a snapshot of the graph for a specific SHA.

        Args:
            repo_id: Repository identifier
            sha: Git SHA for the snapshot
            nodes: List of nodes in the graph
            edges: List of edges in the graph

        Returns:
            Snapshot ID
        """
        pass

    @abstractmethod
    async def get_snapshot(self, snapshot_id: str) -> Optional[GraphSnapshot]:
        """
        Get snapshot metadata by ID.

        Args:
            snapshot_id: Unique snapshot identifier

        Returns:
            GraphSnapshot object or None if not found
        """
        pass

    @abstractmethod
    async def get_snapshots_for_repo(self, repo_id: str) -> List[GraphSnapshot]:
        """
        Get all snapshots for a repository.

        Args:
            repo_id: Repository identifier

        Returns:
            List of GraphSnapshot objects
        """
        pass


class SQLiteGraphTransaction:
    """SQLite transaction implementation for incremental updates."""

    def __init__(self, storage: SQLiteStorage, repo_id: str):
        self.storage = storage
        self.repo_id = repo_id
        self._conn = None
        self._cursor = None

    async def __aenter__(self):
        import sqlite3
        self._conn = sqlite3.connect(self.storage.db_path)
        self._conn.row_factory = sqlite3.Row
        self._cursor = self._conn.cursor()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()
        self._conn = None
        self._cursor = None

    async def upsert_node(self, node) -> None:
        """Upsert a node to the nodes table."""
        import json
        fqn = node.path if node.type == "file" else node.id
        node_data = node.model_dump_json()

        self._cursor.execute("""
            INSERT OR REPLACE INTO nodes
            (fqn, repo_id, type, path, name, node_data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, (fqn, self.repo_id, node.type, node.path, node.name, node_data))

    async def run(self, query: str, **parameters) -> list:
        """Run a raw query (limited support for SQLite)."""
        # SQLite doesn't support Cypher, so this is a no-op placeholder
        # Real implementations should use SQLite-specific methods
        return []

    async def find_node_by_fqn(self, fqn: str):
        """Find node by fully qualified name."""
        from ..models.node import Node

        self._cursor.execute("""
            SELECT node_data FROM nodes
            WHERE fqn = ? AND repo_id = ?
        """, (fqn, self.repo_id))

        row = self._cursor.fetchone()
        if row:
            return Node.model_validate_json(row["node_data"])
        return None

    async def create_edge(self, source_fqn: str, target_fqn: str, edge_type, metadata=None) -> None:
        """Create an edge between nodes."""
        import json
        edge_type_value = edge_type.value if hasattr(edge_type, 'value') else str(edge_type)
        metadata_json = json.dumps(metadata) if metadata else None

        self._cursor.execute("""
            INSERT OR REPLACE INTO edges
            (source_fqn, target_fqn, edge_type, repo_id, metadata, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (source_fqn, target_fqn, edge_type_value, self.repo_id, metadata_json))

    async def delete_edges_for_node(self, fqn: str) -> int:
        """Delete all edges from/to a node."""
        self._cursor.execute("""
            DELETE FROM edges
            WHERE repo_id = ? AND (source_fqn = ? OR target_fqn = ?)
        """, (self.repo_id, fqn, fqn))
        return self._cursor.rowcount

    async def delete_outgoing_edges(self, fqn: str) -> int:
        """Delete all outgoing edges from a node."""
        self._cursor.execute("""
            DELETE FROM edges
            WHERE repo_id = ? AND source_fqn = ?
        """, (self.repo_id, fqn))
        return self._cursor.rowcount

    async def node_exists(self, fqn: str) -> bool:
        """Check if node exists."""
        self._cursor.execute("""
            SELECT 1 FROM nodes WHERE fqn = ? AND repo_id = ? LIMIT 1
        """, (fqn, self.repo_id))
        return self._cursor.fetchone() is not None

    async def create_external_ref(self, source_fqn: str, ref) -> None:
        """Create external reference."""
        edge_type_value = ref.edge_type.value if hasattr(ref.edge_type, 'value') else str(ref.edge_type)

        # First create external ref node if it doesn't exist
        self._cursor.execute("""
            INSERT OR IGNORE INTO nodes
            (fqn, repo_id, type, path, name, node_data, updated_at)
            VALUES (?, ?, 'external', ?, ?, '{}', datetime('now'))
        """, (ref.target_fqn, self.repo_id, ref.target_fqn, ref.target_fqn))

        # Then create the edge
        self._cursor.execute("""
            INSERT OR REPLACE INTO edges
            (source_fqn, target_fqn, edge_type, repo_id, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (source_fqn, ref.target_fqn, edge_type_value, self.repo_id))


class SQLiteStorageBackend(GraphStorage):
    """SQLite storage backend implementation."""

    def __init__(self, db_path: str = "codex_aura.db"):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.storage = SQLiteStorage(db_path)
        self._ensure_incremental_tables()

    def _ensure_incremental_tables(self):
        """Ensure tables for incremental updates exist."""
        import sqlite3
        with sqlite3.connect(self.storage.db_path) as conn:
            # Create nodes table for incremental updates
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    fqn TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    path TEXT,
                    name TEXT,
                    node_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (fqn, repo_id)
                )
            """)

            # Create edges table for incremental updates
            conn.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    source_fqn TEXT NOT NULL,
                    target_fqn TEXT NOT NULL,
                    edge_type TEXT NOT NULL,
                    repo_id TEXT NOT NULL,
                    metadata TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source_fqn, target_fqn, edge_type, repo_id)
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_nodes_repo_id
                ON nodes(repo_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edges_repo_id
                ON edges(repo_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edges_source
                ON edges(source_fqn, repo_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_edges_target
                ON edges(target_fqn, repo_id)
            """)

            conn.commit()

    @asynccontextmanager
    async def transaction(self, repo_id: str):
        """
        Context manager for SQLite transactions.

        Args:
            repo_id: Repository identifier

        Yields:
            SQLiteGraphTransaction object
        """
        txn = SQLiteGraphTransaction(self.storage, repo_id)
        async with txn:
            yield txn

    async def save_graph(self, graph: Graph) -> str:
        """Save a graph to SQLite storage."""
        graph_id = f"{graph.repository.name}_{graph.sha or 'latest'}"
        self.storage.save_graph(graph, graph_id)
        return graph_id

    async def load_graph(self, graph_id: str) -> Optional[Graph]:
        """Load a graph from SQLite storage."""
        return self.storage.load_graph(graph_id)

    async def query_dependencies(self, fqn: str, depth: int = 2) -> List[Node]:
        """Query dependencies from SQLite storage."""
        # For SQLite, we need to find the graph first
        # This is a simplified implementation - in practice, we'd need graph_id
        # For now, assume we query the latest graph
        graphs = self.storage.list_graphs()
        if not graphs:
            return []

        latest_graph = graphs[0]  # Assuming sorted by created_at desc
        graph = self.storage.load_graph(latest_graph["id"])
        if not graph:
            return []

        # Find node by fqn
        target_node = None
        for node in graph.nodes:
            if (node.type == "file" and node.path == fqn) or (node.type != "file" and node.id == fqn):
                target_node = node
                break

        if not target_node:
            return []

        # Use existing traversal logic
        visited, _ = self.storage._traverse_dependencies(graph, target_node.id, depth, "outgoing")
        visited.remove(target_node.id)  # Remove the starting node

        # Convert node ids back to Node objects
        nodes = []
        for node_id in visited:
            node = next((n for n in graph.nodes if n.id == node_id), None)
            if node:
                nodes.append(node)

        return nodes

    async def query_dependencies_weighted(
        self,
        fqn: str,
        edge_weights: Dict[str, float],
        weight_threshold: float = 0.1
    ) -> List[Node]:
        """Query dependencies using weighted expansion - not implemented for SQLite."""
        # For now, fall back to depth-based expansion
        return await self.query_dependencies(fqn, depth=2)

    async def get_all_nodes(self, repo_id: str) -> List[Node]:
        """Get all nodes for a repository from SQLite storage."""
        graphs = self.storage.list_graphs()
        if not graphs:
            return []

        # Find graph by repo_id pattern
        graph_id = None
        for graph in graphs:
            if repo_id in graph["id"]:
                graph_id = graph["id"]
                break

        if not graph_id:
            return []

        graph = self.storage.load_graph(graph_id)
        return graph.nodes if graph else []

    async def create_snapshot(self, repo_id: str, sha: str, nodes: List[Node], edges: List[Edge]) -> str:
        """Create a snapshot - not implemented for SQLite."""
        # SQLite doesn't support snapshots in this implementation
        raise NotImplementedError("Snapshots not supported in SQLite backend")

    async def get_snapshot(self, snapshot_id: str) -> Optional[GraphSnapshot]:
        """Get snapshot - not implemented for SQLite."""
        return None

    async def get_snapshots_for_repo(self, repo_id: str) -> List[GraphSnapshot]:
        """Get snapshots - not implemented for SQLite."""
        return []


class Neo4jStorageBackend(GraphStorage):
    """Neo4j storage backend implementation."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        """Initialize Neo4j storage.

        Args:
            client: Neo4jClient instance, creates default if None
        """
        self.client = client or Neo4jClient()
        self.queries = GraphQueries(self.client)

    async def save_graph(self, graph: Graph) -> str:
        """Save a graph to Neo4j storage."""
        graph_id = f"{graph.repository.name}_{graph.sha or 'latest'}"
        await self.client.migrate_graph_to_neo4j(graph)
        return graph_id

    async def load_graph(self, graph_id: str) -> Optional[Graph]:
        """Load a graph from Neo4j storage."""
        # Neo4j doesn't store complete graphs like SQLite
        # This would require reconstructing the graph from nodes/edges
        # For now, return None as this is complex
        return None

    async def query_dependencies(self, fqn: str, depth: int = 2) -> List[Node]:
        """Query dependencies from Neo4j storage."""
        return await self.queries.get_dependencies(fqn, depth)

    async def query_dependencies_weighted(
        self,
        fqn: str,
        edge_weights: Dict[str, float],
        weight_threshold: float = 0.1
    ) -> List[Node]:
        """Query dependencies using weighted expansion from Neo4j storage."""
        return await self.queries.get_dependencies_weighted(fqn, edge_weights, weight_threshold)

    async def get_all_nodes(self, repo_id: str) -> List[Node]:
        """Get all nodes for a repository from Neo4j storage."""
        # This would require implementing a query to get all nodes for a repo
        # For now, return empty list as this is complex
        return []

    @asynccontextmanager
    async def transaction(self, repo_id: str):
        """
        Context manager for Neo4j transactions.

        Args:
            repo_id: Repository identifier

        Yields:
            GraphTransaction object
        """
        from ..sync.incremental import Neo4jGraphTransaction
        async with self.client.session() as session:
            txn = Neo4jGraphTransaction(session, repo_id)
            try:
                yield txn
                # If we get here without exception, commit is implicit
            except Exception:
                # Rollback would happen automatically on session exit
                raise

    async def create_snapshot(self, repo_id: str, sha: str, nodes: List[Node], edges: List[Edge]) -> str:
        """Create a snapshot - not implemented for Neo4j."""
        # Neo4j doesn't use snapshots in this implementation
        raise NotImplementedError("Snapshots not supported in Neo4j backend")

    async def get_snapshot(self, snapshot_id: str) -> Optional[GraphSnapshot]:
        """Get snapshot - not implemented for Neo4j."""
        return None

    async def get_snapshots_for_repo(self, repo_id: str) -> List[GraphSnapshot]:
        """Get snapshots - not implemented for Neo4j."""
        return []


class PostgresGraphTransaction:
    """PostgreSQL transaction implementation for incremental updates."""

    def __init__(self, snapshot_storage, repo_id: str):
        self.snapshot_storage = snapshot_storage
        self.repo_id = repo_id
        self._operations = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # PostgreSQL transactions are handled by the connection pool
        pass

    async def upsert_node(self, node) -> None:
        """Upsert a node - stores operation for batch commit."""
        self._operations.append(("upsert_node", node))

    async def run(self, query: str, **parameters) -> list:
        """Run a query - not directly supported, use specific methods."""
        return []

    async def find_node_by_fqn(self, fqn: str):
        """Find node by FQN - not implemented for PostgreSQL yet."""
        return None

    async def create_edge(self, source_fqn: str, target_fqn: str, edge_type, metadata=None) -> None:
        """Create an edge - stores operation for batch commit."""
        self._operations.append(("create_edge", source_fqn, target_fqn, edge_type, metadata))

    async def delete_edges_for_node(self, fqn: str) -> int:
        """Delete edges for node - not fully implemented."""
        self._operations.append(("delete_edges", fqn))
        return 0

    async def delete_outgoing_edges(self, fqn: str) -> int:
        """Delete outgoing edges - not fully implemented."""
        self._operations.append(("delete_outgoing_edges", fqn))
        return 0

    async def node_exists(self, fqn: str) -> bool:
        """Check if node exists - not implemented for PostgreSQL yet."""
        return False

    async def create_external_ref(self, source_fqn: str, ref) -> None:
        """Create external reference."""
        self._operations.append(("create_external_ref", source_fqn, ref))


class PostgresStorageBackend(GraphStorage):
    """PostgreSQL storage backend implementation."""

    def __init__(self, connection_string: Optional[str] = None):
        """Initialize PostgreSQL storage.

        Args:
            connection_string: PostgreSQL connection string, uses settings if None
        """
        from .postgres_snapshots import PostgresSnapshotStorage
        self.snapshot_storage = PostgresSnapshotStorage(connection_string)
        # For now, we'll use snapshots for graph storage too
        # In a full implementation, we'd have separate storage for current graphs

    async def save_graph(self, graph: Graph) -> str:
        """Save a graph to PostgreSQL storage via snapshots."""
        # For now, create a snapshot for the graph
        # In production, we'd have separate current graph storage
        snapshot_id = await self.create_snapshot(
            str(graph.repository.id) if graph.repository else "unknown",
            graph.sha or "latest",
            graph.nodes,
            graph.edges
        )
        return snapshot_id

    async def load_graph(self, graph_id: str) -> Optional[Graph]:
        """Load a graph from PostgreSQL storage."""
        # This is complex - would need to reconstruct Graph from snapshot data
        # For now, return None
        return None

    async def query_dependencies(self, fqn: str, depth: int = 2) -> List[Node]:
        """Query dependencies from PostgreSQL storage."""
        # This would require implementing graph traversal logic
        # For now, return empty list
        return []

    async def query_dependencies_weighted(
        self,
        fqn: str,
        edge_weights: Dict[str, float],
        weight_threshold: float = 0.1
    ) -> List[Node]:
        """Query dependencies using weighted expansion - not implemented for PostgreSQL."""
        # For now, return empty list
        return []

    async def get_all_nodes(self, repo_id: str) -> List[Node]:
        """Get all nodes for a repository from PostgreSQL storage."""
        # Get latest snapshot and return its nodes
        snapshots = await self.get_snapshots_for_repo(repo_id)
        if not snapshots:
            return []

        latest_snapshot = snapshots[0]  # Already sorted by created_at desc
        nodes_data = await self.snapshot_storage.get_snapshot_nodes(latest_snapshot.snapshot_id)

        # Convert dict data back to Node objects
        nodes = []
        for node_data in nodes_data:
            # This is a simplified conversion - in practice, we'd need proper Node construction
            # For now, return empty list as proper conversion is complex
            pass
        return nodes

    @asynccontextmanager
    async def transaction(self, repo_id: str):
        """Context manager for PostgreSQL transactions."""
        txn = PostgresGraphTransaction(self.snapshot_storage, repo_id)
        async with txn:
            yield txn

    async def create_snapshot(self, repo_id: str, sha: str, nodes: List[Node], edges: List[Edge]) -> str:
        """Create a snapshot of the graph for a specific SHA."""
        return await self.snapshot_storage.create_snapshot(repo_id, sha, nodes, edges)

    async def get_snapshot(self, snapshot_id: str) -> Optional[GraphSnapshot]:
        """Get snapshot metadata by ID."""
        return await self.snapshot_storage.get_snapshot(snapshot_id)

    async def get_snapshots_for_repo(self, repo_id: str) -> List[GraphSnapshot]:
        """Get all snapshots for a repository."""
        return await self.snapshot_storage.get_snapshots_for_repo(repo_id)


def get_storage(backend: Optional[StorageBackend] = None) -> GraphStorage:
    """
    Get storage backend instance based on configuration.

    Args:
        backend: Storage backend type, reads from env if None

    Returns:
        GraphStorage instance
    """
    if backend is None:
        backend_str = os.getenv("STORAGE_BACKEND", "sqlite").lower()
        try:
            backend = StorageBackend(backend_str)
        except ValueError:
            backend = StorageBackend.SQLITE

    if backend == StorageBackend.SQLITE:
        return SQLiteStorageBackend()
    elif backend == StorageBackend.NEO4J:
        return Neo4jStorageBackend()
    elif backend == StorageBackend.POSTGRES:
        return PostgresStorageBackend()
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")