import ast
import asyncio
import time
from dataclasses import dataclass
from typing import List

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import tiktoken


@dataclass
class CodeChunk:
    id: str
    content: str
    type: str
    name: str
    file_path: str
    start_line: int
    end_line: int


@dataclass
class SearchResult:
    chunk: CodeChunk
    score: float


@dataclass
class RankedNode:
    fqn: str
    score: float


class EmbeddingService:
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        rate_limit_rpm: int = 3000,
        max_concurrent_requests: int = 10
    ):
        self.client = AsyncOpenAI()
        self.model = model
        self.tokenizer = tiktoken.encoding_for_model(model)
        self.rate_limit_rpm = rate_limit_rpm
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)
        self._min_interval = 60 / rate_limit_rpm if rate_limit_rpm else 0
        self._last_request = 0.0

    async def _respect_rate_limit(self):
        """Ensure we don't exceed RPM limits."""
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        sleep_for = self._min_interval - elapsed
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=30))
    async def embed_code(self, code: str) -> list[float]:
        """Generate embedding for code snippet with rate limiting and retries."""
        async with self._semaphore:
            await self._respect_rate_limit()
            tokens = self.tokenizer.encode(code)
            if len(tokens) > 8191:
                code = self.tokenizer.decode(tokens[:8191])

            response = await self.client.embeddings.create(
                model=self.model,
                input=code
            )
            self._last_request = time.monotonic()
            return response.data[0].embedding

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=30))
    async def embed_batch(self, codes: list[str], batch_size: int = 100) -> list[list[float]]:
        """Batch embedding with rate limiting and pauses between batches."""
        all_embeddings: list[list[float]] = []
        pause = max(self._min_interval, 0.5) if self._min_interval else 0.5

        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]
            # Truncate overly long inputs in batch
            safe_batch = []
            for item in batch:
                tokens = self.tokenizer.encode(item)
                if len(tokens) > 8191:
                    item = self.tokenizer.decode(tokens[:8191])
                safe_batch.append(item)

            async with self._semaphore:
                await self._respect_rate_limit()
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=safe_batch
                )
                self._last_request = time.monotonic()
                all_embeddings.extend([item.embedding for item in response.data])

            # Pause between batches to honor rate limit and avoid 429s
            if i + batch_size < len(codes):
                await asyncio.sleep(pause)

        return all_embeddings


class CodeChunker:
    """Split code into semantic chunks for embedding."""

    def chunk_file(self, file_content: str, file_path: str) -> list[CodeChunk]:
        """Chunk file into functions/classes/blocks."""
        tree = ast.parse(file_content)
        chunks = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                chunks.append(CodeChunk(
                    content=ast.get_source_segment(file_content, node),
                    type="function",
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno
                ))
            elif isinstance(node, ast.ClassDef):
                # Class docstring + method signatures
                chunks.append(CodeChunk(
                    content=self._extract_class_summary(node, file_content),
                    type="class",
                    name=node.name,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno
                ))

        return chunks

    def chunk_node(self, node: "Node") -> list[CodeChunk]:
        """Chunk a single node into code chunks."""
        if node.type == "file":
            # For file nodes, use the existing chunk_file method
            return self.chunk_file(node.content, node.path)
        else:
            # For class/function nodes, create chunks based on their content
            chunks = []
            tree = ast.parse(node.content)

            for ast_node in ast.walk(tree):
                if isinstance(ast_node, ast.FunctionDef):
                    chunks.append(CodeChunk(
                        id=f"{node.fqn}::{ast_node.name}",
                        content=ast.get_source_segment(node.content, ast_node),
                        type="function",
                        name=ast_node.name,
                        file_path=node.path,
                        start_line=ast_node.lineno,
                        end_line=ast_node.end_lineno
                    ))
                elif isinstance(ast_node, ast.ClassDef):
                    chunks.append(CodeChunk(
                        id=f"{node.fqn}::{ast_node.name}",
                        content=self._extract_class_summary(ast_node, node.content),
                        type="class",
                        name=ast_node.name,
                        file_path=node.path,
                        start_line=ast_node.lineno,
                        end_line=ast_node.end_lineno
                    ))

            return chunks

    def _extract_class_summary(self, node: ast.ClassDef, file_content: str) -> str:
        """Extract class docstring and method signatures."""
        summary_parts = []

        # Add class definition
        summary_parts.append(ast.get_source_segment(file_content, node))

        # Add method signatures
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                # Get just the function signature
                signature_end = item.body[0].lineno if item.body else item.end_lineno
                # This is approximate, but for summary
                summary_parts.append(f"    def {item.name}(...):")

        return "\n".join(summary_parts)
