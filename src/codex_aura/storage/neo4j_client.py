"""
Neo4j client for Codex Aura storage layer.
Provides async interface to Neo4j graph database.
"""

import os
from typing import Optional, Any, Dict, List
from contextlib import asynccontextmanager
from functools import lru_cache

from neo4j import AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import ServiceUnavailable

from ..models.graph import Graph
from ..models.node import Node
from ..sync.incremental import GraphTransaction


class Neo4jClient:
    """
    Async Neo4j client with connection pooling and session management.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize Neo4j client.

        Args:
            uri: Neo4j connection URI (default: from env NEO4J_URI)
            user: Neo4j username (default: from env NEO4J_USER)
            password: Neo4j password (default: from env NEO4J_PASSWORD)
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")

        self._driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password)
        )

    async def close(self) -> None:
        """Close the driver and cleanup connections."""
        await self._driver.close()

    @asynccontextmanager
    async def session(self):
        """
        Context manager for Neo4j sessions.

        Usage:
            async with client.session() as session:
                result = await session.run("MATCH (n) RETURN n")
        """
        async with self._driver.session() as session:
            yield session

    async def health_check(self) -> bool:
        """
        Check if Neo4j is accessible and responding.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with self.session() as session:
                result = await session.run("RETURN 1")
                record = await result.single()
                return record is not None and record[0] == 1
        except ServiceUnavailable:
            return False

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.fetch_all()
            return [dict(record) for record in records]

    async def execute_write_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a write Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        async with self.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.fetch_all()
            return [dict(record) for record in records]

    async def create_node(
        self,
        labels: List[str],
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new node with labels and properties.

        Args:
            labels: List of node labels
            properties: Node properties

        Returns:
            Created node data
        """
        labels_str = ":".join(labels)
        query = f"CREATE (n:{labels_str} $props) RETURN n"
        result = await self.execute_write_query(query, {"props": properties})
        return result[0] if result else {}

    async def get_node_by_id(self, node_id: int) -> Optional[Dict[str, Any]]:
        """
        Get node by internal ID.

        Args:
            node_id: Neo4j internal node ID

        Returns:
            Node data or None if not found
        """
        query = "MATCH (n) WHERE id(n) = $id RETURN n"
        result = await self.execute_query(query, {"id": node_id})
        return result[0] if result else None

    async def create_relationship(
        self,
        start_node_id: int,
        end_node_id: int,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a relationship between two nodes.

        Args:
            start_node_id: Start node internal ID
            end_node_id: End node internal ID
            relationship_type: Relationship type
            properties: Relationship properties

        Returns:
            Created relationship data
        """
        query = f"""
        MATCH (a), (b)
        WHERE id(a) = $start_id AND id(b) = $end_id
        CREATE (a)-[r:{relationship_type} $props]->(b)
        RETURN r
        """
        result = await self.execute_write_query(
            query,
            {
                "start_id": start_node_id,
                "end_id": end_node_id,
                "props": properties or {}
            }
        )
        return result[0] if result else {}

    async def migrate_graph_to_neo4j(self, sqlite_graph: Graph) -> str:
        """
        Migrate graph from SQLite to Neo4j.

        Args:
            sqlite_graph: The Graph object from SQLite storage

        Returns:
            Neo4j graph ID
        """
        # Generate graph ID
        neo4j_graph_id = f"{sqlite_graph.repository.name}_{sqlite_graph.sha or 'latest'}"

        batch_size = 1000

        async with self.session() as session:
            # Create nodes in batches
            for i in range(0, len(sqlite_graph.nodes), batch_size):
                batch_nodes = sqlite_graph.nodes[i:i + batch_size]

                for node in batch_nodes:
                    # Determine FQN and label
                    if node.type == "file":
                        fqn = node.path
                        label = "File"
                    else:
                        fqn = node.id
                        label = node.type.capitalize()  # Class or Function

                    # Prepare properties
                    properties = node.model_dump()
                    properties["repo_id"] = sqlite_graph.repository.name

                    await session.run("""
                        MERGE (n:Node {fqn: $fqn})
                        SET n += $properties
                        SET n:$label
                    """, fqn=fqn, properties=properties, label=label)

            # Create edges in batches
            for i in range(0, len(sqlite_graph.edges), batch_size):
                batch_edges = sqlite_graph.edges[i:i + batch_size]

                for edge in batch_edges:
                    # Get FQN for source and target nodes
                    source_node = next((n for n in sqlite_graph.nodes if n.id == edge.source), None)
                    target_node = next((n for n in sqlite_graph.nodes if n.id == edge.target), None)

                    if not source_node or not target_node:
                        continue  # Skip invalid edges

                    source_fqn = source_node.path if source_node.type == "file" else source_node.id
                    target_fqn = target_node.path if target_node.type == "file" else target_node.id

                    properties = edge.model_dump()

                    await session.run("""
                        MATCH (a:Node {fqn: $source})
                        MATCH (b:Node {fqn: $target})
                        MERGE (a)-[r:$type]->(b)
                        SET r += $properties
                    """, source=source_fqn, target=target_fqn,
                        type=edge.type.value, properties=properties)

        return neo4j_graph_id

    async def apply_schema(self, schema_path: str) -> None:
        """
        Apply Cypher schema to Neo4j database.

        Args:
            schema_path: Path to the schema.cypher file
        """
        with open(schema_path, 'r') as f:
            schema_content = f.read()

        # Split schema into individual statements
        statements = [stmt.strip() for stmt in schema_content.split(';') if stmt.strip()]

        async with self.session() as session:
            for statement in statements:
                if statement:
                    await session.run(statement)


class GraphQueries:
    """
    Query layer for graph operations in Neo4j.

    Provides methods to query dependencies, dependents, and shortest paths
    with built-in caching for performance.
    """

    def __init__(self, client: Neo4jClient):
        """
        Initialize GraphQueries with a Neo4j client.

        Args:
            client: Neo4jClient instance for database operations
        """
        self.client = client
        self._cache = {}

    async def get_dependencies(self, fqn: str, depth: int = 2) -> List[Node]:
        """
        Get all dependencies up to N levels deep.

        Args:
            fqn: Fully qualified name of the starting node
            depth: Maximum depth to traverse

        Returns:
            List of dependent Node objects ordered by distance
        """
        cache_key = f"deps_{fqn}_{depth}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        query = """
        MATCH path = (start:Node {fqn: $fqn})-[:IMPORTS|CALLS|EXTENDS*1..$depth]->(dep:Node)
        RETURN DISTINCT dep, length(path) as distance
        ORDER BY distance
        """
        result = await self.client.execute_query(query, {"fqn": fqn, "depth": depth})

        nodes = []
        for record in result:
            node_data = dict(record["dep"])
            # Convert back to Node object
            node = Node(**node_data)
            nodes.append(node)

        self._cache[cache_key] = nodes
        return nodes

    async def get_dependents(self, fqn: str, depth: int = 2) -> List[Node]:
        """
        Get all nodes that depend on this node.

        Args:
            fqn: Fully qualified name of the target node
            depth: Maximum depth to traverse

        Returns:
            List of dependent Node objects ordered by distance
        """
        cache_key = f"dependents_{fqn}_{depth}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        query = """
        MATCH path = (dependent:Node)-[:IMPORTS|CALLS|EXTENDS*1..$depth]->(target:Node {fqn: $fqn})
        RETURN DISTINCT dependent, length(path) as distance
        ORDER BY distance
        """
        result = await self.client.execute_query(query, {"fqn": fqn, "depth": depth})

        nodes = []
        for record in result:
            node_data = dict(record["dependent"])
            node = Node(**node_data)
            nodes.append(node)

        self._cache[cache_key] = nodes
        return nodes

    async def shortest_path(self, source: str, target: str) -> List[Node]:
        """
        Find shortest path between two nodes.

        Args:
            source: FQN of source node
            target: FQN of target node

        Returns:
            List of Node objects representing the path
        """
        cache_key = f"path_{source}_{target}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        query = """
        MATCH path = shortestPath(
            (a:Node {fqn: $source})-[*]-(b:Node {fqn: $target})
        )
        RETURN path
        """
        result = await self.client.execute_query(query, {"source": source, "target": target})

        if not result:
            nodes = []
        else:
            path = result[0]["path"]
            nodes = []
            for node in path.nodes:
                node_data = dict(node)
                node_obj = Node(**node_data)
                nodes.append(node_obj)

        self._cache[cache_key] = nodes
        return nodes

    def clear_cache(self):
        """Clear the query cache."""
        self._cache.clear()

    async def save_dependency_graph(self, graph: Graph) -> str:
        """
        Save dependency graph with service relationships to Neo4j.

        Args:
            graph: Graph containing service nodes and SERVICE_CALLS edges.

        Returns:
            Graph ID in Neo4j.
        """
        graph_id = f"dependency_graph_{graph.sha or 'latest'}"

        async with self.session() as session:
            # Create service nodes
            for node in graph.nodes:
                if node.type == "service":
                    await session.run("""
                        MERGE (s:Service {name: $name})
                        SET s.path = $path,
                            s.repo_id = $repo_id,
                            s.graph_id = $graph_id
                    """, name=node.name, path=node.path, repo_id=node.name, graph_id=graph_id)

            # Create dependency relationships
            for edge in graph.edges:
                if edge.type == "SERVICE_CALLS":
                    source_name = edge.source.replace("service_", "")
                    target_name = edge.target.replace("service_", "")

                    await session.run("""
                        MATCH (source:Service {name: $source_name}),
                              (target:Service {name: $target_name})
                        MERGE (source)-[r:SERVICE_CALLS]->(target)
                        SET r.line = $line,
                            r.graph_id = $graph_id
                    """, source_name=source_name, target_name=target_name,
                         line=edge.line, graph_id=graph_id)

        return graph_id