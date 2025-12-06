from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List
from .embeddings import CodeChunk, SearchResult, RankedNode, EmbeddingService
from ..storage.storage_abstraction import get_storage


class VectorStore:
    def __init__(self, url: str = "http://localhost:6333"):
        self.client = QdrantClient(url=url)

    async def create_collection(self, repo_id: str):
        """Create collection for a repository."""
        self.client.create_collection(
            collection_name=f"repo_{repo_id}",
            vectors_config=VectorParams(
                size=1536,  # text-embedding-3-small
                distance=Distance.COSINE
            )
        )

    async def upsert_chunks(
        self,
        repo_id: str,
        chunks: list[CodeChunk],
        embeddings: list[list[float]]
    ):
        """Insert or update code chunks."""
        points = [
            PointStruct(
                id=chunk.id,
                vector=embedding,
                payload={
                    "content": chunk.content,
                    "type": chunk.type,
                    "file_path": chunk.file_path,
                    "name": chunk.name,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line
                }
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self.client.upsert(collection_name=f"repo_{repo_id}", points=points)


class SemanticSearch:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.embeddings = embedding_service
        self.vectors = vector_store

    async def search(
        self,
        repo_id: str,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> list[SearchResult]:
        """Search for relevant code chunks."""
        query_embedding = await self.embeddings.embed_code(query)

        results = self.vectors.client.search(
            collection_name=f"repo_{repo_id}",
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )

        return [
            SearchResult(
                chunk=CodeChunk(**hit.payload),
                score=hit.score
            )
            for hit in results
        ]


class HybridSearch:
    """Combine graph structure with semantic similarity."""

    def __init__(self, semantic_search: SemanticSearch, storage=None):
        self.semantic = semantic_search
        self.graph = storage or get_storage()

    async def search(
        self,
        repo_id: str,
        task: str,
        entry_points: list[str],
        depth: int = 2
    ) -> list[RankedNode]:
        # 1. Get structurally relevant nodes from graph
        graph_nodes = []
        for entry_point in entry_points:
            nodes = await self.graph.query_dependencies(entry_point, depth)
            graph_nodes.extend(nodes)

        # Remove duplicates while preserving order
        seen = set()
        unique_graph_nodes = []
        for node in graph_nodes:
            fqn = node.path if node.type == "file" else node.id
            if fqn not in seen:
                seen.add(fqn)
                unique_graph_nodes.append(node)

        # 2. Get semantically relevant chunks
        semantic_results = await self.semantic.search(
            repo_id, task, limit=50
        )

        # 3. Combine scores
        node_scores = {}
        for node in unique_graph_nodes:
            fqn = node.path if node.type == "file" else node.id
            node_scores[fqn] = {
                "graph_score": 1.0,  # all graph nodes get full graph score
                "semantic_score": 0.0
            }

        for result in semantic_results:
            fqn = result.chunk.file_path if result.chunk.type == "file" else f"{result.chunk.file_path}::{result.chunk.name}"
            if fqn in node_scores:
                node_scores[fqn]["semantic_score"] = result.score
            else:
                node_scores[fqn] = {
                    "graph_score": 0.1,  # not in graph, low base
                    "semantic_score": result.score
                }

        # 4. Final ranking
        ranked = []
        for fqn, scores in node_scores.items():
            combined = (
                0.4 * scores["graph_score"] +
                0.6 * scores["semantic_score"]
            )
            ranked.append(RankedNode(fqn=fqn, score=combined))

        return sorted(ranked, key=lambda x: x.score, reverse=True)