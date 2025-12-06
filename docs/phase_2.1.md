# 📋 Фаза 2.1: Cloud Service & Premium Features

**Длительность:** 8-12 недель  
**Цель:** Запуск облачного сервиса с монетизацией  
**Результат:** Production-ready SaaS + первые платящие клиенты

### E1-1: Neo4j Docker Setup
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Настроить Neo4j для локальной разработки и production.

**Действия:**
- [ ] docker-compose.yml с Neo4j
- [ ] Конфигурация для разных environments
- [ ] Health check скрипт
- [ ] Backup/restore процедуры

**docker-compose.yml:**
```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
```

**Критерии приёмки:**
- [ ] Neo4j запускается через docker-compose
- [ ] APOC plugin установлен
- [ ] Browser доступен на :7474

---

### E1-2: Neo4j Python Driver Integration
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Интеграция neo4j-driver в проект.

**Реализация:**
```python
# src/codex_aura/storage/neo4j_client.py

from neo4j import GraphDatabase, AsyncGraphDatabase
from contextlib import asynccontextmanager

class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    
    async def close(self):
        await self._driver.close()
    
    @asynccontextmanager
    async def session(self):
        async with self._driver.session() as session:
            yield session
    
    async def health_check(self) -> bool:
        async with self.session() as session:
            result = await session.run("RETURN 1")
            return await result.single() is not None
```

**Критерии приёмки:**
- [ ] Connection pool работает
- [ ] Async операции поддерживаются
- [ ] Health check проходит

---

### E1-3: Graph Schema Design
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Спроектировать Cypher-схему для графа кода.

**Схема:**
```cypher
// Node types
CREATE CONSTRAINT file_path IF NOT EXISTS 
FOR (f:File) REQUIRE f.path IS UNIQUE;

CREATE CONSTRAINT class_fqn IF NOT EXISTS
FOR (c:Class) REQUIRE c.fqn IS UNIQUE;

CREATE CONSTRAINT function_fqn IF NOT EXISTS
FOR (fn:Function) REQUIRE fn.fqn IS UNIQUE;

// Indexes for performance
CREATE INDEX file_repo IF NOT EXISTS FOR (f:File) ON (f.repo_id);
CREATE INDEX node_name IF NOT EXISTS FOR (n:Node) ON (n.name);

// Edge types
// (:File)-[:CONTAINS]->(:Class)
// (:File)-[:IMPORTS]->(:File)
// (:Class)-[:EXTENDS]->(:Class)
// (:Function)-[:CALLS]->(:Function)
// (:Class)-[:HAS_METHOD]->(:Function)
```

**Критерии приёмки:**
- [ ] Constraints созданы
- [ ] Indexes оптимизированы
- [ ] Миграции задокументированы

---

### E1-4: Graph Import from SQLite
**Оценка:** 4h | **Приоритет:** P0

**Описание:**
Миграция существующих графов из SQLite в Neo4j.

**Реализация:**
```python
async def migrate_graph_to_neo4j(
    sqlite_graph: Graph,
    neo4j_client: Neo4jClient
) -> str:
    """Migrate graph from SQLite to Neo4j."""
    async with neo4j_client.session() as session:
        # Create nodes
        for node in sqlite_graph.nodes:
            await session.run("""
                MERGE (n:Node {fqn: $fqn})
                SET n += $properties
                SET n:$label
            """, fqn=node.fqn, properties=node.dict(), label=node.type)
        
        # Create edges
        for edge in sqlite_graph.edges:
            await session.run("""
                MATCH (a:Node {fqn: $source})
                MATCH (b:Node {fqn: $target})
                MERGE (a)-[r:$type]->(b)
                SET r += $properties
            """, source=edge.source, target=edge.target, 
                type=edge.type, properties=edge.dict())
    
    return neo4j_graph_id
```

**Критерии приёмки:**
- [ ] Все nodes мигрируют
- [ ] Все edges мигрируют
- [ ] Свойства сохраняются
- [ ] Batch import для больших графов

