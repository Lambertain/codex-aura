"""Content summarization for token budget management."""

from enum import Enum
from typing import Optional

from ..models.node import Node
from .counter import TokenCounter


class SummarizationLevel(str, Enum):
    FULL = "full"           # Complete content
    SIGNATURE = "signature"  # Signature + docstring only
    STUB = "stub"           # Just signature
    REFERENCE = "reference"  # Just name and path


class ContentSummarizer:
    """
    Summarize code content to fit token budgets.

    Strategies (from most to least detail):
    1. FULL: Include everything
    2. SIGNATURE: Signature + docstring + type hints
    3. STUB: Just the signature
    4. REFERENCE: Just a reference to the node
    """

    def __init__(self, token_counter: TokenCounter, llm_client: "LLMClient" = None):
        self.counter = token_counter
        self.llm = llm_client

    def summarize_node(
        self,
        node: "Node",
        target_tokens: int,
        model: str = "gpt-4",
        level: SummarizationLevel = None
    ) -> str:
        """
        Summarize node to fit within target tokens.

        Automatically selects appropriate level if not specified.
        """
        full_content = self._format_full(node)
        full_tokens = self.counter.count(full_content, model)

        # If already fits, return full
        if full_tokens <= target_tokens:
            return full_content

        # Auto-select level if not specified
        if level is None:
            level = self._select_level(node, target_tokens, model)

        if level == SummarizationLevel.FULL:
            return self.counter.truncate_to_tokens(full_content, target_tokens, model)
        elif level == SummarizationLevel.SIGNATURE:
            return self._format_signature(node, target_tokens, model)
        elif level == SummarizationLevel.STUB:
            return self._format_stub(node)
        else:
            return self._format_reference(node)

    def _format_full(self, node: "Node") -> str:
        """Full content with file path context."""
        return f"# {node.path}:{node.start_line}\n{node.content}"

    def _format_signature(
        self,
        node: "Node",
        target_tokens: int,
        model: str
    ) -> str:
        """Signature + docstring format."""
        parts = [f"# {node.path}:{node.start_line}"]

        if node.type == "function":
            parts.append(node.signature or f"def {node.name}(...):")
            if node.docstring:
                # Include as much docstring as fits
                doc_tokens = target_tokens - self.counter.count("\n".join(parts), model) - 10
                if doc_tokens > 50:
                    truncated_doc = self.counter.truncate_to_tokens(
                        node.docstring, doc_tokens, model
                    )
                    parts.append(f'    """{truncated_doc}"""')
            parts.append("    ...")

        elif node.type == "class":
            parts.append(f"class {node.name}:")
            if node.docstring:
                doc_tokens = target_tokens - self.counter.count("\n".join(parts), model) - 10
                if doc_tokens > 50:
                    truncated_doc = self.counter.truncate_to_tokens(
                        node.docstring, doc_tokens, model
                    )
                    parts.append(f'    """{truncated_doc}"""')

            # Include method signatures
            methods = getattr(node, 'methods', [])[:5]  # Top 5 methods
            for method in methods:
                parts.append(f"    {method.signature}")
            if len(methods) > 5:
                parts.append(f"    # ... and {len(methods) - 5} more methods")

        return "\n".join(parts)

    def _format_stub(self, node: "Node") -> str:
        """Minimal stub format."""
        return f"# {node.path}:{node.start_line}\n{node.signature or node.name}"

    def _format_reference(self, node: "Node") -> str:
        """Just a reference."""
        return f"# See: {node.fqn} in {node.path}"

    def _select_level(
        self,
        node: "Node",
        target_tokens: int,
        model: str
    ) -> SummarizationLevel:
        """Auto-select appropriate summarization level."""
        # Try each level from most to least detailed
        levels = [
            SummarizationLevel.SIGNATURE,
            SummarizationLevel.STUB,
            SummarizationLevel.REFERENCE
        ]

        for level in levels:
            content = self.summarize_node(node, target_tokens * 2, model, level)
            if self.counter.count(content, model) <= target_tokens:
                return level

        return SummarizationLevel.REFERENCE

    async def llm_summarize(
        self,
        node: "Node",
        target_tokens: int,
        model: str = "gpt-4"
    ) -> str:
        """
        Use LLM to intelligently summarize code.

        More expensive but produces better summaries.
        """
        if not self.llm:
            return self.summarize_node(node, target_tokens, model, SummarizationLevel.SIGNATURE)

        prompt = f"""Summarize this code in approximately {target_tokens} tokens.
Keep the most important functionality, type signatures, and key logic.
```{node.language or 'python'}
{node.content}
```

Provide a concise summary that preserves the essential information."""

        response = await self.llm.generate(
            prompt,
            max_tokens=target_tokens + 50,
            model="gpt-3.5-turbo"  # Use cheaper model for summarization
        )

        return f"# {node.path} (summarized)\n{response}"