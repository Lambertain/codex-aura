import ast
from dataclasses import dataclass
from typing import List

from openai import AsyncOpenAI
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
    def __init__(self, model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI()
        self.model = model
        self.tokenizer = tiktoken.encoding_for_model(model)

    async def embed_code(self, code: str) -> list[float]:
        """Generate embedding for code snippet."""
        # Truncate if too long
        tokens = self.tokenizer.encode(code)
        if len(tokens) > 8191:
            code = self.tokenizer.decode(tokens[:8191])

        response = await self.client.embeddings.create(
            model=self.model,
            input=code
        )
        return response.data[0].embedding

    async def embed_batch(self, codes: list[str]) -> list[list[float]]:
        """Batch embedding for efficiency."""
        response = await self.client.embeddings.create(
            model=self.model,
            input=codes
        )
        return [item.embedding for item in response.data]


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