---

### E1-5: Neo4j Query Layer
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Реализовать типичные запросы к графу.

**Запросы:**
```python
class GraphQueries:
    async def get_dependencies(self, fqn: str, depth: int = 2) -> list[Node]:
        """Get all dependencies up to N levels deep."""
        query = """
        MATCH path = (start:Node {fqn: $fqn})-[:IMPORTS|CALLS|EXTENDS*1..$depth]->(dep)
        RETURN DISTINCT dep, length(path) as distance
        ORDER BY distance
        """
        ...
    
    async def get_dependents(self, fqn: str, depth: int = 2) -> list[Node]:
        """Get all nodes that depend on this node."""
        query = """
        MATCH path = (dependent)-[:IMPORTS|CALLS|EXTENDS*1..$depth]->(target:Node {fqn: $fqn})
        RETURN DISTINCT dependent, length(path) as distance
        ORDER BY distance
        """
        ...
    
    async def shortest_path(self, source: str, target: str) -> list[Node]:
        """Find shortest path between two nodes."""
        query = """
        MATCH path = shortestPath(
            (a:Node {fqn: $source})-[*]-(b:Node {fqn: $target})
        )
        RETURN path
        """
        ...
```

**Критерии приёмки:**
- [ ] get_dependencies работает
- [ ] get_dependents работает
- [ ] shortest_path работает
- [ ] Результаты кешируются

---

### E1-6: Storage Backend Abstraction
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Абстракция для переключения между SQLite и Neo4j.

**Реализация:**
```python
from abc import ABC, abstractmethod
from enum import Enum

class StorageBackend(str, Enum):
    SQLITE = "sqlite"
    NEO4J = "neo4j"

class GraphStorage(ABC):
    @abstractmethod
    async def save_graph(self, graph: Graph) -> str: ...
    
    @abstractmethod
    async def load_graph(self, graph_id: str) -> Graph: ...
    
    @abstractmethod
    async def query_dependencies(self, fqn: str, depth: int) -> list[Node]: ...

class SQLiteStorage(GraphStorage): ...
class Neo4jStorage(GraphStorage): ...

def get_storage(backend: StorageBackend) -> GraphStorage:
    if backend == StorageBackend.SQLITE:
        return SQLiteStorage()
    return Neo4jStorage()
```

**Критерии приёмки:**
- [ ] Интерфейс единый
- [ ] SQLite работает как fallback
- [ ] Конфигурация через env

---

## E2: 🔍 Semantic Search

> **Зависимость от E3:** Нет — можно начинать сразу

### E2-1: Vector Database Setup (Qdrant)
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Настроить Qdrant для хранения embeddings.

**docker-compose.yml:**
```yaml
services:
  qdrant:
    image: qdrant/qdrant:v1.7.4
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
```

**Критерии приёмки:**
- [ ] Qdrant запускается
- [ ] REST API доступен
- [ ] gRPC API доступен

---

### E2-2: Embedding Service
**Оценка:** 4h | **Приоритет:** P0

**Описание:**
Сервис для генерации embeddings кода.

**Реализация:**
```python
# src/codex_aura/search/embeddings.py

from openai import AsyncOpenAI
import tiktoken

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
```

**Критерии приёмки:**
- [ ] Single embedding работает
- [ ] Batch embedding работает
- [ ] Token limit handled
- [ ] Rate limiting

---

### E2-3: Code Chunking Strategy
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Стратегия разбиения кода на чанки для embeddings.

**Реализация:**
```python
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
```

**Критерии приёмки:**
- [ ] Functions извлекаются
- [ ] Classes извлекаются
- [ ] Docstrings включаются
- [ ] Line numbers сохраняются

---

### E2-4: Qdrant Collection Management
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Создание и управление коллекциями в Qdrant.

