"""Tests for plugin system."""

import pytest
from pathlib import Path

from src.codex_aura.plugins.registry import PluginRegistry
from src.codex_aura.plugins.config import PluginConfig
from src.codex_aura.plugins.builtin.context_basic import BasicContextPlugin
from src.codex_aura.plugins.builtin.impact_basic import BasicImpactPlugin


def test_plugin_registry():
    """Test that plugins are registered correctly."""
    # Import plugins to trigger registration
    from src.codex_aura.plugins import builtin  # noqa: F401

    # Check context plugins
    context_plugins = PluginRegistry.list_context_plugins()
    assert "basic" in context_plugins

    # Check impact plugins
    impact_plugins = PluginRegistry.list_impact_plugins()
    assert "basic" in impact_plugins

    # Get plugin instances
    context_plugin_class = PluginRegistry.get_context_plugin("basic")
    assert context_plugin_class == BasicContextPlugin

    impact_plugin_class = PluginRegistry.get_impact_plugin("basic")
    assert impact_plugin_class == BasicImpactPlugin


def test_plugin_config():
    """Test plugin configuration loading."""
    config_path = Path(__file__).parent.parent / ".codex-aura" / "plugins.yaml"
    config = PluginConfig(config_path)

    # Test default values
    assert config.get_context_plugin() == "basic"
    assert config.get_context_fallback_plugin() == "basic"
    assert config.get_impact_plugin() == "basic"

    # Test analyzer config
    assert config.get_analyzer_plugin("python") == "codex_aura.plugins.builtin.python"

    # Test premium config
    assert config.get_premium_plugin("context") == "codex_aura_premium.semantic"
    assert config.get_premium_plugin("impact") == "codex_aura_premium.impact_advanced"


def test_basic_context_plugin():
    """Test BasicContextPlugin functionality."""
    from src.codex_aura.models.node import Node

    plugin = BasicContextPlugin()

    # Create test nodes (without distance attributes - basic plugin handles this)
    nodes = [
        Node(id="node1", type="file", name="file1.py", path="file1.py"),
        Node(id="node2", type="file", name="file2.py", path="file2.py"),
        Node(id="node3", type="file", name="file3.py", path="file3.py"),
    ]

    # Test ranking (without distance, should maintain order)
    ranked = plugin.rank_nodes(nodes)
    assert len(ranked) == 3
    assert ranked[0].id == "node1"  # Original order maintained
    assert ranked[1].id == "node2"
    assert ranked[2].id == "node3"

    # Test token limiting
    limited = plugin.rank_nodes(nodes, max_tokens=50)  # Should limit to ~0-1 nodes
    assert len(limited) <= len(nodes)

    # Test capabilities
    capabilities = plugin.get_capabilities()
    assert capabilities["semantic_ranking"] is False
    assert capabilities["token_budgeting"] is False
    assert capabilities["task_understanding"] is False


def test_basic_impact_plugin():
    """Test BasicImpactPlugin functionality."""
    from src.codex_aura.models.graph import Graph, Repository, Stats
    from src.codex_aura.models.node import Node
    from src.codex_aura.models.edge import Edge, EdgeType
    from datetime import datetime

    plugin = BasicImpactPlugin()

    # Create test graph
    nodes = [
        Node(id="file1.py", type="file", name="file1.py", path="file1.py"),
        Node(id="file2.py", type="file", name="file2.py", path="file2.py"),
        Node(id="func1", type="function", name="func1", path="file1.py"),
        Node(id="func2", type="function", name="func2", path="file2.py"),
    ]

    edges = [
        Edge(source="func2", target="func1", type=EdgeType.CALLS),
    ]

    graph = Graph(
        version="0.1",
        generated_at=datetime.now(),
        repository=Repository(path="/test", name="test"),
        stats=Stats(total_nodes=4, total_edges=1, node_types={"file": 2, "function": 2}),
        nodes=nodes,
        edges=edges,
    )

    # Test impact analysis
    changed_files = ["file1.py"]
    report = plugin.analyze_impact(changed_files, graph)

    assert "file2.py" in report.affected_files
    assert report.risk_level == "low"  # Only 1 affected file