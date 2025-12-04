"""SQLite storage backend for codex-aura."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..models.graph import Graph, load_graph, save_graph


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
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
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
            conn.commit()

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