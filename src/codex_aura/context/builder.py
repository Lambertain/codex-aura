import time
from typing import TYPE_CHECKING

from ..models.node import Node, RankedNode
from ..search.vector_store import SemanticSearch
from ..storage.storage_abstraction import GraphStorage
from ..token_budget.allocator import BudgetAllocator
from ..token_budget.counter import TokenCounter
from ..token_budget.presets import get_preset
from ..token_budget.summarizer import ContentSummarizer

if TYPE_CHECKING:
    from .formatter import ContextFormatter
    from ..api.models.context import ContextRequest, ContextResponse, ContextStats


class ContextBuilder:
    """
    Build intelligent code context for AI agents.

    Pipeline:
    1. Resolve entry points
    2. Graph traversal (structural relevance)
    3. Semantic search (content relevance)
    4. Hybrid ranking
    5. Budget allocation
    6. Format output
    """

    def __init__(
        self,
        graph_storage: GraphStorage,
        semantic_search: SemanticSearch,
        budget_allocator: BudgetAllocator,
        token_counter: TokenCounter,
        summarizer: ContentSummarizer
    ):
        self.graph = graph_storage
        self.search = semantic_search
        self.allocator = budget_allocator
        self.counter = token_counter
        self.summarizer = summarizer

    async def build(self, request: "ContextRequest") -> "ContextResponse":
        """Build context for the given request."""
        start_time = time.time()

        # Step 1: Resolve entry points
        entry_nodes = await self._resolve_entry_points(
            request.repo_id,
            request.entry_points
        )

        # Step 2: Get structurally relevant nodes (graph traversal)
        graph_nodes = await self._traverse_graph(
            request.repo_id,
            entry_nodes,
            depth=request.depth
        )

        # Step 3: Get semantically relevant nodes
        semantic_nodes = await self._semantic_search(
            request.repo_id,
            request.task,
            limit=100
        )

        # Step 4: Combine and rank
        ranked_nodes = self._hybrid_rank(
            graph_nodes,
            semantic_nodes,
            task=request.task
        )

        # Step 5: Apply filters
        filtered_nodes = self._apply_filters(
            ranked_nodes,
            include_tests=request.include_tests,
            file_patterns=request.file_patterns
        )

        # Step 6: Allocate budget
        max_tokens = request.max_tokens or get_preset(request.model).recommended_context

        allocation = self.allocator.allocate(
            nodes=filtered_nodes,
            max_tokens=max_tokens,
            strategy=request.budget_strategy,
            model=request.model
        )

        # Step 7: Format output
        formatted_context = await self._format_context(
            allocation.selected_nodes,
            format=request.format,
            include_metadata=request.include_metadata,
            include_docs=request.include_docs
        )

        generation_time = int((time.time() - start_time) * 1000)

        from ..api.models.context import ContextResponse, ContextStats, NodeSummary

        return ContextResponse(
            context=formatted_context,
            nodes=[NodeSummary.from_node(n.node) for n in allocation.selected_nodes],
            stats=ContextStats(
                total_tokens=allocation.total_tokens,
                budget_used_pct=allocation.budget_used_pct,
                nodes_included=allocation.nodes_included,
                nodes_excluded=allocation.nodes_excluded,
                nodes_truncated=allocation.nodes_truncated,
                search_mode="hybrid",
                allocation_strategy=allocation.strategy_used.value,
                generation_time_ms=generation_time
            )
        )

    async def _resolve_entry_points(
        self,
        repo_id: str,
        entry_points: list[str]
    ) -> list[str]:
        """Resolve entry points to node FQNs."""
        resolved = []

        for entry in entry_points:
            # Glob pattern
            if "*" in entry:
                matches = await self.graph.find_nodes_by_glob(repo_id, entry)
                resolved.extend(matches)

            # File path
            elif entry.endswith(".py"):
                nodes = await self.graph.get_nodes_in_file(repo_id, entry)
                resolved.extend(n.fqn for n in nodes)

            # Line reference (file.py:42)
            elif ":" in entry and entry.split(":")[1].isdigit():
                file_path, line = entry.rsplit(":", 1)
                node = await self.graph.get_node_at_line(repo_id, file_path, int(line))
                if node:
                    resolved.append(node.fqn)

            # FQN
            else:
                resolved.append(entry)

        return resolved

    async def _traverse_graph(
        self,
        repo_id: str,
        entry_fqns: list[str],
        depth: int
    ) -> list[RankedNode]:
        """Traverse graph from entry points."""
        all_nodes = {}
        visited = set()

        async def traverse(fqn: str, current_depth: int, score: float):
            if fqn in visited or current_depth > depth:
                return
            visited.add(fqn)

            # Get node
            node = await self.graph.get_node(repo_id, fqn)
            if not node:
                return

            # Add to results
            if fqn not in all_nodes:
                all_nodes[fqn] = RankedNode(
                    node=node,
                    score=score,
                    tokens=0  # Will be computed later
                )
            else:
                # Update score if this path is shorter
                if score > all_nodes[fqn].score:
                    all_nodes[fqn].score = score

            if current_depth < depth:
                # Get dependencies and dependents
                deps = await self.graph.get_dependencies(repo_id, fqn, 1)
                dependents = await self.graph.get_dependents(repo_id, fqn, 1)

                for dep_fqn, _ in deps + dependents:
                    await traverse(dep_fqn, current_depth + 1, score * 0.8)

        for fqn in entry_fqns:
            await traverse(fqn, 0, 1.0)

        return list(all_nodes.values())

    async def _semantic_search(
        self,
        repo_id: str,
        task: str,
        limit: int
    ) -> list[RankedNode]:
        """Get semantically relevant nodes."""
        results = await self.search.search(repo_id, task, limit=limit)

        nodes = []
        for r in results:
            # Create Node from CodeChunk
            node = Node(
                id=r.chunk.id,
                type=r.chunk.type,
                name=r.chunk.name,
                path=r.chunk.file_path,
                content=r.chunk.content,
                lines=[r.chunk.start_line, r.chunk.end_line] if r.chunk.start_line and r.chunk.end_line else None
            )
            nodes.append(RankedNode(
                node=node,
                score=r.score,  # Cosine similarity
                tokens=0
            ))

        return nodes

    def _hybrid_rank(
        self,
        graph_nodes: list[RankedNode],
        semantic_nodes: list[RankedNode],
        task: str,
        graph_weight: float = 0.4,
        semantic_weight: float = 0.6
    ) -> list[RankedNode]:
        """Combine graph and semantic scores."""
        scores = {}
        nodes = {}

        # Add graph scores
        for rn in graph_nodes:
            scores[rn.node.fqn] = {"graph": rn.score, "semantic": 0.0}
            nodes[rn.node.fqn] = rn.node

        # Add semantic scores
        for rn in semantic_nodes:
            if rn.node.fqn in scores:
                scores[rn.node.fqn]["semantic"] = rn.score
            else:
                scores[rn.node.fqn] = {"graph": 0.1, "semantic": rn.score}
                nodes[rn.node.fqn] = rn.node

        # Combine scores
        ranked = []
        for fqn, s in scores.items():
            combined = graph_weight * s["graph"] + semantic_weight * s["semantic"]
            ranked.append(RankedNode(
                node=nodes[fqn],
                score=combined,
                tokens=0
            ))

        return sorted(ranked, key=lambda r: r.score, reverse=True)

    def _apply_filters(
        self,
        nodes: list[RankedNode],
        include_tests: bool,
        file_patterns: list[str]
    ) -> list[RankedNode]:
        """Apply filters to nodes."""
        filtered = []

        for rn in nodes:
            # Test filter
            if not include_tests and self._is_test_file(rn.node.path):
                continue

            # Pattern filter
            if file_patterns and not self._matches_patterns(rn.node.path, file_patterns):
                continue

            filtered.append(rn)

        return filtered

    async def _format_context(
        self,
        nodes: list[RankedNode],
        format: str,
        include_metadata: bool,
        include_docs: bool
    ) -> str:
        """Format nodes into context string."""
        # Import here to avoid circular imports
        from .formatter import ContextFormatter

        formatter = ContextFormatter(
            include_metadata=include_metadata,
            include_docs=include_docs
        )

        if format == "markdown":
            return formatter.to_markdown(nodes)
        elif format == "xml":
            return formatter.to_xml(nodes)
        elif format == "json":
            return formatter.to_json(nodes)
        else:
            return formatter.to_plain(nodes)

    @staticmethod
    def _is_test_file(file_path: str) -> bool:
        """Check if file is a test file."""
        return "test" in file_path.lower() or file_path.endswith("_test.py")

    @staticmethod
    def _matches_patterns(file_path: str, patterns: list[str]) -> bool:
        """Check if file matches any of the patterns."""
        import fnmatch

        for pattern in patterns:
            if pattern.startswith("!"):
                if fnmatch.fnmatch(file_path, pattern[1:]):
                    return False
            else:
                if fnmatch.fnmatch(file_path, pattern):
                    return True
        return not patterns  # If no patterns, include all