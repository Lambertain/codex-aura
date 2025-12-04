"""Tests for custom impact plugin."""

import pytest
from unittest.mock import Mock

from codex_aura.models.graph import Graph
from codex_aura_custom_plugin.impact import CustomImpactPlugin


class TestCustomImpactPlugin:
    """Test cases for CustomImpactPlugin."""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance."""
        return CustomImpactPlugin()

    @pytest.fixture
    def mock_graph(self):
        """Create mock graph for testing."""
        graph = Mock(spec=Graph)

        # Create mock nodes
        nodes = {}
        for i in range(5):
            node = Mock()
            node.id = f"node_{i}"
            node.type = "function" if i % 2 == 0 else "class"
            node.file_path = f"/path/to/file_{i}.py"
            nodes[node.id] = node

        graph.nodes = nodes
        graph.get_neighbors = Mock(return_value=[])
        return graph

    def test_plugin_attributes(self, plugin):
        """Test plugin has correct attributes."""
        assert plugin.name == "custom_impact"
        assert plugin.version == "0.1.0"

    def test_analyze_impact_empty_files(self, plugin, mock_graph):
        """Test impact analysis with empty file list."""
        result = plugin.analyze_impact([], mock_graph)

        assert result.affected_files == []
        assert result.risk_level in ['low', 'medium', 'high']

    def test_analyze_impact_single_file(self, plugin, mock_graph):
        """Test impact analysis with single changed file."""
        changed_files = ["/path/to/file_0.py"]

        # Mock node finding
        plugin._find_node_by_file = Mock(return_value=mock_graph.nodes["node_0"])

        result = plugin.analyze_impact(changed_files, mock_graph)

        assert isinstance(result.affected_files, list)
        assert result.risk_level in ['low', 'medium', 'high']

    def test_analyze_impact_multiple_files(self, plugin, mock_graph):
        """Test impact analysis with multiple changed files."""
        changed_files = ["/path/to/file_0.py", "/path/to/file_1.py"]

        # Mock node finding
        def mock_find_node(graph, file_path):
            for node in graph.nodes.values():
                if node.file_path == file_path:
                    return node
            return None

        plugin._find_node_by_file = mock_find_node

        result = plugin.analyze_impact(changed_files, mock_graph)

        assert isinstance(result.affected_files, list)
        assert result.risk_level in ['low', 'medium', 'high']

    def test_get_capabilities(self, plugin):
        """Test capabilities reporting."""
        caps = plugin.get_capabilities()

        expected_caps = {
            "deep_analysis": True,
            "performance_tracking": False,
            "risk_assessment": True
        }

        assert caps == expected_caps

    def test_find_node_by_file(self, plugin, mock_graph):
        """Test node finding by file path."""
        file_path = "/path/to/file_0.py"
        node = plugin._find_node_by_file(mock_graph, file_path)

        assert node is not None
        assert node.file_path == file_path

    def test_find_node_by_file_not_found(self, plugin, mock_graph):
        """Test node finding when file not found."""
        file_path = "/path/to/nonexistent.py"
        node = plugin._find_node_by_file(mock_graph, file_path)

        assert node is None

    def test_extract_file_paths(self, plugin):
        """Test file path extraction from nodes."""
        nodes = []
        for i in range(3):
            node = Mock()
            node.file_path = f"/path/to/file_{i}.py"
            nodes.append(node)

        file_paths = plugin._extract_file_paths(nodes)

        assert len(file_paths) == 3
        assert "/path/to/file_0.py" in file_paths
        assert "/path/to/file_1.py" in file_paths
        assert "/path/to/file_2.py" in file_paths

    def test_calculate_node_impact(self, plugin):
        """Test node impact calculation."""
        node = Mock()
        node.type = "function"
        node.file_path = "/path/to/core.py"

        direct_deps = [Mock(), Mock()]  # 2 direct dependencies
        indirect_deps = [Mock(), Mock(), Mock()]  # 3 indirect dependencies

        impact = plugin._calculate_node_impact(node, direct_deps, indirect_deps)

        # Should return positive integer
        assert isinstance(impact, int)
        assert impact > 0

    def test_assess_risk_level(self, plugin):
        """Test risk level assessment."""
        # Low risk
        risk = plugin._assess_risk_level(3, 2)  # score 3, 2 affected files
        assert risk == "low"

        # Medium risk
        risk = plugin._assess_risk_level(10, 5)  # score 10, 5 affected files
        assert risk == "medium"

        # High risk
        risk = plugin._assess_risk_level(20, 15)  # score 20, 15 affected files
        assert risk == "high"