**Реализация:**
```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

class VectorStore:
    def __init__(self, url: str = "http://localhost:6333"):
        self.client = QdrantClient(url=url)
    
    async def create_collection(self, repo_id: str):
        """Create collection for a repository."""
        self.client.create_collection(
            collection_name=f"repo_{repo_id}",
            vectors_config=VectorParams(
                size=1536,  # text-embedding-3-small
                distance=Distance.COSINE
            )
        )
    
    async def upsert_chunks(
        self, 
        repo_id: str, 
        chunks: list[CodeChunk],
        embeddings: list[list[float]]
    ):
        """Insert or update code chunks."""
        points = [
            PointStruct(
                id=chunk.id,
                vector=embedding,
                payload={
                    "content": chunk.content,
                    "type": chunk.type,
                    "file_path": chunk.file_path,
                    "name": chunk.name,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line
                }
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self.client.upsert(collection_name=f"repo_{repo_id}", points=points)
```

**Критерии приёмки:**
- [ ] Collection создаётся
- [ ] Points вставляются
- [ ] Metadata сохраняется

---

### E2-5: Semantic Search Query
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Поиск релевантного кода по запросу.

**Реализация:**
```python
class SemanticSearch:
    def __init__(self, embedding_service: EmbeddingService, vector_store: VectorStore):
        self.embeddings = embedding_service
        self.vectors = vector_store
    
    async def search(
        self,
        repo_id: str,
        query: str,
        limit: int = 10,
        score_threshold: float = 0.7
    ) -> list[SearchResult]:
        """Search for relevant code chunks."""
        query_embedding = await self.embeddings.embed_code(query)
        
        results = self.vectors.client.search(
            collection_name=f"repo_{repo_id}",
            query_vector=query_embedding,
            limit=limit,
            score_threshold=score_threshold
        )
        
        return [
            SearchResult(
                chunk=CodeChunk(**hit.payload),
                score=hit.score
            )
            for hit in results
        ]
```

**Критерии приёмки:**
- [ ] Поиск работает
- [ ] Score threshold фильтрует
- [ ] Результаты ранжированы

---

### E2-6: Hybrid Search (Graph + Vector)
**Оценка:** 4h | **Приоритет:** P0

**Описание:**
Комбинирование graph traversal и semantic search.

**Реализация:**
```python
class HybridSearch:
    """Combine graph structure with semantic similarity."""
    
    async def search(
        self,
        repo_id: str,
        task: str,
        entry_points: list[str],
        depth: int = 2
    ) -> list[RankedNode]:
        # 1. Get structurally relevant nodes from graph
        graph_nodes = await self.graph.get_dependencies(
            entry_points, depth=depth
        )
        
        # 2. Get semantically relevant chunks
        semantic_results = await self.semantic.search(
            repo_id, task, limit=50
        )
        
        # 3. Combine scores
        node_scores = {}
        for node in graph_nodes:
            node_scores[node.fqn] = {
                "graph_score": 1.0 / (node.distance + 1),  # closer = higher
                "semantic_score": 0.0
            }
        
        for result in semantic_results:
            fqn = result.chunk.fqn
            if fqn in node_scores:
                node_scores[fqn]["semantic_score"] = result.score
            else:
                node_scores[fqn] = {
                    "graph_score": 0.1,  # not in graph, low base
                    "semantic_score": result.score
                }
        
        # 4. Final ranking
        ranked = []
        for fqn, scores in node_scores.items():
            combined = (
                0.4 * scores["graph_score"] + 
                0.6 * scores["semantic_score"]
            )
            ranked.append(RankedNode(fqn=fqn, score=combined))
        
        return sorted(ranked, key=lambda x: x.score, reverse=True)
```

**Критерии приёмки:**
- [ ] Graph + Vector комбинируются
- [ ] Веса настраиваемые
- [ ] Результаты лучше чем отдельно

---

### E2-7: Search API Endpoint
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
REST API для semantic search.

