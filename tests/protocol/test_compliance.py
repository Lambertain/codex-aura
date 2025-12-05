"""Protocol compliance tests for Codex Aura."""

import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

from codex_aura.models.node import Node, BlameInfo
from codex_aura.models.edge import Edge, EdgeType


def load_schema(schema_name: str) -> dict:
    """Load a JSON schema from the schemas directory."""
    schema_path = Path(__file__).parent.parent.parent / "schemas" / schema_name
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_sample_node() -> Node:
    """Create a sample node for testing."""
    return Node(
        id="test_node_123",
        type="function",
        name="process_data",
        path="src/utils.py",
        lines=[10, 25],
        docstring="Process input data and return results.",
        blame=BlameInfo(
            primary_author="john.doe@example.com",
            contributors=["john.doe@example.com", "jane.smith@example.com"],
            author_distribution={"john.doe@example.com": 15, "jane.smith@example.com": 5}
        )
    )


def create_sample_edge() -> Edge:
    """Create a sample edge for testing."""
    return Edge(
        source="node_123",
        target="node_456",
        type=EdgeType.CALLS,
        line=15
    )


def test_node_schema_compliance():
    """Test that Node model complies with node.schema.json."""
    node = create_sample_node()
    schema = load_schema("node.schema.json")

    # Convert node to dict format
    node_dict = node.model_dump()

    # Validate against schema
    try:
        validate(node_dict, schema)
    except ValidationError as e:
        pytest.fail(f"Node schema validation failed: {e.message}")


def test_edge_schema_compliance():
    """Test that Edge model complies with edge.schema.json."""
    edge = create_sample_edge()
    schema = load_schema("edge.schema.json")

    # Convert edge to dict format
    edge_dict = edge.model_dump()

    # Validate against schema
    try:
        validate(edge_dict, schema)
    except ValidationError as e:
        pytest.fail(f"Edge schema validation failed: {e.message}")


def test_api_response_compliance():
    """Test that API responses comply with context-response.schema.json."""
    # Sample context response data
    response_data = {
        "context_nodes": [
            {
                "id": "node_123",
                "type": "function",
                "path": "src/utils.py",
                "code": "def process_data():\n    return 'processed'",
                "relevance": 0.95
            },
            {
                "id": "node_456",
                "type": "class",
                "path": "src/models.py",
                "relevance": 0.85
            }
        ],
        "total_nodes": 2,
        "truncated": False
    }

    schema = load_schema("context-response.schema.json")

    # Validate against schema
    try:
        validate(response_data, schema)
    except ValidationError as e:
        pytest.fail(f"Context response schema validation failed: {e.message}")


def test_graph_schema_compliance():
    """Test that Graph model complies with graph.schema.json."""
    from codex_aura.models.graph import Graph, Repository, Stats

    # Create sample graph data
    graph = Graph(
        version="1.0",
        generated_at="2024-01-01T00:00:00Z",
        repository=Repository(
            path="/path/to/repo",
            name="test-repo"
        ),
        stats=Stats(
            total_nodes=10,
            total_edges=15,
            node_types={"file": 3, "class": 4, "function": 3},
            average_complexity=2.5,
            hot_spots_count=2
        ),
        nodes=[create_sample_node()],
        edges=[create_sample_edge()],
        sha="abc123def456"
    )

    schema = load_schema("graph.schema.json")

    # Convert graph to dict format
    graph_dict = graph.model_dump()

    # Validate against schema
    try:
        validate(graph_dict, schema)
    except ValidationError as e:
        pytest.fail(f"Graph schema validation failed: {e.message}")


def test_context_request_schema_compliance():
    """Test that context request complies with context-request.schema.json."""
    # Sample context request data
    request_data = {
        "graph_id": "g_abc123def456",
        "entry_points": ["node_123", "node_456"],
        "depth": 3,
        "include_code": True,
        "max_nodes": 50
    }

    schema = load_schema("context-request.schema.json")

    # Validate against schema
    try:
        validate(request_data, schema)
    except ValidationError as e:
        pytest.fail(f"Context request schema validation failed: {e.message}")


