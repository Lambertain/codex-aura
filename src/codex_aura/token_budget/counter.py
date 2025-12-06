import tiktoken
from functools import lru_cache
from typing import Literal

from ..models.node import Node


ModelName = Literal[
    "gpt-4", "gpt-4-turbo", "gpt-4o",
    "gpt-3.5-turbo",
    "claude-3-opus", "claude-3-sonnet", "claude-3-haiku",
    "claude-3.5-sonnet"
]


class TokenCounter:
    """
    Accurate token counting for different LLM models.

    Uses tiktoken for OpenAI models and approximations for others.
    """

    # Model to encoding mapping
    ENCODINGS = {
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4o": "o200k_base",
        "gpt-3.5-turbo": "cl100k_base",
        # Claude uses similar tokenization to cl100k
        "claude-3-opus": "cl100k_base",
        "claude-3-sonnet": "cl100k_base",
        "claude-3-haiku": "cl100k_base",
        "claude-3.5-sonnet": "cl100k_base",
    }

    # Claude tokenization multiplier (slightly different from OpenAI)
    CLAUDE_MULTIPLIER = 1.05

    def __init__(self):
        self._encodings: dict[str, tiktoken.Encoding] = {}

    @lru_cache(maxsize=10)
    def _get_encoding(self, model: ModelName) -> tiktoken.Encoding:
        """Get or create encoding for model."""
        encoding_name = self.ENCODINGS.get(model, "cl100k_base")
        return tiktoken.get_encoding(encoding_name)

    def count(self, text: str, model: ModelName = "gpt-4") -> int:
        """
        Count tokens in text for specified model.

        Args:
            text: Text to count tokens for
            model: Target LLM model

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        encoding = self._get_encoding(model)
        token_count = len(encoding.encode(text))

        # Apply Claude multiplier if needed
        if model.startswith("claude"):
            token_count = int(token_count * self.CLAUDE_MULTIPLIER)

        return token_count

    def count_node(self, node: Node, model: ModelName = "gpt-4") -> int:
        """
        Count tokens for a code node.

        Includes signature, docstring, and content.
        """
        parts = []

        # File path as context
        parts.append(f"# {node.path}")

        # Signature (using name as signature)
        if node.name:
            parts.append(node.name)

        # Docstring
        if node.docstring:
            parts.append(f'"""{node.docstring}"""')

        # Content
        if node.content:
            parts.append(node.content)

        full_text = "\n".join(parts)
        return self.count(full_text, model)

    def count_batch(
        self,
        texts: list[str],
        model: ModelName = "gpt-4"
    ) -> list[int]:
        """Count tokens for multiple texts efficiently."""
        encoding = self._get_encoding(model)
        multiplier = self.CLAUDE_MULTIPLIER if model.startswith("claude") else 1.0

        return [
            int(len(encoding.encode(text)) * multiplier)
            for text in texts
        ]

    def estimate_from_chars(self, char_count: int, model: ModelName = "gpt-4") -> int:
        """
        Rough estimate of tokens from character count.

        Useful for quick estimates without full tokenization.
        Average: ~4 chars per token for code.
        """
        chars_per_token = 3.5 if model.startswith("claude") else 4.0
        return int(char_count / chars_per_token)

    def truncate_to_tokens(
        self,
        text: str,
        max_tokens: int,
        model: ModelName = "gpt-4"
    ) -> str:
        """Truncate text to fit within token limit."""
        encoding = self._get_encoding(model)
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return text

        truncated_tokens = tokens[:max_tokens]
        return encoding.decode(truncated_tokens)