**Endpoint:**
```http
POST /api/v1/search
Content-Type: application/json

{
  "repo_id": "repo_abc123",
  "query": "authentication JWT validation",
  "mode": "hybrid",  // "semantic" | "graph" | "hybrid"
  "limit": 20,
  "filters": {
    "file_types": [".py"],
    "paths": ["src/auth/**"]
  }
}
```

**Response:**
```json
{
  "results": [
    {
      "fqn": "src.auth.jwt.validate_token",
      "type": "function",
      "file_path": "src/auth/jwt.py",
      "score": 0.92,
      "snippet": "def validate_token(token: str) -> Claims:..."
    }
  ],
  "total": 15,
  "search_mode": "hybrid"
}
```

**Критерии приёмки:**
- [ ] API работает
- [ ] Filters применяются
- [ ] Response format консистентный

---

### E2-8: Index Rebuild Command
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
CLI команда для перестройки индекса.

**Команда:**
```bash
codex-aura index rebuild --repo-id repo_abc123 --force
```

**Критерии приёмки:**
- [ ] Полный rebuild работает
- [ ] Progress отображается
- [ ] --force пересоздаёт с нуля

---

## E3: 🔗 Webhook Handler

> ⚠️ **Зависимость от E3-5:** Incremental Graph Update

### E3-1: Webhook Receiver Setup
**Оценка:** 2h | **Приоритет:** P0 | **Зависимость:** ❌

**Описание:**
Базовый endpoint для приёма webhooks.

**Endpoint:**
```python
@app.post("/webhooks/github/{repo_id}")
async def github_webhook(
    repo_id: str,
    request: Request,
    x_hub_signature_256: str = Header(...)
):
    payload = await request.body()
    
    # Verify signature
    if not verify_github_signature(payload, x_hub_signature_256):
        raise HTTPException(401, "Invalid signature")
    
    event = request.headers.get("X-GitHub-Event")
    data = await request.json()
    
    # Queue for processing
    await webhook_queue.enqueue(
        WebhookEvent(repo_id=repo_id, event=event, data=data)
    )
    
    return {"status": "queued"}
```

**Критерии приёмки:**
- [ ] Signature verification работает
- [ ] Events queued

---

### E3-2: GitHub Event Handlers
**Оценка:** 3h | **Приоритет:** P0 | **Зависимость:** ❌

**Описание:**
Обработчики для разных типов событий.

**События:**
```python
class WebhookProcessor:
    handlers = {
        "push": handle_push,
        "pull_request": handle_pull_request,
        "create": handle_branch_create,
        "delete": handle_branch_delete
    }
    
    async def handle_push(self, repo_id: str, data: dict):
        """Handle push event - update graph."""
        commits = data["commits"]
        changed_files = set()
        
        for commit in commits:
            changed_files.update(commit["added"])
            changed_files.update(commit["modified"])
            changed_files.update(commit["removed"])
        
        # Trigger incremental update
        await self.graph_updater.update_files(repo_id, list(changed_files))
```

**Критерии приёмки:**
- [ ] Push events обрабатываются
- [ ] PR events обрабатываются
- [ ] Branch events обрабатываются

---

### E3-3: GitLab Webhook Support
**Оценка:** 2h | **Приоритет:** P1 | **Зависимость:** ❌

**Описание:**
Поддержка GitLab webhooks.

**Критерии приёмки:**
- [ ] GitLab signature verification
- [ ] Event mapping к внутренним типам

---

### E3-4: Webhook Queue (Redis)
**Оценка:** 2h | **Приоритет:** P0 | **Зависимость:** ❌

**Описание:**
Очередь для асинхронной обработки webhooks.

**Реализация:**
```python
from arq import create_pool
from arq.connections import RedisSettings

redis_settings = RedisSettings(host="localhost", port=6379)

async def process_webhook(ctx, event: WebhookEvent):
    processor = WebhookProcessor()
    await processor.process(event)

class WorkerSettings:
    functions = [process_webhook]
    redis_settings = redis_settings
```

**Критерии приёмки:**
- [ ] Queue работает
- [ ] Retry logic есть
- [ ] Dead letter queue для failed