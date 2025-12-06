"""Content summarization for token budget management."""

from typing import Optional

from ..models.node import Node
from .counter import TokenCounter


class ContentSummarizer:
    """Summarizes content to fit within token budgets."""

    def __init__(self, counter: TokenCounter = None, llm=None):
        self.counter = counter or TokenCounter()
        self.llm = llm  # Optional LLM for advanced summarization

    async def summarize_node(
        self,
        node: Node,
        target_tokens: int
    ) -> str:
        """Summarize node content to fit token budget."""
        content = getattr(node, 'content', '')
        if self.counter.count(content) <= target_tokens:
            return content

        # Strategy 1: Keep signature + docstring only
        if node.type == "function":
            signature = getattr(node, 'signature', '')
            docstring = getattr(node, 'docstring', '') or ''
            summary = f"{signature}\n    '''{docstring}'''"
            if self.counter.count(summary) <= target_tokens:
                return summary

        # Strategy 2: LLM summarization
        if self.llm:
            prompt = f"Summarize this code in {target_tokens} tokens:\n{content}"
            try:
                summary = await self.llm.generate(prompt, max_tokens=target_tokens)
                return summary
            except Exception:
                # Fallback if LLM fails
                pass

        # Strategy 3: Simple truncation as fallback
        return self._truncate_content(content, target_tokens)

    def _truncate_content(self, content: str, target_tokens: int) -> str:
        """Simple content truncation fallback."""
        if self.counter.count(content) <= target_tokens:
            return content

        # Binary search for the right length
        left, right = 0, len(content)
        while left < right:
            mid = (left + right + 1) // 2
            if self.counter.count(content[:mid]) <= target_tokens:
                left = mid
            else:
                right = mid - 1

        truncated = content[:left]
        # Try to end at a complete line
        if '\n' in truncated:
            last_newline = truncated.rfind('\n')
            if last_newline > len(truncated) * 0.8:  # Don't cut too much
                truncated = truncated[:last_newline]

        return truncated + "\n# ... (truncated)"