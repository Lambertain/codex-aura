#!/usr/bin/env python3
"""
Migration script to move graphs from SQLite to Neo4j.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codex_aura.storage.sqlite import SQLiteStorage
from codex_aura.storage.neo4j_client import Neo4jClient


async def main():
    """Main migration function."""
    if len(sys.argv) != 2:
        print("Usage: python migrate_to_neo4j.py <graph_id>")
        sys.exit(1)

    graph_id = sys.argv[1]

    # Initialize storages
    sqlite_storage = SQLiteStorage()
    neo4j_client = Neo4jClient()

    try:
        # Load graph from SQLite
        print(f"Loading graph {graph_id} from SQLite...")
        sqlite_graph = sqlite_storage.load_graph(graph_id)
        if not sqlite_graph:
            print(f"Graph {graph_id} not found in SQLite")
            sys.exit(1)

        print(f"Found graph with {len(sqlite_graph.nodes)} nodes and {len(sqlite_graph.edges)} edges")

        # Apply schema if needed
        schema_path = Path(__file__).parent / "schema.cypher"
        if schema_path.exists():
            print("Applying schema...")
            await neo4j_client.apply_schema(str(schema_path))
            print("Schema applied successfully")

        # Migrate graph
        print("Migrating graph to Neo4j...")
        neo4j_graph_id = await neo4j_client.migrate_graph_to_neo4j(sqlite_graph)
        print(f"Migration completed. Neo4j graph ID: {neo4j_graph_id}")

    finally:
        await neo4j_client.close()


if __name__ == "__main__":
    asyncio.run(main())