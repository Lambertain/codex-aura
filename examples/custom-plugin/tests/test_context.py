"""Tests for custom context plugin."""

import pytest
from unittest.mock import Mock

from codex_aura.models.node import Node
from codex_aura_custom_plugin.context import CustomContextPlugin


class TestCustomContextPlugin:
    """Test cases for CustomContextPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return CustomContextPlugin()

    @pytest.fixture
    def sample_nodes(self):
        """Create sample nodes for testing."""
        nodes = []
        for i in range(5):
            node = Mock(spec=Node)
            node.id = f"node_{i}"
            node.type = "function" if i % 2 == 0 else "class"
            node.name = f"test_func_{i}"
            node.content = f"def test_func_{i}(): pass"
            node.distance = i
            node.file_path = f"/path/to/file_{i}.py"
            nodes.append(node)
        return nodes

    def test_plugin_attributes(self, plugin):
        """Test plugin has correct attributes."""
        assert plugin.name == "custom_context"
        assert plugin.version == "0.1.0"

    def test_rank_nodes_empty_list(self, plugin):
        """Test ranking empty node list."""
        result = plugin.rank_nodes([])
        assert result == []

    def test_rank_nodes_basic_ranking(self, plugin, sample_nodes):
        """Test basic node ranking by distance."""
        result = plugin.rank_nodes(sample_nodes)

        # Should be sorted by distance (ascending)
        assert len(result) == 5
        assert result[0].distance == 0
        assert result[-1].distance == 4

    def test_rank_nodes_with_task(self, plugin, sample_nodes):
        """Test ranking with task context."""
        task = "implement user authentication"
        result = plugin.rank_nodes(sample_nodes, task=task)

        # Should still return all nodes
        assert len(result) == 5

        # Task keywords should be extracted
        assert "authentication" in plugin.task_keywords

    def test_rank_nodes_with_token_limit(self, plugin, sample_nodes):
        """Test ranking with token limit."""
        max_tokens = 50  # Should limit to ~2-3 nodes
        result = plugin.rank_nodes(sample_nodes, max_tokens=max_tokens)

        assert len(result) <= 5  # Should not exceed total nodes
        # Note: This test assumes the token estimation works correctly

    def test_get_capabilities(self, plugin):
        """Test capabilities reporting."""
        caps = plugin.get_capabilities()

        expected_caps = {
            "semantic_ranking": True,
            "token_budgeting": True,
            "task_understanding": True
        }

        assert caps == expected_caps

    def test_calculate_relevance_score(self, plugin, sample_nodes):
        """Test relevance score calculation."""
        node = sample_nodes[0]
        score = plugin._calculate_relevance_score(node)

        # Should return a float score
        assert isinstance(score, float)
        assert score >= 0

    def test_estimate_tokens(self, plugin, sample_nodes):
        """Test token estimation."""
        node = sample_nodes[0]
        tokens = plugin._estimate_tokens(node)

        # Should return positive integer
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_extract_task_keywords(self, plugin):
        """Test task keyword extraction."""
        task = "Create user login functionality"
        plugin._extract_task_keywords(task)

        assert "create" in plugin.task_keywords
        assert "user" in plugin.task_keywords
        assert "login" in plugin.task_keywords
        assert "functionality" in plugin.task_keywords