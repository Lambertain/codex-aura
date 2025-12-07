"""
Unified Context Pipeline for Codex Aura.

Combines semantic search, graph expansion, ranking, budget allocation,
summarization, and final formatting into a single black-box pipeline.
"""

import time
import logging
from typing import List, Optional, Dict, Any
from dataclasses import field
from dataclasses import dataclass

from ..models.node import Node, RankedNode
from ..models.usage import UsageEvent
from ..search.vector_store import SemanticSearch, SearchResult
from ..search.embeddings import EmbeddingService
from ..storage.storage_abstraction import get_storage
from ..storage.usage_storage import UsageStorage
from ..context.ranking import SemanticRankingEngine, RankedContextNode
from ..token_budget.allocator import BudgetAllocator
from ..token_budget.counter import TokenCounter
from ..token_budget.summarizer import ContentSummarizer
from ..context.formatters import ContextFormatter
from ..api.models.context import ContextResponse, ContextStats, NodeSummary

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the context pipeline."""

    # Semantic search
    semantic_limit: int = 50
    semantic_threshold: float = 0.7

    # Graph expansion
    graph_depth: int = 2  # Legacy depth-based expansion
    graph_weight_threshold: float = 0.1  # Stop expansion when cumulative weight < threshold
    edge_weights: Dict[str, float] = field(default_factory=lambda: {
        "CALLS": 0.9,
        "IMPORTS": 0.6,
        "EXTENDS": 1.0
    })  # Edge type weights for weighted expansion

    # Ranking weights
    semantic_weight: float = 0.4
    graph_weight: float = 0.3
    criticality_weight: float = 0.15
    frequency_weight: float = 0.1
    token_efficiency_weight: float = 0.05

    # Budget allocation
    default_budget_strategy: str = "adaptive"

    # Summarization
    enable_summarization: bool = True
    max_summary_tokens: int = 1000

    # Output
    default_format: str = "markdown"
    include_metadata: bool = True
    include_docs: bool = True


class UnifiedContextPipeline:
    """
    Unified pipeline for generating intelligent code context.

    Pipeline stages:
    1. Semantic search - Find semantically relevant code chunks
    2. Graph expansion - Expand from entry points using dependency graph
    3. Ranking - Rank nodes by multiple criteria (semantic, graph, criticality)
    4. Budget allocation - Select optimal subset within token limits
    5. Summarization - Summarize oversized nodes if needed
    6. Final formatting - Format into requested output format
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        graph_storage=None,
        token_counter: Optional[TokenCounter] = None,
        config: Optional[PipelineConfig] = None
    ):
        """
        Initialize the unified context pipeline.

        Args:
            embedding_service: Service for generating embeddings
            graph_storage: Storage interface for graph operations
            token_counter: Token counter for budget management
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self.embeddings = embedding_service
        self.graph = graph_storage or get_storage()
        self.token_counter = token_counter or TokenCounter()

        # Initialize search and ranking
        vector_store = None  # Will be initialized per repo
        self.semantic_search = SemanticSearch(embedding_service, vector_store)
        self.ranking_engine = SemanticRankingEngine(self.token_counter)

        # Initialize budget and summarization
        self.budget_allocator = BudgetAllocator(self.token_counter)
        self.summarizer = ContentSummarizer(self.token_counter)

        # Initialize formatter
        self.formatter = ContextFormatter(
            include_metadata=self.config.include_metadata,
            include_docs=self.config.include_docs
        )

        logger.info("Unified Context Pipeline initialized")

    async def run(
        self,
        repo_id: str,
        task: str,
        max_tokens: int,
        model: str = "gpt-4",
        entry_points: Optional[List[str]] = None,
        format: str = "markdown"
    ) -> ContextResponse:
        """
        Run the unified context pipeline.

        Args:
            repo_id: Repository identifier
            task: Task description for semantic relevance
            max_tokens: Maximum token budget
            model: Target LLM model
            entry_points: Optional entry points for graph expansion
            format: Output format

        Returns:
            ContextResult with formatted context and statistics
        """
        start_time = time.time()
        logger.info(f"Starting context pipeline for repo {repo_id}, task: {task[:50]}...")

        try:
            # Stage 1: Semantic search
            logger.info("Stage 1: Performing semantic search")
            semantic_results = await self._semantic_search(repo_id, task)
            logger.info(f"Found {len(semantic_results)} semantically relevant chunks")

            # Stage 2: Graph expansion
            logger.info("Stage 2: Expanding graph from entry points")
            graph_nodes = await self._graph_expansion(repo_id, entry_points or [])
            logger.info(f"Expanded to {len(graph_nodes)} graph nodes")

            # Stage 3: Ranking
            logger.info("Stage 3: Ranking nodes by relevance")
            ranked_nodes = self._ranking(task, semantic_results, graph_nodes, model)
            logger.info(f"Ranked {len(ranked_nodes)} nodes")

            # Stage 4: Budget allocation
            logger.info("Stage 4: Allocating token budget")
            selected_nodes, allocation_stats = self._budget_allocation(
                ranked_nodes, max_tokens, model
            )
            logger.info(f"Selected {len(selected_nodes)} nodes within {allocation_stats.total_tokens} tokens")

            # Stage 5: Summarization (if needed)
            if self.config.enable_summarization:
                logger.info("Stage 5: Summarizing oversized content")
                summarized_nodes = await self._summarization(selected_nodes, model)
                logger.info(f"Summarized {len(summarized_nodes)} nodes")
            else:
                summarized_nodes = selected_nodes

            # Stage 6: Final formatting
            logger.info("Stage 6: Formatting final output")
            formatted_context = self._final_formatting(summarized_nodes, format)
            logger.info(f"Generated {len(formatted_context)} characters of context")

            # Calculate final statistics
            generation_time = int((time.time() - start_time) * 1000)

            stats = ContextStats(
                total_tokens=allocation_stats.total_tokens,
                budget_used_pct=allocation_stats.budget_used_pct,
                nodes_included=len(summarized_nodes),
                nodes_excluded=len(ranked_nodes) - len(summarized_nodes),
                nodes_truncated=allocation_stats.nodes_truncated,
                search_mode="hybrid",
                allocation_strategy=allocation_stats.strategy_used.value,
                generation_time_ms=generation_time
            )

            # Create node summaries
            node_summaries = [NodeSummary.from_node(node) for node in summarized_nodes]

            logger.info(f"Pipeline completed in {generation_time}ms")

            # Log usage event (async, don't wait)
            try:
                usage_storage = UsageStorage()
                await usage_storage.insert_usage_event(UsageEvent(
                    user_id="system",  # TODO: get from context when available
                    event_type="context_request",
                    endpoint="context_pipeline",
                    tokens_used=allocation_stats.total_tokens,
                    metadata={
                        "repo_id": repo_id,
                        "task_length": len(task),
                        "nodes_selected": len(summarized_nodes),
                        "generation_time_ms": generation_time
                    }
                ))
            except Exception as e:
                logger.warning(f"Failed to log usage: {e}")

            return ContextResponse(
                context=formatted_context,
                nodes=node_summaries,
                stats=stats
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise

    async def _semantic_search(self, repo_id: str, task: str) -> List[SearchResult]:
        """Stage 1: Perform semantic search for relevant code chunks."""
        # Initialize vector store for this repo
        from ..search.vector_store import VectorStore
        vector_store = VectorStore()
        self.semantic_search.vectors = vector_store

        results = await self.semantic_search.search(
            repo_id=repo_id,
            query=task,
            limit=self.config.semantic_limit,
            score_threshold=self.config.semantic_threshold
        )

        # Log semantic search usage
        try:
            usage_storage = UsageStorage()
            await usage_storage.insert_usage_event(UsageEvent(
                user_id="system",  # TODO: get from context
                event_type="semantic_search",
                endpoint="semantic_search",
                tokens_used=None,  # Semantic search doesn't consume user tokens directly
                metadata={
                    "repo_id": repo_id,
                    "query_length": len(task),
                    "results_count": len(results),
                    "avg_score": sum(r.score for r in results) / len(results) if results else 0
                }
            ))
        except Exception as e:
            logger.warning(f"Failed to log semantic search usage: {e}")

        return results

    async def _graph_expansion(self, repo_id: str, entry_points: List[str]) -> List[Node]:
        """Stage 2: Expand from entry points using dependency graph with weighted expansion."""
        if not entry_points:
            # If no entry points, get some default nodes (e.g., main files)
            entry_points = await self._get_default_entry_points(repo_id)

        all_nodes = set()

        for entry_point in entry_points:
            # Resolve entry point to FQN
            resolved_fqns = await self._resolve_entry_point(repo_id, entry_point)

            for fqn in resolved_fqns:
                # Get dependencies using weighted expansion
                deps = await self.graph.get_dependencies_weighted(
                    repo_id,
                    fqn,
                    self.config.edge_weights,
                    self.config.graph_weight_threshold
                )
                for node in deps:
                    all_nodes.add(node)

                # Get the entry node itself
                entry_node = await self.graph.get_node(repo_id, fqn)
                if entry_node:
                    all_nodes.add(entry_node)

        return list(all_nodes)

    def _ranking(
        self,
        task: str,
        semantic_results: List[SearchResult],
        graph_nodes: List[Node],
        model: str
    ) -> List[RankedContextNode]:
        """Stage 3: Rank nodes using multiple criteria."""
        # Use ranking engine
        ranked = self.ranking_engine.rank_context(
            query=task,
            sem_results=semantic_results,
            graph_results=graph_nodes,
            focal_nodes=[],  # Could be derived from entry points
            model=model
        )

        return ranked

    def _budget_allocation(
        self,
        ranked_nodes: List[RankedContextNode],
        max_tokens: int,
        model: str
    ) -> tuple[List[Node], Any]:
        """Stage 4: Allocate token budget optimally."""
        # Convert to RankedNode format expected by allocator
        ranked_for_allocator = [
            RankedNode(node=rn.node, score=rn.combined_score, tokens=rn.tokens)
            for rn in ranked_nodes
        ]

        allocation = self.budget_allocator.allocate(
            nodes=ranked_for_allocator,
            max_tokens=max_tokens,
            strategy=self.config.default_budget_strategy,
            model=model
        )

        return allocation.selected_nodes, allocation

    async def _summarization(self, nodes: List[Node], model: str) -> List[Node]:
        """Stage 5: Summarize oversized nodes."""
        summarized = []

        for node in nodes:
            token_count = self.token_counter.count_node(node, model)

            if token_count > self.config.max_summary_tokens:
                # Summarize the node
                summarized_content = await self.summarizer.summarize_node(
                    node=node,
                    max_tokens=self.config.max_summary_tokens,
                    model=model
                )
                # Create a new node with summarized content
                summarized_node = Node(
                    id=f"{node.id}_summarized",
                    type=node.type,
                    name=node.name,
                    path=node.path,
                    content=summarized_content,
                    lines=node.lines,
                    docstring=node.docstring
                )
                summarized.append(summarized_node)
            else:
                summarized.append(node)

        return summarized

    def _final_formatting(self, nodes: List[Node], format: str) -> str:
        """Stage 6: Format nodes into final output."""
        # Convert to RankedNode format for formatter
        ranked_for_formatter = [
            RankedNode(node=node, score=1.0, tokens=0) for node in nodes
        ]

        if format == "markdown":
            return self.formatter.to_markdown(ranked_for_formatter)
        elif format == "xml":
            return self.formatter.to_xml(ranked_for_formatter)
        elif format == "json":
            return self.formatter.to_json(ranked_for_formatter)
        else:
            return self.formatter.to_plain(ranked_for_formatter)

    async def _get_default_entry_points(self, repo_id: str) -> List[str]:
        """Get default entry points if none provided."""
        # Simple heuristic: look for common entry files
        candidates = ["main.py", "app.py", "__init__.py", "index.py"]

        entry_points = []
        for candidate in candidates:
            try:
                nodes = await self.graph.get_nodes_in_file(repo_id, candidate)
                if nodes:
                    entry_points.extend([n.fqn for n in nodes])
            except:
                continue

        return entry_points[:5]  # Limit to 5

    async def _resolve_entry_point(self, repo_id: str, entry_point: str) -> List[str]:
        """Resolve an entry point string to FQNs."""
        # Handle different entry point formats
        if "*" in entry_point:
            # Glob pattern
            matches = await self.graph.find_nodes_by_glob(repo_id, entry_point)
            return [n.fqn for n in matches]

        elif entry_point.endswith(".py"):
            # File path
            nodes = await self.graph.get_nodes_in_file(repo_id, entry_point)
            return [n.fqn for n in nodes]

        elif ":" in entry_point and entry_point.split(":")[1].isdigit():
            # File:line reference
            file_path, line = entry_point.rsplit(":", 1)
            node = await self.graph.get_node_at_line(repo_id, file_path, int(line))
            return [node.fqn] if node else []

        else:
            # Assume it's already an FQN
            return [entry_point]


# Convenience function for API usage
async def run_context_pipeline(
    repo_id: str,
    task: str,
    max_tokens: int,
    model: str = "gpt-4",
    entry_points: Optional[List[str]] = None,
    format: str = "markdown"
) -> ContextResponse:
    """
    Convenience function to run the unified context pipeline.

    Args:
        repo_id: Repository identifier
        task: Task description
        max_tokens: Maximum token budget
        model: Target LLM model
        entry_points: Optional entry points
        format: Output format

    Returns:
        Context response
    """
    from ..search.embeddings import EmbeddingService

    embedding_service = EmbeddingService()
    pipeline = UnifiedContextPipeline(embedding_service)

    return await pipeline.run(
        repo_id=repo_id,
        task=task,
        max_tokens=max_tokens,
        model=model,
        entry_points=entry_points,
        format=format
    )