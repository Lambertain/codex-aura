"""Token counting functionality for different LLM models."""

import tiktoken

from ..models.node import Node


class TokenCounter:
    """Counts tokens for different LLM models."""

    encodings = {
        "gpt-4": tiktoken.encoding_for_model("gpt-4"),
        "gpt-3.5-turbo": tiktoken.encoding_for_model("gpt-3.5-turbo"),
        "claude": tiktoken.get_encoding("cl100k_base"),  # approximate
    }

    def count(self, text: str, model: str = "gpt-4") -> int:
        """Count tokens in text for specified model."""
        encoding = self.encodings.get(model, self.encodings["gpt-4"])
        return len(encoding.encode(text))

    def count_node(self, node: Node) -> int:
        """Count tokens for a code node."""
        # Assuming node has signature and content attributes
        signature = getattr(node, 'signature', '')
        content = getattr(node, 'content', '')
        return self.count(f"{signature}\n{content}")