def test_node_with_extensions_compliance():
    """Test that nodes with extension fields still validate."""
    node = create_sample_node()

    # Add extension fields (should start with 'x-')
    node_dict = node.model_dump()
    node_dict["x-custom-field"] = "custom value"
    node_dict["x-company-specific"] = {"nested": "data"}

    schema = load_schema("node.schema.json")

    # Should still validate with extensions
    try:
        validate(node_dict, schema)
    except ValidationError as e:
        pytest.fail(f"Node with extensions schema validation failed: {e.message}")


def test_edge_with_extensions_compliance():
    """Test that edges with extension fields still validate."""
    edge = create_sample_edge()

    # Add extension fields
    edge_dict = edge.model_dump()
    edge_dict["x-custom-metadata"] = "additional info"

    schema = load_schema("edge.schema.json")

    # Should still validate with extensions
    try:
        validate(edge_dict, schema)
    except ValidationError as e:
        pytest.fail(f"Edge with extensions schema validation failed: {e.message}")


def test_invalid_node_schema_fails():
    """Test that invalid node data fails schema validation."""
    schema = load_schema("node.schema.json")

    # Invalid node - missing required 'id' field
    invalid_node = {
        "type": "function",
        "name": "test_func",
        "path": "test.py"
    }

    with pytest.raises(ValidationError):
        validate(invalid_node, schema)


def test_invalid_edge_schema_fails():
    """Test that invalid edge data fails schema validation."""
    schema = load_schema("edge.schema.json")

    # Invalid edge - invalid type
    invalid_edge = {
        "source": "node1",
        "target": "node2",
        "type": "INVALID_TYPE"
    }

    with pytest.raises(ValidationError):
        validate(invalid_edge, schema)


def test_custom_edge_type_compliance():
    """Test that custom edge types starting with CUSTOM_ are allowed."""
    from codex_aura.models.edge import Edge, EdgeType

    # Test creating edge with custom type
    custom_edge = Edge(
        source="node_123",
        target="node_456",
        type=EdgeType("CUSTOM_ANNOTATION"),  # Should work with _missing_ method
        line=20
    )

    assert custom_edge.type == "CUSTOM_ANNOTATION"
    assert isinstance(custom_edge.type, EdgeType)

    # Test schema validation
    schema = load_schema("edge.schema.json")
    edge_dict = custom_edge.model_dump()

    # Should validate successfully
    try:
        validate(edge_dict, schema)
    except ValidationError as e:
        pytest.fail(f"Custom edge type schema validation failed: {e.message}")


def test_extension_fields_backwards_compatibility():
    """Test that extension fields don't break existing functionality."""
    # Test node without extensions still works
    node = create_sample_node()
    node_dict = node.model_dump()

    # Should not have any x- fields
    assert not any(key.startswith("x-") for key in node_dict.keys())

    # Test edge without extensions still works
    edge = create_sample_edge()
    edge_dict = edge.model_dump()

    # Should not have any x- fields
    assert not any(key.startswith("x-") for key in edge_dict.keys())

    # Both should still validate
    node_schema = load_schema("node.schema.json")
    edge_schema = load_schema("edge.schema.json")

    validate(node_dict, node_schema)
    validate(edge_dict, edge_schema)


def test_extension_field_validation():
    """Test that extension fields are properly validated."""
    node_schema = load_schema("node.schema.json")
    edge_schema = load_schema("edge.schema.json")

    # Valid extension fields
    valid_node = create_sample_node().model_dump()
    valid_node["x-custom-field"] = "value"
    valid_node["x-company-data"] = {"nested": True}

    valid_edge = create_sample_edge().model_dump()
    valid_edge["x-metadata"] = "additional info"

    # Should validate
    validate(valid_node, node_schema)
    validate(valid_edge, edge_schema)

    # Invalid extension fields (don't start with x-)
    invalid_node = create_sample_node().model_dump()
    invalid_node["custom-field"] = "value"  # Missing x- prefix

    invalid_edge = create_sample_edge().model_dump()
    invalid_edge["metadata"] = "info"  # Missing x- prefix

    # Should fail validation
    with pytest.raises(ValidationError):
        validate(invalid_node, node_schema)

    with pytest.raises(ValidationError):
        validate(invalid_edge, edge_schema)