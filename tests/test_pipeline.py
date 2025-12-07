"""Tests for Unified Context Pipeline."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from codex_aura.context.pipeline import UnifiedContextPipeline, PipelineConfig
from codex_aura.models.node import Node
from codex_aura.search.embeddings import SearchResult, CodeChunk
from codex_aura.api.models.context import ContextResponse, ContextStats


class TestUnifiedContextPipeline:
    """Test the UnifiedContextPipeline class."""

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service."""
        service = MagicMock()
        service.embed_code = AsyncMock(return_value=[0.1, 0.2, 0.3])
        return service

    @pytest.fixture
    def mock_graph_storage(self):
        """Mock graph storage."""
        storage = MagicMock()
        storage.get_dependencies = AsyncMock(return_value=[("func_a", 1), ("func_b", 2)])
        storage.get_node = AsyncMock(return_value=Node(
            id="func_a",
            type="function",
            name="func_a",
            path="test.py",
            content="def func_a(): pass"
        ))
        storage.get_nodes_in_file = AsyncMock(return_value=[
            Node(id="func_a", type="function", name="func_a", path="test.py", content="def func_a(): pass")
        ])
        storage.find_nodes_by_glob = AsyncMock(return_value=[
            Node(id="func_a", type="function", name="func_a", path="test.py", content="def func_a(): pass")
        ])
        storage.get_node_at_line = AsyncMock(return_value=Node(
            id="func_a", type="function", name="func_a", path="test.py", content="def func_a(): pass"
        ))
        return storage

    @pytest.fixture
    def mock_token_counter(self):
        """Mock token counter."""
        counter = MagicMock()
        counter.count_node = MagicMock(return_value=100)
        return counter

    @pytest.fixture
    def pipeline(self, mock_embedding_service, mock_graph_storage, mock_token_counter):
        """Create pipeline with mocked dependencies."""
        return UnifiedContextPipeline(
            embedding_service=mock_embedding_service,
            graph_storage=mock_graph_storage,
            token_counter=mock_token_counter
        )

    @pytest.fixture
    def sample_search_results(self):
        """Sample search results."""
        return [
            SearchResult(
                chunk=CodeChunk(
                    id="chunk1",
                    content="def func_a(): pass",
                    type="function",
                    file_path="test.py",
                    name="func_a",
                    start_line=1,
                    end_line=1
                ),
                score=0.9
            )
        ]

    @pytest.fixture
    def sample_nodes(self):
        """Sample nodes."""
        return [
            Node(
                id="func_a",
                type="function",
                name="func_a",
                path="test.py",
                content="def func_a(): pass"
            )
        ]

    @pytest.mark.asyncio
    async def test_pipeline_run_basic(self, pipeline, sample_search_results, sample_nodes):
        """Test basic pipeline run."""
        # Mock the internal methods
        pipeline._semantic_search = AsyncMock(return_value=sample_search_results)
        pipeline._graph_expansion = AsyncMock(return_value=sample_nodes)
        pipeline._ranking = MagicMock(return_value=[])
        pipeline._budget_allocation = MagicMock(return_value=(sample_nodes, MagicMock(
            total_tokens=100,
            budget_used_pct=50.0,
            nodes_truncated=0,
            strategy_used=MagicMock(value="adaptive")
        )))
        pipeline._summarization = AsyncMock(return_value=sample_nodes)
        pipeline._final_formatting = MagicMock(return_value="formatted context")

        result = await pipeline.run(
            repo_id="test_repo",
            task="implement login",
            max_tokens=1000,
            model="gpt-4"
        )

        assert isinstance(result, ContextResponse)
        assert result.context == "formatted context"
        assert len(result.nodes) == 1
        assert isinstance(result.stats, ContextStats)
        assert result.stats.total_tokens == 100
        assert result.stats.budget_used_pct == 50.0

    @pytest.mark.asyncio
    async def test_pipeline_run_with_entry_points(self, pipeline, sample_search_results, sample_nodes):
        """Test pipeline run with entry points."""
        pipeline._semantic_search = AsyncMock(return_value=sample_search_results)
        pipeline._graph_expansion = AsyncMock(return_value=sample_nodes)
        pipeline._ranking = MagicMock(return_value=[])
        pipeline._budget_allocation = MagicMock(return_value=(sample_nodes, MagicMock(
            total_tokens=100,
            budget_used_pct=50.0,
            nodes_truncated=0,
            strategy_used=MagicMock(value="adaptive")
        )))
        pipeline._summarization = AsyncMock(return_value=sample_nodes)
        pipeline._final_formatting = MagicMock(return_value="formatted context")

        result = await pipeline.run(
            repo_id="test_repo",
            task="implement login",
            max_tokens=1000,
            model="gpt-4",
            entry_points=["main.py"]
        )

        pipeline._graph_expansion.assert_called_once_with("test_repo", ["main.py"])

    @pytest.mark.asyncio
    async def test_semantic_search_stage(self, pipeline):
        """Test semantic search stage."""
        with patch('codex_aura.search.vector_store.VectorStore') as mock_vector_store_class:
            mock_vector_store = MagicMock()
            mock_vector_store_class.return_value = mock_vector_store

            pipeline.semantic_search.search = AsyncMock(return_value=[])

            results = await pipeline._semantic_search("test_repo", "test task")

            mock_vector_store_class.assert_called_once()
            pipeline.semantic_search.search.assert_called_once_with(
                repo_id="test_repo",
                query="test task",
                limit=50,
                score_threshold=0.7
            )

    @pytest.mark.asyncio
    async def test_graph_expansion_stage(self, pipeline, sample_nodes):
        """Test graph expansion stage."""
        pipeline._resolve_entry_point = AsyncMock(return_value=["func_a"])
        pipeline.graph.get_node = AsyncMock(return_value=sample_nodes[0])
        pipeline.graph.get_dependencies = AsyncMock(return_value=[])
        pipeline.graph.get_dependents = AsyncMock(return_value=[])

        result = await pipeline._graph_expansion("test_repo", ["func_a"])

        assert len(result) == 1
        assert result[0].id == "func_a"

    @pytest.mark.asyncio
    async def test_resolve_entry_point_file(self, pipeline, sample_nodes):
        """Test resolving file entry point."""
        pipeline.graph.get_nodes_in_file = AsyncMock(return_value=sample_nodes)

        result = await pipeline._resolve_entry_point("test_repo", "test.py")

        assert result == ["func_a"]

    @pytest.mark.asyncio
    async def test_resolve_entry_point_glob(self, pipeline, sample_nodes):
        """Test resolving glob entry point."""
        pipeline.graph.find_nodes_by_glob = AsyncMock(return_value=sample_nodes)

        result = await pipeline._resolve_entry_point("test_repo", "*.py")

        assert result == ["func_a"]

    @pytest.mark.asyncio
    async def test_resolve_entry_point_line_ref(self, pipeline, sample_nodes):
        """Test resolving line reference entry point."""
        pipeline.graph.get_node_at_line = AsyncMock(return_value=sample_nodes[0])

        result = await pipeline._resolve_entry_point("test_repo", "test.py:10")

        assert result == ["func_a"]

    @pytest.mark.asyncio
    async def test_resolve_entry_point_fqn(self, pipeline):
        """Test resolving FQN entry point."""
        result = await pipeline._resolve_entry_point("test_repo", "func_a")

        assert result == ["func_a"]

    def test_ranking_stage(self, pipeline, sample_search_results, sample_nodes):
        """Test ranking stage."""
        # Mock ranking engine
        pipeline.ranking_engine.rank_context = MagicMock(return_value=[])

        result = pipeline._ranking("test task", sample_search_results, sample_nodes, "gpt-4")

        pipeline.ranking_engine.rank_context.assert_called_once()

    def test_budget_allocation_stage(self, pipeline, sample_nodes):
        """Test budget allocation stage."""
        # Mock budget allocator
        mock_allocation = MagicMock()
        mock_allocation.selected_nodes = sample_nodes
        mock_allocation.total_tokens = 100
        mock_allocation.budget_used_pct = 50.0
        mock_allocation.nodes_truncated = 0
        mock_allocation.strategy_used = MagicMock(value="adaptive")

        pipeline.budget_allocator.allocate = MagicMock(return_value=mock_allocation)

        selected, stats = pipeline._budget_allocation([], 1000, "gpt-4")

        assert selected == sample_nodes
        assert stats == mock_allocation

    @pytest.mark.asyncio
    async def test_summarization_stage(self, pipeline, sample_nodes):
        """Test summarization stage."""
        # Mock summarizer
        pipeline.summarizer.summarize_node = AsyncMock(return_value="summarized content")

        # Make one node large
        large_node = Node(
            id="large_func",
            type="function",
            name="large_func",
            path="test.py",
            content="def large_func(): " + "x" * 2000  # Make it large
        )

        pipeline.token_counter.count_node = MagicMock(return_value=2000)  # Over threshold

        result = await pipeline._summarization([large_node], "gpt-4")

        assert len(result) == 1
        pipeline.summarizer.summarize_node.assert_called_once()

    def test_final_formatting_stage(self, pipeline, sample_nodes):
        """Test final formatting stage."""
        pipeline.formatter.to_markdown = MagicMock(return_value="markdown content")

        result = pipeline._final_formatting(sample_nodes, "markdown")

        assert result == "markdown content"
        pipeline.formatter.to_markdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_default_entry_points(self, pipeline, sample_nodes):
        """Test getting default entry points."""
        pipeline.graph.get_nodes_in_file = AsyncMock(side_effect=[
            sample_nodes,  # main.py
            [],  # app.py
            [],  # __init__.py
            [],  # index.py
        ])

        result = await pipeline._get_default_entry_points("test_repo")

        assert len(result) == 1
        assert "func_a" in result

    def test_pipeline_config(self):
        """Test pipeline configuration."""
        config = PipelineConfig(
            semantic_limit=100,
            graph_depth=3,
            enable_summarization=False
        )

        assert config.semantic_limit == 100
        assert config.graph_depth == 3
        assert config.enable_summarization is False

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, pipeline):
        """Test pipeline error handling."""
        pipeline._semantic_search = AsyncMock(side_effect=Exception("Search failed"))

        with pytest.raises(Exception, match="Search failed"):
            await pipeline.run("test_repo", "test task", 1000, "gpt-4")

    def test_pipeline_logging(self, pipeline, caplog):
        """Test that pipeline logs stages."""
        import logging
        caplog.set_level(logging.INFO)

        # This would require actually running the pipeline
        # For now, just check that logger is configured
        assert pipeline.logger.name == "codex_aura.context.pipeline"


@pytest.mark.asyncio
async def test_run_context_pipeline_function():
    """Test the convenience function."""
    with patch('codex_aura.context.pipeline.UnifiedContextPipeline') as mock_pipeline_class:
        mock_pipeline = MagicMock()
        mock_pipeline.run = AsyncMock(return_value="result")
        mock_pipeline_class.return_value = mock_pipeline

        with patch('codex_aura.search.embeddings.EmbeddingService'):
            from codex_aura.context.pipeline import run_context_pipeline

            result = await run_context_pipeline("repo", "task", 1000, "gpt-4")

            assert result == "result"
            mock_pipeline.run.assert_called_once_with(
                repo_id="repo",
                task="task",
                max_tokens=1000,
                model="gpt-4",
                entry_points=None,
                format="markdown"
            )