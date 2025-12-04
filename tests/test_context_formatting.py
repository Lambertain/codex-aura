"""Tests for Context formatting functionality."""

import pytest
from codex_aura.sdk.context import Context, ContextNode
from codex_aura.models.edge import Edge, EdgeType


class TestContextFormatting:
    """Test Context.to_prompt() method with different formats."""

    @pytest.fixture
    def sample_context_nodes(self):
        """Create sample context nodes for testing."""
        return [
            ContextNode(
                id="func_login",
                type="function",
                path="src/auth/login.py",
                code="def login(username: str, password: str) -> User:\n    '''Authenticate user and return User object.'''\n    user = get_user(username)\n    if not verify_password(password, user.password_hash):\n        raise AuthenticationError()\n    return user",
                relevance=1.0
            ),
            ContextNode(
                id="func_get_user",
                type="function",
                path="src/auth/user.py",
                code="def get_user(username: str) -> User:\n    return User.query.filter_by(username=username).first()",
                relevance=0.8
            ),
            ContextNode(
                id="func_verify_password",
                type="function",
                path="src/auth/security.py",
                code="def verify_password(password: str, hash: str) -> bool:\n    return bcrypt.checkpw(password.encode(), hash.encode())",
                relevance=0.7
            )
        ]

    @pytest.fixture
    def sample_edges(self):
        """Create sample edges for testing."""
        return [
            Edge(
                source="func_login",
                target="func_get_user",
                type=EdgeType.CALLS,
                line=3
            ),
            Edge(
                source="func_login",
                target="func_verify_password",
                type=EdgeType.CALLS,
                line=4
            )
        ]

    @pytest.fixture
    def sample_context(self, sample_context_nodes, sample_edges):
        """Create a sample Context object."""
        return Context(
            context_nodes=sample_context_nodes,
            total_nodes=3,
            truncated=False,
            edges=sample_edges
        )

    def test_markdown_format_basic(self, sample_context):
        """Test basic markdown formatting."""
        result = sample_context.to_prompt(format="markdown")

        assert "## Relevant Code Context" in result
        assert "### func_login" in result
        assert "### func_get_user" in result
        assert "### func_verify_password" in result
        assert "```python" in result
        assert "def login(username: str" in result

    def test_markdown_format_with_tree(self, sample_context):
        """Test markdown formatting with tree structure."""
        result = sample_context.to_prompt(format="markdown", include_tree=True)

        assert "### File Structure" in result
        assert "#### src/auth/login.py" in result
        assert "#### src/auth/user.py" in result
        assert "#### src/auth/security.py" in result

    def test_markdown_format_with_edges(self, sample_context):
        """Test markdown formatting with edges."""
        result = sample_context.to_prompt(format="markdown", include_edges=True)

        assert "### Dependencies" in result
        assert "`src/auth/login.py` **CALLS** `src/auth/user.py`" in result
        assert "`src/auth/login.py` **CALLS** `src/auth/security.py`" in result

    def test_plain_format_basic(self, sample_context):
        """Test basic plain text formatting."""
        result = sample_context.to_prompt(format="plain")

        assert "CODE CONTEXT" in result
        assert "CONTEXT NODES:" in result
        assert "func_login (function) - src/auth/login.py" in result
        assert "Relevance: 1.0" in result

    def test_plain_format_with_tree(self, sample_context):
        """Test plain text formatting with tree structure."""
        result = sample_context.to_prompt(format="plain", include_tree=True)

        assert "FILE STRUCTURE:" in result
        assert "src/auth/login.py:" in result

    def test_plain_format_with_edges(self, sample_context):
        """Test plain text formatting with edges."""
        result = sample_context.to_prompt(format="plain", include_edges=True)

        assert "DEPENDENCIES:" in result
        assert "src/auth/login.py CALLS src/auth/user.py" in result

    def test_xml_format_basic(self, sample_context):
        """Test basic XML formatting."""
        result = sample_context.to_prompt(format="xml")

        assert "<context>" in result
        assert "</context>" in result
        assert "<context_nodes>" in result
        assert '<node id="func_login"' in result
        assert 'type="function"' in result
        assert 'path="src/auth/login.py"' in result

    def test_xml_format_with_tree(self, sample_context):
        """Test XML formatting with tree structure."""
        result = sample_context.to_prompt(format="xml", include_tree=True)

        assert "<file_structure>" in result
        assert '<file path="src/auth/login.py">' in result

    def test_xml_format_with_edges(self, sample_context):
        """Test XML formatting with edges."""
        result = sample_context.to_prompt(format="xml", include_edges=True)

        assert "<dependencies>" in result
        assert 'type="CALLS"' in result
        assert 'source="src/auth/login.py"' in result
        assert 'target="src/auth/user.py"' in result

    def test_max_chars_truncation(self, sample_context):
        """Test max_chars truncation."""
        result = sample_context.to_prompt(format="markdown", max_chars=100)

        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    def test_max_chars_no_truncation(self, sample_context):
        """Test that content is not truncated when under max_chars."""
        result = sample_context.to_prompt(format="markdown", max_chars=10000)

        assert len(result) < 10000
        assert not result.endswith("...")

    def test_context_without_edges(self, sample_context_nodes):
        """Test formatting when context has no edges."""
        context = Context(
            context_nodes=sample_context_nodes,
            total_nodes=3,
            truncated=False,
            edges=None
        )

        result = context.to_prompt(format="markdown", include_edges=True)
        assert "### Dependencies" not in result

    def test_empty_context(self):
        """Test formatting with empty context."""
        context = Context(
            context_nodes=[],
            total_nodes=0,
            truncated=False,
            edges=None
        )

        result = context.to_prompt(format="markdown")
        assert "## Relevant Code Context" in result
        assert "CONTEXT NODES" not in result

    def test_default_format(self, sample_context):
        """Test that default format is markdown."""
        result_default = sample_context.to_prompt()
        result_markdown = sample_context.to_prompt(format="markdown")

        assert result_default == result_markdown

    def test_xml_escaping(self, sample_context_nodes):
        """Test that XML format properly escapes special characters."""
        # Create a node with XML-sensitive characters
        nodes_with_xml = sample_context_nodes + [
            ContextNode(
                id="func_xml_test",
                type="function",
                path="test.py",
                code='def test():\n    return "<>&\'"',
                relevance=0.5
            )
        ]

        context = Context(
            context_nodes=nodes_with_xml,
            total_nodes=4,
            truncated=False,
            edges=None
        )

        result = context.to_prompt(format="xml")
        assert "<" in result
        assert ">" in result
        assert "&" in result
        assert "<" not in result.replace("<context>", "").replace("<context_nodes>", "").replace('<node id="', "").replace('<code>', "")  # Allow expected XML tags