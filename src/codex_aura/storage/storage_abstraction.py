"""Storage backend abstraction for codex-aura."""

import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional

from ..models.graph import Graph
from ..models.node import Node
from .neo4j_client import Neo4jClient, GraphQueries
from .sqlite import SQLiteStorage


class StorageBackend(str, Enum):
    """Storage backend types."""
    SQLITE = "sqlite"
    NEO4J = "neo4j"


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


class SQLiteStorageBackend(GraphStorage):
    """SQLite storage backend implementation."""

    def __init__(self, db_path: str = "codex_aura.db"):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.storage = SQLiteStorage(db_path)

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
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")