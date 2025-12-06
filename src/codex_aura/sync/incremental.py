from dataclasses import dataclass
from pathlib import Path
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from ..models.node import Node
from ..models.edge import Edge, EdgeType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.base import Reference
from ..storage.storage_abstraction import GraphStorage
from ..analyzer.base import BaseAnalyzer
from ..search.vector_store import VectorStore
from ..search.embeddings import EmbeddingService, CodeChunker
from . import ChangeType, FileChange


@dataclass
class Reference:
    target_fqn: str
    edge_type: EdgeType


@dataclass
class IncrementalUpdateResult:
    nodes_added: int
    nodes_updated: int
    nodes_deleted: int
    edges_recalculated: int
    duration_ms: int
    errors: list[str]


class GraphTransaction:
    """Transaction context for graph operations."""

    def __init__(self, storage: GraphStorage, repo_id: str):
        self.storage = storage
        self.repo_id = repo_id
        self.operations = []

    async def upsert_node(self, node: Node) -> None:
        """Upsert a node."""
        # For Neo4j, this would be a MERGE operation
        # For SQLite, this would be an INSERT OR REPLACE
        self.operations.append(("upsert_node", node))

    async def run(self, query: str, **parameters) -> List[Dict[str, Any]]:
        """Run a query."""
        self.operations.append(("run", query, parameters))
        # This is a placeholder - actual implementation would depend on storage backend
        return []

    async def find_node_by_fqn(self, fqn: str) -> Optional[Node]:
        """Find node by fully qualified name."""
        self.operations.append(("find_node", fqn))
        # This is a placeholder - actual implementation would depend on storage backend
        return None

    async def create_edge(self, source_fqn: str, target_fqn: str, edge_type: EdgeType, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Create an edge between nodes."""
        self.operations.append(("create_edge", source_fqn, target_fqn, edge_type, metadata))

    async def delete_edges_for_node(self, fqn: str) -> int:
        """Delete all edges from/to a node."""
        self.operations.append(("delete_edges_for_node", fqn))
        return 0  # Placeholder

    async def delete_outgoing_edges(self, fqn: str) -> int:
        """Delete all outgoing edges from a node."""
        self.operations.append(("delete_outgoing_edges", fqn))
        return 0  # Placeholder

    async def node_exists(self, fqn: str) -> bool:
        """Check if node exists."""
        self.operations.append(("node_exists", fqn))
        return False  # Placeholder

    async def create_external_ref(self, source_fqn: str, ref: "Reference") -> None:
        """Create external reference."""
        self.operations.append(("create_external_ref", source_fqn, ref))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Commit operations
            pass
        else:
            # Rollback operations
            pass


class Neo4jGraphTransaction:
    """Neo4j-specific transaction implementation."""

    def __init__(self, session, repo_id: str):
        self.session = session
        self.repo_id = repo_id

    async def upsert_node(self, node: Node) -> None:
        """Upsert a node in Neo4j."""
        # Determine FQN and label
        if node.type == "file":
            fqn = node.path
            label = "File"
        else:
            fqn = node.id
            label = node.type.capitalize()  # Class or Function

        # Prepare properties
        properties = node.model_dump()
        properties["repo_id"] = self.repo_id

        await self.session.run("""
            MERGE (n:Node {fqn: $fqn})
            SET n += $properties
            SET n:$label
        """, fqn=fqn, properties=properties, label=label)

    async def run(self, query: str, **parameters) -> List[Dict[str, Any]]:
        """Run a Cypher query."""
        result = await self.session.run(query, parameters)
        records = await result.fetch_all()
        return [dict(record) for record in records]

    async def find_node_by_fqn(self, fqn: str) -> Optional[Node]:
        """Find node by fully qualified name."""
        result = await self.session.run(
            "MATCH (n:Node {fqn: $fqn}) RETURN n",
            fqn=fqn
        )
        record = await result.single()
        if record:
            node_data = dict(record["n"])
            return Node(**node_data)
        return None

    async def create_edge(self, source_fqn: str, target_fqn: str, edge_type: EdgeType, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Create an edge between nodes."""
        await self.session.run("""
            MATCH (a:Node {fqn: $source})
            MATCH (b:Node {fqn: $target})
            MERGE (a)-[r:$type]->(b)
        """, source=source_fqn, target=target_fqn, type=edge_type.value)

    async def delete_edges_for_node(self, fqn: str) -> int:
        """Delete all edges from/to a node."""
        result = await self.session.run("""
            MATCH (n:Node {fqn: $fqn})-[r]-()
            DELETE r
            RETURN count(r) as cnt
        """, fqn=fqn)
        record = await result.single()
        return record["cnt"] if record else 0

    async def delete_outgoing_edges(self, fqn: str) -> int:
        """Delete all outgoing edges from a node."""
        result = await self.session.run("""
            MATCH (n:Node {fqn: $fqn})-[r]->()
            DELETE r
            RETURN count(r) as cnt
        """, fqn=fqn)
        record = await result.single()
        return record["cnt"] if record else 0

    async def node_exists(self, fqn: str) -> bool:
        """Check if node exists."""
        result = await self.session.run("""
            MATCH (n:Node {fqn: $fqn})
            RETURN count(n) > 0 as exists
        """, fqn=fqn)
        record = await result.single()
        return record["exists"] if record else False

    async def create_external_ref(self, source_fqn: str, ref: "Reference") -> None:
        """Create external reference."""
        # For now, just create a placeholder node
        await self.session.run("""
            MERGE (n:ExternalRef {fqn: $target})
            SET n.type = 'external'
            WITH n
            MATCH (s:Node {fqn: $source})
            MERGE (s)-[r:$type]->(n)
        """, source=source_fqn, target=ref.target_fqn, type=ref.type.value)


class IncrementalGraphUpdater:
    """Updates graph incrementally based on file changes."""

    def __init__(
        self,
        graph_storage: GraphStorage,
        analyzer: BaseAnalyzer,
        vector_store: VectorStore,
        embedding_service: EmbeddingService
    ):
        self.storage = graph_storage
        self.analyzer = analyzer
        self.vectors = vector_store
        self.embeddings = embedding_service
        self.chunker = CodeChunker()

    async def update(
        self,
        repo_id: str,
        changes: list[FileChange],
        repo_path: Path
    ) -> IncrementalUpdateResult:
        """
        Apply incremental updates to graph based on file changes.

        Strategy:
        1. Delete nodes for removed/modified files
        2. Re-analyze added/modified files
        3. Recalculate edges for affected nodes
        4. Update vector index for changed chunks
        """
        start_time = asyncio.get_event_loop().time()
        result = IncrementalUpdateResult(
            nodes_added=0, nodes_updated=0, nodes_deleted=0,
            edges_recalculated=0, duration_ms=0, errors=[]
        )

        try:
            # Group changes by type for efficient processing
            deleted_files = [c.path for c in changes if c.change_type == ChangeType.DELETED]
            modified_files = [c.path for c in changes if c.change_type == ChangeType.MODIFIED]
            added_files = [c.path for c in changes if c.change_type == ChangeType.ADDED]
            renamed_files = [c for c in changes if c.change_type == ChangeType.RENAMED]

            async with self.storage.transaction(repo_id) as txn:
                # Step 1: Handle deletions
                for file_path in deleted_files:
                    deleted_count = await self._delete_file_nodes(txn, file_path)
                    result.nodes_deleted += deleted_count

                # Step 2: Handle renames (delete old, analyze new)
                for change in renamed_files:
                    await self._delete_file_nodes(txn, change.old_path)
                    added_files.append(change.path)

                # Step 3: Handle modifications (delete old nodes, re-analyze)
                for file_path in modified_files:
                    await self._delete_file_nodes(txn, file_path)

                # Step 4: Analyze new/modified files
                files_to_analyze = added_files + modified_files
                for file_path in files_to_analyze:
                    full_path = repo_path / file_path
                    if not full_path.exists():
                        result.errors.append(f"File not found: {file_path}")
                        continue

                    try:
                        nodes = await self.analyzer.analyze_file(full_path)
                        for node in nodes:
                            await txn.upsert_node(node)
                            result.nodes_added += 1
                    except Exception as e:
                        result.errors.append(f"Analysis failed for {file_path}: {e}")

                # Step 5: Recalculate edges for affected files
                all_affected = set(deleted_files + modified_files + added_files)
                edges_count = await self._recalculate_edges(txn, all_affected)
                result.edges_recalculated = edges_count

                # Step 6: Update vector index
                await self._update_vector_index(
                    repo_id,
                    files_to_analyze,
                    deleted_files,
                    repo_path
                )

        except Exception as e:
            result.errors.append(f"Update failed: {e}")
            raise

        end_time = asyncio.get_event_loop().time()
        result.duration_ms = int((end_time - start_time) * 1000)

        return result

    async def _delete_file_nodes(self, txn, file_path: str) -> int:
        """Delete all nodes belonging to a file."""
        # This would be implemented differently for each storage backend
        # For Neo4j: MATCH (n:Node {file_path: $file_path}) DETACH DELETE n
        # For SQLite: DELETE FROM nodes WHERE file_path = ?
        query = "MATCH (n:Node {file_path: $file_path}) DETACH DELETE n RETURN count(n) as cnt"
        results = await txn.run(query, file_path=file_path)
        return results[0]["cnt"] if results else 0

    async def _recalculate_edges(
        self,
        txn,
        affected_files: set[str]
    ) -> int:
        """
        Recalculate edges for nodes in affected files.

        This is the tricky part:
        - IMPORTS edges: re-resolve import statements
        - CALLS edges: re-analyze function calls
        - EXTENDS edges: re-check inheritance
        """
        edges_created = 0

        # Get all nodes from affected files
        query = """
        MATCH (n:Node)
        WHERE n.file_path IN $files
        RETURN n
        """
        results = await txn.run(query, files=list(affected_files))
        affected_nodes = [record["n"] for record in results]

        for node in affected_nodes:
            # Re-resolve references for this node
            references = await self.analyzer.resolve_references(node)

            for ref in references:
                # Find target node
                target = await txn.find_node_by_fqn(ref.target_fqn)
                if target:
                    await txn.create_edge(
                        source_fqn=node["fqn"],
                        target_fqn=target["fqn"],
                        edge_type=ref.edge_type
                    )
                    edges_created += 1

        return edges_created

    async def _update_vector_index(
        self,
        repo_id: str,
        updated_files: list[str],
        deleted_files: list[str],
        repo_path: Path
    ):
        """Update Qdrant index for changed files."""
        collection = f"repo_{repo_id}"

        # Delete vectors for removed/modified files
        all_removed = set(updated_files + deleted_files)
        if all_removed:
            await self.vectors.delete_by_filter(
                collection,
                {"file_path": {"$in": list(all_removed)}}
            )

        # Re-embed updated files
        for file_path in updated_files:
            full_path = repo_path / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text()
            chunks = self.chunker.chunk_file(content, file_path)

            if chunks:
                embeddings = await self.embeddings.embed_batch(
                    [c.content for c in chunks]
                )
                await self.vectors.upsert_chunks(
                    collection, chunks, embeddings
                )


class BatchIncrementalUpdater(IncrementalGraphUpdater):
    """Optimized updater for large changesets."""

    async def update_batch(
        self,
        repo_id: str,
        changes: list[FileChange],
        repo_path: Path,
        batch_size: int = 50
    ) -> IncrementalUpdateResult:
        """Process changes in batches for memory efficiency."""

        total_result = IncrementalUpdateResult(
            nodes_added=0, nodes_updated=0, nodes_deleted=0,
            edges_recalculated=0, duration_ms=0, errors=[]
        )

        # Process in batches
        for i in range(0, len(changes), batch_size):
            batch = changes[i:i + batch_size]
            batch_result = await self.update(repo_id, batch, repo_path)

            # Aggregate results
            total_result.nodes_added += batch_result.nodes_added
            total_result.nodes_deleted += batch_result.nodes_deleted
            total_result.edges_recalculated += batch_result.edges_recalculated
            total_result.errors.extend(batch_result.errors)

        return total_result