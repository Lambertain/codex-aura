"""Vector index synchronization for incremental updates."""

from dataclasses import dataclass
from typing import List

from ..models.node import Node
from ..search.vector_store import VectorStore
from ..search.embeddings import EmbeddingService, CodeChunker
from ..storage.storage_abstraction import GraphStorage


@dataclass
class VectorSyncResult:
    """Result of vector index synchronization."""
    vectors_added: int
    vectors_deleted: int
    embedding_tokens: int


class VectorIndexSyncer:
    """Keep vector index in sync with graph changes."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        chunker: CodeChunker
    ):
        self.vectors = vector_store
        self.embeddings = embedding_service
        self.chunker = chunker

    async def sync_changes(
        self,
        repo_id: str,
        updated_nodes: list[Node],
        deleted_nodes: list[Node]
    ) -> VectorSyncResult:
        """
        Sync vector index with graph changes.

        Strategy:
        1. Delete vectors for deleted nodes
        2. Delete old vectors for updated nodes
        3. Re-chunk and re-embed updated nodes
        4. Upsert new vectors
        """
        collection = f"repo_{repo_id}"
        result = VectorSyncResult(
            vectors_added=0,
            vectors_deleted=0,
            embedding_tokens=0
        )

        # Step 1: Delete vectors for deleted nodes
        deleted_fqns = [n.fqn for n in deleted_nodes]
        if deleted_fqns:
            deleted_count = await self.vectors.delete_by_fqns(
                collection, deleted_fqns
            )
            result.vectors_deleted += deleted_count

        # Step 2: Delete old vectors for updated nodes
        updated_fqns = [n.fqn for n in updated_nodes]
        if updated_fqns:
            deleted_count = await self.vectors.delete_by_fqns(
                collection, updated_fqns
            )
            result.vectors_deleted += deleted_count

        # Step 3: Chunk and embed updated nodes
        if updated_nodes:
            all_chunks = []
            for node in updated_nodes:
                chunks = self.chunker.chunk_node(node)
                all_chunks.extend(chunks)

            if all_chunks:
                # Batch embed for efficiency
                texts = [c.content for c in all_chunks]
                embeddings = await self.embeddings.embed_batch(texts)

                # Track token usage
                result.embedding_tokens = sum(
                    len(self.embeddings.tokenizer.encode(t))
                    for t in texts
                )

                # Upsert to vector store
                await self.vectors.upsert_chunks(
                    collection, all_chunks, embeddings
                )
                result.vectors_added = len(all_chunks)

        return result

    async def full_reindex(
        self,
        repo_id: str,
        graph: GraphStorage,
        batch_size: int = 100
    ) -> VectorSyncResult:
        """Full reindex of all nodes (for recovery/migration)."""
        collection = f"repo_{repo_id}"

        # Clear existing
        await self.vectors.delete_collection(collection)
        await self.vectors.create_collection(collection)

        result = VectorSyncResult(
            vectors_added=0,
            vectors_deleted=0,
            embedding_tokens=0
        )

        # Process in batches
        all_nodes = await graph.get_all_nodes()

        for i in range(0, len(all_nodes), batch_size):
            batch = all_nodes[i:i + batch_size]
            batch_result = await self.sync_changes(repo_id, batch, [])
            result.vectors_added += batch_result.vectors_added
            result.embedding_tokens += batch_result.embedding_tokens

        return result