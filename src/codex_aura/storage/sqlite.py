"""SQLite storage backend for codex-aura."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple
from collections import deque

from ..models.graph import Graph, load_graph, save_graph
from ..models.edge import Edge, EdgeType


class SQLiteStorage:
    """SQLite storage backend for graphs."""

    def __init__(self, db_path: str = "codex_aura.db"):
        """Initialize SQLite storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables and run migrations."""
        with sqlite3.connect(self.db_path) as conn:
            # Create migrations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
            """)

            # Create graphs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS graphs (
                    id TEXT PRIMARY KEY,
                    repo_name TEXT NOT NULL,
                    repo_path TEXT NOT NULL,
                    sha TEXT,
                    created_at TEXT NOT NULL,
                    graph_data TEXT NOT NULL
                )
            """)

            # Create services table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    service_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    repo_id TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create usage_events table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    tokens_used INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on user_id and timestamp for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_user_timestamp
                ON usage_events(user_id, timestamp)
            """)

            # Create index on repo_id for services
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_services_repo_id
                ON services(repo_id)
            """)

            conn.commit()

        self._run_migrations()

    def save_graph(self, graph: Graph, graph_id: str) -> None:
        """Save a graph to storage.

        Args:
            graph: The graph to save
            graph_id: Unique identifier for the graph
        """
        # Save graph data as JSON
        graph_json = graph.model_dump_json()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO graphs
                (id, repo_name, repo_path, sha, created_at, graph_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                graph_id,
                graph.repository.name,
                graph.repository.path,
                None,  # sha - could be computed from git
                graph.generated_at.isoformat(),
                graph_json
            ))
            conn.commit()

    def load_graph(self, graph_id: str) -> Optional[Graph]:
        """Load a graph from storage.

        Args:
            graph_id: Unique identifier for the graph

        Returns:
            The loaded graph or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT graph_data FROM graphs WHERE id = ?
            """, (graph_id,))

            row = cursor.fetchone()
            if row:
                return Graph.model_validate_json(row[0])
            return None

    def list_graphs(self, repo_path: Optional[str] = None) -> List[dict]:
        """List all stored graphs.

        Args:
            repo_path: Optional filter by repository path

        Returns:
            List of graph information dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            if repo_path:
                cursor = conn.execute("""
                    SELECT id, repo_name, repo_path, sha, created_at, graph_data
                    FROM graphs
                    WHERE repo_path = ?
                    ORDER BY created_at DESC
                """, (repo_path,))
            else:
                cursor = conn.execute("""
                    SELECT id, repo_name, repo_path, sha, created_at, graph_data
                    FROM graphs
                    ORDER BY created_at DESC
                """)

            graphs = []
            for row in cursor.fetchall():
                graph_id, repo_name, repo_path, sha, created_at_str, graph_data = row

                # Parse graph data to get stats
                graph = Graph.model_validate_json(graph_data)

                graphs.append({
                    "id": graph_id,
                    "repo_name": repo_name,
                    "repo_path": repo_path,
                    "sha": sha,
                    "created_at": datetime.fromisoformat(created_at_str),
                    "node_count": graph.stats.total_nodes,
                    "edge_count": graph.stats.total_edges
                })

            return graphs

    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph from storage.

        Args:
            graph_id: Unique identifier for the graph

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM graphs WHERE id = ?", (graph_id,))
            conn.commit()
            return cursor.rowcount > 0

    def query_nodes(self, graph_id: str, node_types: Optional[List[str]] = None,
                   path_filter: Optional[str] = None) -> List:
        """Query nodes from a stored graph.

        Args:
            graph_id: Graph identifier
            node_types: Filter by node types
            path_filter: Filter by path substring

        Returns:
            List of Node objects
        """
        graph = self.load_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        nodes = graph.nodes

        if node_types:
            nodes = [n for n in nodes if n.type in node_types]

        if path_filter:
            nodes = [n for n in nodes if path_filter in n.path]

        return nodes

    def query_edges(self, graph_id: str, edge_types: Optional[List[str]] = None,
                   source_filter: Optional[str] = None, target_filter: Optional[str] = None) -> List[Edge]:
        """Query edges from a stored graph.

        Args:
            graph_id: Graph identifier
            edge_types: Filter by edge types
            source_filter: Filter by source node substring
            target_filter: Filter by target node substring

        Returns:
            List of Edge objects
        """
        graph = self.load_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        edges = graph.edges

        if edge_types:
            edges = [e for e in edges if e.type.value in edge_types]

        if source_filter:
            edges = [e for e in edges if source_filter in e.source]

        if target_filter:
            edges = [e for e in edges if target_filter in e.target]

        return edges

    def query_dependencies(self, graph_id: str, node_id: str, direction: str = "both",
                          max_depth: int = 2, edge_types: Optional[List[str]] = None) -> Tuple[Set[str], Set[Tuple[str, str, str]]]:
        """Query dependencies for a node using BFS traversal.

        Args:
            graph_id: Graph identifier
            node_id: Starting node ID
            direction: "incoming", "outgoing", or "both"
            max_depth: Maximum traversal depth
            edge_types: Filter by edge types

        Returns:
            Tuple of (node_ids, edges) where edges are (source, target, type) tuples
        """
        graph = self.load_graph(graph_id)
        if not graph:
            raise ValueError(f"Graph {graph_id} not found")

        return self._traverse_dependencies(graph, node_id, max_depth, direction, edge_types)

    def _traverse_dependencies(self, graph: Graph, start_node_id: str, max_depth: int,
                              direction: str, edge_types: Optional[List[str]] = None) -> Tuple[Set[str], Set[Tuple[str, str, str]]]:
        """Internal method for dependency traversal."""
        visited = set([start_node_id])
        edges = set()
        queue = deque([(start_node_id, 0)])  # (node_id, depth)

        while queue:
            current_node_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Get edges based on direction
            if direction in ["outgoing", "both"]:
                outgoing = [e for e in graph.edges if e.source == current_node_id]
                if edge_types:
                    outgoing = [e for e in outgoing if e.type.value in edge_types]

                for edge in outgoing:
                    if edge.target not in visited:
                        visited.add(edge.target)
                        queue.append((edge.target, depth + 1))
                    edges.add((edge.source, edge.target, edge.type.value))

            if direction in ["incoming", "both"]:
                incoming = [e for e in graph.edges if e.target == current_node_id]
                if edge_types:
                    incoming = [e for e in incoming if e.type.value in edge_types]

                for edge in incoming:
                    if edge.source not in visited:
                        visited.add(edge.source)
                        queue.append((edge.source, depth + 1))
                    edges.add((edge.source, edge.target, edge.type.value))

        return visited, edges

    def _run_migrations(self):
        """Run database migrations."""
        current_version = self._get_schema_version()

        # Migration 1: Initial schema (already applied in _init_db)
        if current_version < 1:
            # Already handled in _init_db
            self._apply_migration(1, "initial_schema")

        # Migration 2: Add services table
        if current_version < 2:
            with sqlite3.connect(self.db_path) as conn:
                # Create services table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS services (
                        service_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        repo_id TEXT NOT NULL UNIQUE,
                        description TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create index on repo_id for services
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_services_repo_id
                    ON services(repo_id)
                """)

                conn.commit()

            self._apply_migration(2, "add_services_table")

        # Future migrations can be added here
        # if current_version < 3:
        #     # Add new table/index
        #     self._apply_migration(3, "add_indexes")

    def _get_schema_version(self) -> int:
        """Get current schema version."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT MAX(version) FROM migrations")
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0

    def _apply_migration(self, version: int, name: str):
        """Apply a migration."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, datetime.now().isoformat())
            )
            conn.commit()

    def _get_connection(self):
        """Get database connection (for testing)."""
        return sqlite3.connect(self.db_path)

    async def insert_usage_event(
        self,
        user_id: str,
        endpoint: str,
        tokens_used: int,
        timestamp: datetime
    ) -> None:
        """Insert usage event for billing tracking.

        Args:
            user_id: User identifier
            endpoint: API endpoint called
            tokens_used: Number of tokens consumed
            timestamp: Event timestamp
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO usage_events
                (user_id, endpoint, tokens_used, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                user_id,
                endpoint,
                tokens_used,
                timestamp.isoformat()
            ))
            conn.commit()

    def save_service(self, service) -> None:
        """Save a service to the database.

        Args:
            service: Service object to save
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO services
                (service_id, name, repo_id, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                str(service.service_id),
                service.name,
                str(service.repo_id),
                service.description,
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_service_by_repo_id(self, repo_id: str):
        """Get service by repository ID.

        Args:
            repo_id: Repository ID

        Returns:
            Service object or None if not found
        """
        from ..models.service import Service

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT service_id, name, repo_id, description
                FROM services WHERE repo_id = ?
            """, (repo_id,))

            row = cursor.fetchone()
            if row:
                return Service(
                    service_id=row[0],
                    name=row[1],
                    repo_id=row[2],
                    description=row[3]
                )
        return None

    def get_service_by_id(self, service_id: str):
        """Get service by service ID.

        Args:
            service_id: Service ID

        Returns:
            Service object or None if not found
        """
        from ..models.service import Service

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT service_id, name, repo_id, description
                FROM services WHERE service_id = ?
            """, (service_id,))

            row = cursor.fetchone()
            if row:
                return Service(
                    service_id=row[0],
                    name=row[1],
                    repo_id=row[2],
                    description=row[3]
                )
        return None

    def list_services(self):
        """List all services.

        Returns:
            List of Service objects
        """
        from ..models.service import Service

        services = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT service_id, name, repo_id, description
                FROM services ORDER BY name
            """)

            for row in cursor.fetchall():
                services.append(Service(
                    service_id=row[0],
                    name=row[1],
                    repo_id=row[2],
                    description=row[3]
                ))
        return services

    def delete_service(self, service_id: str) -> bool:
        """Delete a service by ID.

        Args:
            service_id: Service ID to delete

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM services WHERE service_id = ?", (service_id,))
            conn.commit()
            return cursor.rowcount > 0