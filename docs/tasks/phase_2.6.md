# Phase 2.6: Улучшения и исправления после Code Review

**Дата создания:** 2025-12-07
**Автор:** Quality Guardian
**Статус:** Backlog
**Приоритет:** P1 (улучшения стабильности)

---

## Контекст

После code review Phase 2.1, Phase 2.2, Phase 2.3, Phase 2.4 и Phase 2.5 выявлены потенциальные улучшения, которые повысят надёжность и производительность системы.

---

## E6-1: Исправить динамическое присвоение labels в Neo4j

**Оценка:** 2h | **Приоритет:** P0 (баг)

**Проблема:**
В `neo4j_client.py:227` используется `SET n:$label`, что не работает в Cypher напрямую — параметры нельзя использовать для labels.

**Файл:** `src/codex_aura/storage/neo4j_client.py:223-227`

**Текущий код:**
```python
await session.run("""
    MERGE (n:Node {fqn: $fqn})
    SET n += $properties
    SET n:$label
""", fqn=fqn, properties=properties, label=label)
```

**Решение:**
Использовать APOC процедуру или динамически формировать запрос:

```python
# Вариант 1: APOC
await session.run("""
    MERGE (n:Node {fqn: $fqn})
    SET n += $properties
    CALL apoc.create.addLabels(n, [$label]) YIELD node
    RETURN node
""", fqn=fqn, properties=properties, label=label)

# Вариант 2: Динамический запрос (менее безопасно)
query = f"""
    MERGE (n:Node {{fqn: $fqn}})
    SET n += $properties
    SET n:{label}
"""
await session.run(query, fqn=fqn, properties=properties)
```

**Критерии приёмки:**
- [x] Labels корректно присваиваются нодам
- [ ] Тесты проходят с реальным Neo4j
- [x] APOC plugin подтверждён в docker-compose

---

## E6-2: Добавить backup/restore скрипты для Neo4j

**Оценка:** 3h | **Приоритет:** P1

**Описание:**
В E1-1 упомянуты backup/restore процедуры, но они не реализованы.

**Реализация:**

```bash
# scripts/neo4j_backup.sh
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec codex-aura-neo4j-1 neo4j-admin database dump neo4j --to-path=/backups/neo4j_${TIMESTAMP}.dump
echo "Backup created: neo4j_${TIMESTAMP}.dump"

# scripts/neo4j_restore.sh
#!/bin/bash
BACKUP_FILE=$1
docker exec codex-aura-neo4j-1 neo4j-admin database load neo4j --from-path=/backups/${BACKUP_FILE} --overwrite-destination
echo "Restored from: ${BACKUP_FILE}"
```

**Критерии приёмки:**
- [x] `scripts/neo4j_backup.sh` создаёт dump
- [x] `scripts/neo4j_restore.sh` восстанавливает из dump
- [x] Документация в README

---

## E6-3: Rate limiting для OpenAI Embedding API

**Оценка:** 2h | **Приоритет:** P1

**Проблема:**
В `search/embeddings.py:51-57` batch embedding не имеет rate limiting, что может привести к 429 ошибкам.

**Файл:** `src/codex_aura/search/embeddings.py`

**Решение:**
```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

class EmbeddingService:
    def __init__(self, model: str = "text-embedding-3-small", rate_limit_rpm: int = 3000):
        self.client = AsyncOpenAI()
        self.model = model
        self.tokenizer = tiktoken.encoding_for_model(model)
        self.rate_limit_rpm = rate_limit_rpm
        self._semaphore = asyncio.Semaphore(10)  # Max concurrent requests

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=60))
    async def embed_code(self, code: str) -> list[float]:
        """Generate embedding with retry logic."""
        async with self._semaphore:
            tokens = self.tokenizer.encode(code)
            if len(tokens) > 8191:
                code = self.tokenizer.decode(tokens[:8191])

            response = await self.client.embeddings.create(
                model=self.model,
                input=code
            )
            return response.data[0].embedding

    async def embed_batch(self, codes: list[str], batch_size: int = 100) -> list[list[float]]:
        """Batch embedding with rate limiting."""
        all_embeddings = []

        for i in range(0, len(codes), batch_size):
            batch = codes[i:i + batch_size]

            async with self._semaphore:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                all_embeddings.extend([item.embedding for item in response.data])

            # Rate limit: wait between batches
            if i + batch_size < len(codes):
                await asyncio.sleep(0.5)

        return all_embeddings
```

**Критерии приёмки:**
- [x] Semaphore ограничивает concurrent requests
- [x] Retry с exponential backoff
- [x] Batch processing с паузами

---

## E6-4: Кеширование результатов HybridSearch

**Оценка:** 2h | **Приоритет:** P2

**Проблема:**
`HybridSearch` выполняет дорогие операции (graph traversal + embedding + vector search) без кеширования.

**Файл:** `src/codex_aura/search/vector_store.py:107-169`

**Решение:**
```python
from functools import lru_cache
import hashlib
import time

class HybridSearch:
    def __init__(self, semantic_search: SemanticSearch, storage=None):
        self.semantic = semantic_search
        self.graph = storage or get_storage()
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    def _cache_key(self, repo_id: str, task: str, entry_points: list[str], depth: int) -> str:
        """Generate cache key from search parameters."""
        key_data = f"{repo_id}:{task}:{sorted(entry_points)}:{depth}"
        return hashlib.md5(key_data.encode()).hexdigest()

    async def search(
        self,
        repo_id: str,
        task: str,
        entry_points: list[str],
        depth: int = 2,
        use_cache: bool = True
    ) -> list[RankedNode]:
        cache_key = self._cache_key(repo_id, task, entry_points, depth)

        # Check cache
        if use_cache and cache_key in self._cache:
            cached_result, cached_time = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_result

        # Execute search (existing logic)
        result = await self._execute_search(repo_id, task, entry_points, depth)

        # Store in cache
        self._cache[cache_key] = (result, time.time())

        return result

    def clear_cache(self, repo_id: str = None):
        """Clear cache, optionally for specific repo."""
        if repo_id:
            keys_to_delete = [k for k in self._cache if k.startswith(repo_id)]
            for k in keys_to_delete:
                del self._cache[k]
        else:
            self._cache.clear()
```

**Критерии приёмки:**
- [x] Результаты кешируются на 5 минут
- [x] Cache key учитывает все параметры
- [x] Метод `clear_cache()` для инвалидации

---

## E6-5: Добавить Redis в docker-compose для webhook queue

**Оценка:** 1h | **Приоритет:** P0

**Проблема:**
В `webhooks/queue.py` используется Redis, но его нет в `docker-compose.yml`.

**Решение:**
```yaml
# docker-compose.yml
services:
  neo4j:
    # ... existing config

  qdrant:
    # ... existing config

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  neo4j_data:
  qdrant_data:
  redis_data:
```

**Критерии приёмки:**
- [x] Redis добавлен в docker-compose.yml
- [x] Healthcheck работает
- [x] Persistence через appendonly

---

## E6-6: Интеграционные тесты для webhook flow

**Оценка:** 4h | **Приоритет:** P1

**Описание:**
Отсутствуют integration tests для полного webhook flow: receive → queue → process → snapshot.

**Реализация:**
```python
# tests/integration/test_webhook_flow.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_github_push_webhook_creates_snapshot(app, redis_client):
    """Test full webhook flow: receive → queue → process → snapshot."""

    # 1. Setup
    repo_id = "test-repo"
    payload = {
        "ref": "refs/heads/main",
        "commits": [
            {
                "id": "abc123def456",
                "message": "Test commit",
                "added": ["src/new_file.py"],
                "modified": ["src/existing.py"],
                "removed": []
            }
        ],
        "repository": {"name": "test-repo", "full_name": "user/test-repo"}
    }

    # 2. Send webhook
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            f"/webhooks/github/{repo_id}",
            json=payload,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": "sha256=<valid_signature>"
            }
        )

    assert response.status_code == 200
    assert response.json()["status"] == "queued"

    # 3. Verify event in queue
    # ... check redis queue

    # 4. Process event
    # ... trigger worker

    # 5. Verify snapshot created
    # ... check storage
```

**Критерии приёмки:**
- [x] Тест GitHub push → snapshot
- [ ] Тест GitLab merge request
- [ ] Тест retry на failure
- [ ] Тест dead letter queue

---

## E6-7: Документация API endpoints

**Оценка:** 2h | **Приоритет:** P2

**Описание:**
Добавить OpenAPI descriptions для всех endpoints из Phase 2.1.

**Файлы:**
- `src/codex_aura/api/server.py` — Search endpoint
- `src/codex_aura/api/webhooks.py` — Webhook endpoints

**Критерии приёмки:**
- [ ] Все endpoints имеют description
- [ ] Request/Response examples в OpenAPI
- [ ] `/docs` показывает полную документацию

---

## Сводка

### Phase 2.1 Improvements

| ID | Задача | Приоритет | Оценка |
|----|--------|-----------|--------|
| E6-1 | Fix Neo4j dynamic labels | P0 | 2h |
| E6-2 | Neo4j backup/restore scripts | P1 | 3h |
| E6-3 | OpenAI rate limiting | P1 | 2h |
| E6-4 | HybridSearch caching | P2 | 2h |
| E6-5 | Add Redis to docker-compose | P0 | 1h |
| E6-6 | Integration tests webhooks | P1 | 4h |
| E6-7 | API documentation | P2 | 2h |

**Подитог Phase 2.1:** 16 часов

### Phase 2.2 Improvements

| ID | Задача | Приоритет | Оценка |
|----|--------|-----------|--------|
| E6-8 | Fix Neo4j dynamic relationship types | P0 | 2h |
| E6-9 | Implement GraphTransaction properly | P0 | 4h |
| E6-10 | Unit tests for sync module | P1 | 4h |
| E6-11 | Concurrent sync protection | P1 | 2h |
| E6-12 | File encoding error handling | P2 | 1h |

**Подитог Phase 2.2:** 13 часов

### Phase 2.3 Improvements

| ID | Задача | Приоритет | Оценка |
|----|--------|-----------|--------|
| E6-13 | Track truncated nodes in BudgetAllocator | P2 | 1h |
| E6-14 | Pass user_id to context pipeline | P1 | 1h |
| E6-15 | Fix bare except in graph expansion | P2 | 0.5h |
| E6-16 | ContextCache use async Redis | P1 | 2h |
| E6-17 | Fix async/sync mismatch in summarizer | P1 | 0.5h |
| E6-18 | Add model validation to TokenCounter | P2 | 1h |

**Подитог Phase 2.3:** 6 часов

### Phase 2.4 Improvements

| ID | Задача | Приоритет | Оценка |
|----|--------|-----------|--------|
| E8-19 | Missing Optional import в stripe_client | P0 | 0.5h |
| E8-20 | Sync Stripe SDK в async методе | P1 | 1h |
| E8-21 | Missing get_current_user в billing.py | P0 | 0.5h |
| E8-22 | Wrong Stripe event name | P1 | 0.5h |
| E8-23 | Missing logger import | P0 | 0.5h |
| E8-24 | SQLiteStorage missing insert_usage_event | P1 | 2h |
| E8-25 | PlanLimits dataclass vs model_dump | P0 | 0.5h |
| E7-* | Dashboard не реализован (отдельный milestone) | P2 | 20h |

**Подитог Phase 2.4 (без Dashboard):** 5.5 часов
**Dashboard (отдельно):** 20 часов

### Phase 2.5 Improvements

| ID | Задача | Приоритет | Оценка |
|----|--------|-----------|--------|
| E9-26 | Snapshot Retrieval API endpoint | P1 | 3h |
| E9-27 | Context Clustering (k-means/HDBSCAN) | P2 | 6h |
| E9-28 | Missing methods в GraphStorage ABC | P1 | 2h |

**Подитог Phase 2.5:** 11 часов

---

**Общая оценка (improvements only):** 51.5 часов
**С Dashboard:** 71.5 часов

---

## Порядок выполнения (рекомендуемый)

### Критические баги (P0) - Блокеры запуска
1. **E6-5** Redis в docker-compose (блокер для webhooks)
2. **E6-1** Fix Neo4j labels (баг)
3. **E6-8** Fix Neo4j dynamic relationship types (баг)
4. **E6-9** Implement GraphTransaction properly (баг)
5. **E8-19** Missing Optional import в stripe_client (syntax error)
6. **E8-21** Missing get_current_user в billing.py (syntax error)
7. **E8-23** Missing logger import (syntax error)
8. **E8-25** PlanLimits dataclass vs model_dump (runtime error)

### Высокий приоритет (P1) - Стабильность
9. **E6-3** Rate limiting (стабильность)
10. **E6-14** Pass user_id to context pipeline (корректность analytics)
11. **E6-16** ContextCache use async Redis (производительность)
12. **E6-17** Fix async/sync mismatch (runtime errors)
13. **E8-20** Sync Stripe SDK в async методе (event loop blocking)
14. **E8-22** Wrong Stripe event name (webhook не работает)
15. **E8-24** SQLiteStorage missing insert_usage_event (usage tracking)
16. **E9-26** Snapshot Retrieval API endpoint (недостающий функционал)
17. **E9-28** Missing methods в GraphStorage ABC (runtime stability)
18. **E6-2** Backup scripts (операционная готовность)
19. **E6-6** Integration tests (качество)
20. **E6-10** Unit tests for sync module (качество)
21. **E6-11** Concurrent sync protection (стабильность)

### Средний приоритет (P2) - Улучшения
22. **E6-4** Caching (производительность)
23. **E6-13** Track truncated nodes (метрики)
24. **E6-15** Fix bare except (код качество)
25. **E6-18** Model validation (DX)
26. **E6-7** Documentation (DX)
27. **E6-12** File encoding error handling (edge cases)
28. **E9-27** Context Clustering (premium feature)

### Отдельный Milestone (P2)
29. **E7-*** Dashboard (20h) - рекомендуется отдельная фаза

---

## Phase 2.2 Improvements

---

## E6-8: Исправить динамическое создание relationship types в Neo4j

**Оценка:** 2h | **Приоритет:** P0 (баг)

**Проблема:**
В `sync/incremental.py:144-148` и `sync/incremental.py:182-188` используется `MERGE (a)-[r:$type]->(b)`, что не работает в Cypher — параметры нельзя использовать для relationship types.

**Файлы:**
- `src/codex_aura/sync/incremental.py:144-148`
- `src/codex_aura/sync/incremental.py:182-188`

**Текущий код:**
```python
await self.session.run("""
    MATCH (a:Node {fqn: $source})
    MATCH (b:Node {fqn: $target})
    MERGE (a)-[r:$type]->(b)
""", source=source_fqn, target=target_fqn, type=edge_type.value)
```

**Решение:**
```python
# Вариант 1: APOC
await self.session.run("""
    MATCH (a:Node {fqn: $source})
    MATCH (b:Node {fqn: $target})
    CALL apoc.merge.relationship(a, $type, {}, {}, b, {}) YIELD rel
    RETURN rel
""", source=source_fqn, target=target_fqn, type=edge_type.value)

# Вариант 2: Динамический запрос с whitelist validation
VALID_EDGE_TYPES = {"IMPORTS", "CALLS", "EXTENDS", "CONTAINS"}
if edge_type.value not in VALID_EDGE_TYPES:
    raise ValueError(f"Invalid edge type: {edge_type.value}")

query = f"""
    MATCH (a:Node {{fqn: $source}})
    MATCH (b:Node {{fqn: $target}})
    MERGE (a)-[r:{edge_type.value}]->(b)
"""
await self.session.run(query, source=source_fqn, target=target_fqn)
```

**Критерии приёмки:**
- [x] Relationship types корректно создаются
- [x] Whitelist validation для безопасности
- [ ] Тесты проходят с реальным Neo4j

---

## E6-9: Реализовать GraphTransaction для storage backends

**Оценка:** 4h | **Приоритет:** P0 (критический функционал)

**Проблема:**
`GraphTransaction` в `sync/incremental.py:36-94` — это placeholder, который ничего не делает. Все методы возвращают заглушки:
- `run()` возвращает `[]`
- `find_node_by_fqn()` возвращает `None`
- `node_exists()` возвращает `False`
- `delete_edges_for_node()` возвращает `0`

Это означает, что **incremental sync фактически не работает** для generic storage!

**Файл:** `src/codex_aura/sync/incremental.py:36-94`

**Решение:**
```python
class GraphTransaction:
    """Transaction context for graph operations."""

    def __init__(self, storage: GraphStorage, repo_id: str):
        self.storage = storage
        self.repo_id = repo_id
        self._pending_nodes: List[Node] = []
        self._pending_edges: List[tuple] = []
        self._deleted_nodes: List[str] = []

    async def upsert_node(self, node: Node) -> None:
        """Queue node for upsert."""
        self._pending_nodes.append(node)

    async def run(self, query: str, **parameters) -> List[Dict[str, Any]]:
        """Execute query against storage backend."""
        # For SQLite: parse query and convert to SQL
        # For PostgreSQL: execute directly
        return await self.storage.execute_query(query, parameters)

    async def find_node_by_fqn(self, fqn: str) -> Optional[Node]:
        """Find node by fully qualified name."""
        return await self.storage.find_node_by_fqn(self.repo_id, fqn)

    async def node_exists(self, fqn: str) -> bool:
        """Check if node exists."""
        node = await self.find_node_by_fqn(fqn)
        return node is not None

    async def delete_edges_for_node(self, fqn: str) -> int:
        """Delete all edges from/to a node."""
        return await self.storage.delete_edges_for_node(self.repo_id, fqn)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Commit: persist all pending operations
            for node in self._pending_nodes:
                await self.storage.upsert_node(self.repo_id, node)
            # ... commit edges
        # On exception: discard pending operations (automatic rollback)
```

**Критерии приёмки:**
- [x] GraphTransaction работает с SQLiteStorage
- [x] GraphTransaction работает с PostgresStorage
- [x] Rollback при исключениях
- [ ] Unit tests для transaction behavior

---

## E6-10: Unit tests для sync module

**Оценка:** 4h | **Приоритет:** P1

**Проблема:**
Модуль `sync/` содержит критическую бизнес-логику, но не имеет unit tests.

**Тесты для создания:**

```python
# tests/unit/test_change_detection.py
@pytest.mark.asyncio
async def test_detect_changes_returns_correct_types():
    """Test change detection correctly identifies A/M/D/R."""

@pytest.mark.asyncio
async def test_detect_renames_with_similarity_threshold():
    """Test rename detection with different thresholds."""

@pytest.mark.asyncio
async def test_get_changed_lines_parses_unified_diff():
    """Test line-level change parsing."""


# tests/unit/test_partial_analysis.py
@pytest.mark.asyncio
async def test_partial_analyzer_identifies_affected_nodes():
    """Test that only changed nodes are re-analyzed."""

@pytest.mark.asyncio
async def test_partial_analyzer_handles_new_file():
    """Test analysis of completely new files."""


# tests/unit/test_edge_recalc.py
@pytest.mark.asyncio
async def test_edge_recalculator_removes_old_edges():
    """Test edge cleanup for deleted nodes."""

@pytest.mark.asyncio
async def test_edge_recalculator_detects_imports():
    """Test IMPORTS edge detection from AST."""


# tests/unit/test_vector_sync.py
@pytest.mark.asyncio
async def test_vector_sync_deletes_old_vectors():
    """Test vector cleanup for deleted nodes."""

@pytest.mark.asyncio
async def test_full_reindex_clears_collection():
    """Test full reindex starts fresh."""
```

**Критерии приёмки:**
- [ ] >80% coverage для sync module
- [ ] Тесты для edge cases (empty files, syntax errors)
- [ ] Mocked storage backends

---

## E6-11: Защита от concurrent sync operations

**Оценка:** 2h | **Приоритет:** P1

**Проблема:**
Нет защиты от параллельного выполнения sync для одного репозитория. Если два webhook приходят одновременно, возможны race conditions.

**Файл:** `src/codex_aura/sync/status.py`

**Решение:**
```python
class SyncStatusTracker:
    async def acquire_sync_lock(self, repo_id: str, timeout: int = 300) -> bool:
        """
        Try to acquire exclusive sync lock for repository.
        Returns True if lock acquired, False if already locked.
        """
        if not self.redis_pool:
            return True  # No Redis = no locking (single instance mode)

        lock_key = f"sync_lock:{repo_id}"

        # Try to set lock with NX (only if not exists) and EX (expiry)
        acquired = await self.redis_pool.set(
            lock_key,
            datetime.utcnow().isoformat(),
            nx=True,
            ex=timeout
        )
        return bool(acquired)

    async def release_sync_lock(self, repo_id: str) -> None:
        """Release sync lock."""
        if self.redis_pool:
            await self.redis_pool.delete(f"sync_lock:{repo_id}")

    async def is_sync_locked(self, repo_id: str) -> bool:
        """Check if sync is currently running."""
        if not self.redis_pool:
            return False
        lock_value = await self.redis_pool.get(f"sync_lock:{repo_id}")
        return lock_value is not None


# Usage in IncrementalGraphUpdater:
async def update(self, repo_id: str, changes: list[FileChange], repo_path: Path):
    status_tracker = SyncStatusTracker(...)

    if not await status_tracker.acquire_sync_lock(repo_id):
        raise ConcurrentSyncError(f"Sync already in progress for {repo_id}")

    try:
        # ... existing sync logic
    finally:
        await status_tracker.release_sync_lock(repo_id)
```

**Критерии приёмки:**
- [x] Redis-based distributed lock
- [x] Lock timeout для dead locks
- [x] Graceful handling когда lock занят

---

## E6-12: Обработка ошибок encoding в file read

**Оценка:** 1h | **Приоритет:** P2

**Проблема:**
В `sync/incremental.py:362` используется `full_path.read_text()` без обработки encoding errors. Binary файлы или файлы с нестандартной кодировкой вызовут исключение.

**Файл:** `src/codex_aura/sync/incremental.py:362`

**Решение:**
```python
async def _update_vector_index(self, ...):
    for file_path in updated_files:
        full_path = repo_path / file_path
        if not full_path.exists():
            continue

        # Skip binary files
        if self._is_binary_file(full_path):
            continue

        try:
            content = full_path.read_text(encoding='utf-8', errors='replace')
        except UnicodeDecodeError:
            # Try with different encodings
            for encoding in ['latin-1', 'cp1252']:
                try:
                    content = full_path.read_text(encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                logger.warning(f"Could not decode {file_path}, skipping")
                continue

        chunks = self.chunker.chunk_file(content, file_path)
        # ...

def _is_binary_file(self, path: Path) -> bool:
    """Check if file is binary."""
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
            return b'\x00' in chunk
    except Exception:
        return True
```

**Критерии приёмки:**
- [x] Binary файлы пропускаются
- [x] Fallback encodings для non-UTF8 файлов
- [x] Logging для skipped файлов

---

## Phase 2.3 Improvements

---

## E6-13: Отслеживание truncated nodes в BudgetAllocator

**Оценка:** 1h | **Приоритет:** P2

**Проблема:**
В `token_budget/allocator.py:102` есть TODO: `nodes_truncated=0,  # TODO: track truncated`. Метрика truncated nodes не отслеживается, что скрывает информацию о потерях контекста.

**Файл:** `src/codex_aura/token_budget/allocator.py:97-105`

**Текущий код:**
```python
return AllocationResult(
    selected_nodes=selected,
    total_tokens=total_tokens,
    budget_used_pct=round(total_tokens / available_budget * 100, 1),
    nodes_included=len(selected),
    nodes_truncated=0,  # TODO: track truncated
    nodes_excluded=len(nodes) - len(selected),
    strategy_used=strategy
)
```

**Решение:**
```python
def allocate(self, ...):
    # ... existing code
    truncated_count = 0

    def track_truncation(nodes: list[RankedNode]) -> tuple[list[RankedNode], int]:
        count = 0
        for node in nodes:
            if hasattr(node, '_was_truncated') and node._was_truncated:
                count += 1
        return nodes, count

    # After each strategy
    selected, truncated_count = track_truncation(selected)

    return AllocationResult(
        selected_nodes=selected,
        total_tokens=total_tokens,
        budget_used_pct=round(total_tokens / available_budget * 100, 1),
        nodes_included=len(selected),
        nodes_truncated=truncated_count,
        nodes_excluded=len(nodes) - len(selected),
        strategy_used=strategy
    )

def _truncate_node(self, node: RankedNode, max_tokens: int) -> RankedNode:
    # ... existing truncation logic
    truncated_node._was_truncated = True  # Mark as truncated
    return truncated_node
```

**Критерии приёмки:**
- [ ] `nodes_truncated` корректно подсчитывается
- [ ] Метрика видна в analytics
- [ ] Unit tests для truncation tracking

---

## E6-14: Передача user_id в context pipeline

**Оценка:** 1h | **Приоритет:** P1

**Проблема:**
В `context/pipeline.py:206,248` используется hardcoded `user_id="system"` вместо реального ID пользователя. Это искажает usage analytics.

**Файлы:**
- `src/codex_aura/context/pipeline.py:206`
- `src/codex_aura/context/pipeline.py:248`

**Решение:**
```python
class UnifiedContextPipeline:
    async def run(
        self,
        repo_id: str,
        task: str,
        max_tokens: int,
        model: str = "gpt-4",
        entry_points: Optional[List[str]] = None,
        format: str = "markdown",
        user_id: Optional[str] = None  # Add user_id parameter
    ) -> ContextResponse:
        # ...
        try:
            usage_storage = UsageStorage()
            await usage_storage.insert_usage_event(UsageEvent(
                user_id=user_id or "anonymous",  # Use passed user_id
                event_type="context_request",
                # ...
            ))


# Also update convenience function:
async def run_context_pipeline(
    repo_id: str,
    task: str,
    max_tokens: int,
    model: str = "gpt-4",
    entry_points: Optional[List[str]] = None,
    format: str = "markdown",
    user_id: Optional[str] = None
) -> ContextResponse:
    # Pass user_id to pipeline
```

**Критерии приёмки:**
- [ ] user_id передаётся через API → Pipeline
- [ ] UsageEvent содержит реальный user_id
- [ ] "anonymous" для unauthenticated requests

---

## E6-15: Bare except в graph expansion

**Оценка:** 0.5h | **Приоритет:** P2

**Проблема:**
В `context/pipeline.py:391-393` используется bare `except:` без типа исключения, что может маскировать критические ошибки.

**Файл:** `src/codex_aura/context/pipeline.py:391-393`

**Текущий код:**
```python
for candidate in candidates:
    try:
        nodes = await self.graph.get_nodes_in_file(repo_id, candidate)
        if nodes:
            entry_points.extend([n.fqn for n in nodes])
    except:  # Bare except!
        continue
```

**Решение:**
```python
for candidate in candidates:
    try:
        nodes = await self.graph.get_nodes_in_file(repo_id, candidate)
        if nodes:
            entry_points.extend([n.fqn for n in nodes])
    except (KeyError, FileNotFoundError, ValueError) as e:
        logger.debug(f"Entry point candidate {candidate} not found: {e}")
        continue
    except Exception as e:
        logger.warning(f"Unexpected error resolving entry point {candidate}: {e}")
        continue
```

**Критерии приёмки:**
- [ ] Specific exception handling
- [ ] Logging для диагностики
- [ ] Не маскируются critical errors (SystemExit, KeyboardInterrupt)

---

## E6-16: Cache для ContextCache использует sync Redis API

**Оценка:** 2h | **Приоритет:** P1

**Проблема:**
В `context/cache.py:33-54` методы помечены как `async`, но используют sync Redis client (`self.redis.get()`, `self.redis.setex()`). Это блокирует event loop.

**Файл:** `src/codex_aura/context/cache.py`

**Текущий код:**
```python
class ContextCache:
    def __init__(self, redis: Redis, ttl: int = 300):
        self.redis = redis  # Sync Redis client!
        self.ttl = ttl

    async def get(...):
        cached = await self.redis.get(key)  # Doesn't work with sync client!
```

**Решение:**
```python
from redis.asyncio import Redis as AsyncRedis

class ContextCache:
    def __init__(self, redis: AsyncRedis, ttl: int = 300):
        """
        Args:
            redis: Async Redis client (redis.asyncio.Redis)
            ttl: Cache TTL in seconds
        """
        self.redis = redis
        self.ttl = ttl

    async def get(
        self,
        request: "ContextRequest",
        graph_version: str
    ) -> "ContextResponse | None":
        key = self._cache_key(request, graph_version)
        cached = await self.redis.get(key)  # Now properly async

        if cached:
            return ContextResponse.model_validate_json(cached)
        return None

    async def set(
        self,
        request: "ContextRequest",
        graph_version: str,
        response: "ContextResponse"
    ):
        key = self._cache_key(request, graph_version)
        await self.redis.setex(key, self.ttl, response.model_dump_json())
```

**Критерии приёмки:**
- [ ] Использует `redis.asyncio` вместо sync `redis`
- [ ] Все методы действительно async
- [ ] Type hints корректны

---

## E6-17: ContentSummarizer.summarize_node возвращает неправильный тип

**Оценка:** 0.5h | **Приоритет:** P1

**Проблема:**
В `token_budget/summarizer.py:32-62` метод `summarize_node` возвращает `str`, но в `context/pipeline.py:344-348` ожидается, что он вернёт content для Node. При await вызове sync функции возникнет ошибка.

**Файлы:**
- `src/codex_aura/token_budget/summarizer.py:32`
- `src/codex_aura/context/pipeline.py:344`

**Текущий код в pipeline.py:**
```python
summarized_content = await self.summarizer.summarize_node(  # await sync function!
    node=node,
    max_tokens=self.config.max_summary_tokens,
    model=model
)
```

**Решение:**
```python
# In summarizer.py - make synchronous call explicit
def summarize_node(self, node: Node, target_tokens: int, ...) -> str:
    """Synchronous summarization."""
    # ... existing code

# In pipeline.py - don't await sync function
if token_count > self.config.max_summary_tokens:
    # Call without await - it's synchronous
    summarized_content = self.summarizer.summarize_node(
        node=node,
        target_tokens=self.config.max_summary_tokens,
        model=model
    )
```

**Критерии приёмки:**
- [ ] Sync/async вызовы соответствуют сигнатурам
- [ ] Нет `await` на sync функциях
- [ ] Тесты проходят без RuntimeWarning

---

## E6-18: Отсутствует валидация model name в TokenCounter

**Оценка:** 1h | **Приоритет:** P2

**Проблема:**
`TokenCounter.count()` принимает любой `ModelName`, но если передан неизвестный model, используется fallback без warning. Это может привести к неточному подсчёту токенов.

**Файл:** `src/codex_aura/token_budget/counter.py:43-46`

**Решение:**
```python
import logging

logger = logging.getLogger(__name__)

class TokenCounter:
    SUPPORTED_MODELS = set(ENCODINGS.keys())

    def count(self, text: str, model: ModelName = "gpt-4") -> int:
        if model not in self.SUPPORTED_MODELS:
            logger.warning(
                f"Unknown model '{model}', using cl100k_base encoding. "
                f"Supported: {self.SUPPORTED_MODELS}"
            )

        # ... existing code
```

**Критерии приёмки:**
- [ ] Warning при unknown model
- [ ] SUPPORTED_MODELS константа для валидации
- [ ] Документация в docstring

---

## Phase 2.4 Improvements

---

## E8-19: Missing Optional import в stripe_client.py

**Оценка:** 0.5h | **Приоритет:** P0 (синтаксическая ошибка)

**Проблема:**
В `billing/stripe_client.py:69` используется `Optional[dict]` как return type, но `Optional` не импортирован.

**Файл:** `src/codex_aura/billing/stripe_client.py:69`

**Текущий код:**
```python
async def get_subscription_by_customer(self, customer_id: str) -> Optional[dict]:  # Optional not imported!
```

**Решение:**
```python
# В начале файла добавить:
from typing import Optional
```

**Критерии приёмки:**
- [ ] `Optional` импортирован
- [ ] Код проходит mypy/pyright

---

## E8-20: Sync Stripe SDK в async методе

**Оценка:** 1h | **Приоритет:** P1

**Проблема:**
`stripe_client.py:74` метод `construct_event` помечен как async, но вызывает sync Stripe SDK методы. Это блокирует event loop.

**Файл:** `src/codex_aura/billing/stripe_client.py:74`

**Текущий код:**
```python
async def construct_event(self, payload: bytes, sig_header: str, endpoint_secret: str) -> stripe.Event:
    """Construct Stripe event from webhook payload."""
    return stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)  # Sync call!
```

**Решение:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

class StripeClient:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=3)

    async def construct_event(self, payload: bytes, sig_header: str, endpoint_secret: str) -> stripe.Event:
        """Construct Stripe event from webhook payload (non-blocking)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            stripe.Webhook.construct_event,
            payload, sig_header, endpoint_secret
        )
```

**Критерии приёмки:**
- [ ] Все Stripe SDK вызовы через executor
- [ ] Event loop не блокируется
- [ ] ThreadPool cleanup при shutdown

---

## E8-21: Missing get_current_user в billing.py

**Оценка:** 0.5h | **Приоритет:** P0 (синтаксическая ошибка)

**Проблема:**
В `api/billing.py:35` используется `get_current_user`, который не импортирован и не определён.

**Файл:** `src/codex_aura/api/billing.py:35`

**Текущий код:**
```python
async def create_checkout_session(
    request: CheckoutRequest,
    user: User = Depends(get_current_user)  # get_current_user not defined!
):
```

**Решение:**
```python
# Использовать уже существующий require_auth middleware:
from ..api.middleware.auth import require_auth

@router.post("/checkout")
async def create_checkout_session(
    request: CheckoutRequest,
    current_user = Depends(require_auth)  # Use require_auth
):
    user = current_user  # Уже авторизованный пользователь
```

**Критерии приёмки:**
- [ ] Все endpoints используют существующий auth middleware
- [ ] Консистентный naming (current_user везде)

---

## E8-22: Неправильное название Stripe event в webhook handler

**Оценка:** 0.5h | **Приоритет:** P1

**Проблема:**
В `api/billing.py:111` используется `invoice.payment_succeeded`, но в Stripe API это событие называется `invoice.paid`.

**Файл:** `src/codex_aura/api/billing.py:111`

**Текущий код:**
```python
if event.type == "invoice.payment_succeeded":  # Неправильное название!
    await handler.handle_invoice_paid(event.data.object)
```

**Решение:**
```python
if event.type == "invoice.paid":  # Правильное название
    await handler.handle_invoice_paid(event.data.object)
```

**Критерии приёмки:**
- [ ] Все Stripe event names соответствуют документации
- [ ] Тесты с mock Stripe events

---

## E8-23: Missing logger import в billing.py

**Оценка:** 0.5h | **Приоритет:** P0 (синтаксическая ошибка)

**Проблема:**
В `api/billing.py:121` используется `logger.error()`, но logger не импортирован.

**Файл:** `src/codex_aura/api/billing.py:121`

**Текущий код:**
```python
except Exception as e:
    logger.error(f"Webhook error: {e}")  # logger not imported!
```

**Решение:**
```python
# В начале файла:
import logging

logger = logging.getLogger(__name__)
```

**Критерии приёмки:**
- [ ] Logger импортирован во всех модулях
- [ ] Консистентный logging format

---

## E8-24: SQLiteStorage не имеет метода insert_usage_event

**Оценка:** 2h | **Приоритет:** P1

**Проблема:**
В `billing/usage.py:40` вызывается `self.db.insert_usage_event()`, но `SQLiteStorage` не имеет этого метода.

**Файл:** `src/codex_aura/billing/usage.py:40`

**Текущий код:**
```python
class UsageTracker:
    def __init__(self, redis: Redis, db: SQLiteStorage):  # SQLiteStorage doesn't have insert_usage_event!
        self.redis = redis
        self.db = db

    async def record_request(self, ...):
        await self.db.insert_usage_event(...)  # Method doesn't exist!
```

**Решение:**
```python
# Вариант 1: Добавить метод в SQLiteStorage
# src/codex_aura/storage/sqlite.py
class SQLiteStorage:
    def insert_usage_event(self, user_id: str, endpoint: str, tokens_used: int, timestamp: datetime):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO usage_events (user_id, endpoint, tokens_used, timestamp)
                VALUES (?, ?, ?, ?)
            """, (user_id, endpoint, tokens_used, timestamp))

# Вариант 2: Использовать UsageStorage вместо SQLiteStorage
from ..storage.usage_storage import UsageStorage

class UsageTracker:
    def __init__(self, redis: Redis, usage_storage: UsageStorage):
        self.redis = redis
        self.usage_storage = usage_storage
```

**Критерии приёмки:**
- [ ] UsageTracker использует правильный storage class
- [ ] usage_events таблица создаётся в миграциях
- [ ] Тесты для persistent storage

---

## E8-25: PlanLimits dataclass не имеет model_dump

**Оценка:** 0.5h | **Приоритет:** P0 (runtime error)

**Проблема:**
В `api/billing.py:26` вызывается `limits.model_dump()`, но `PlanLimits` — это dataclass, а не Pydantic model.

**Файл:** `src/codex_aura/api/billing.py:26`

**Текущий код:**
```python
@router.get("/plans")
async def get_plans():
    return {
        tier.value: {
            "limits": limits.model_dump(),  # AttributeError: dataclass has no model_dump!
```

**Решение:**
```python
# Вариант 1: Использовать asdict для dataclass
from dataclasses import asdict

@router.get("/plans")
async def get_plans():
    return {
        tier.value: {
            "limits": asdict(limits),  # Правильно для dataclass
            "price_id": STRIPE_PRICES.get(tier)
        }
        for tier, limits in PLAN_LIMITS.items()
    }

# Вариант 2: Конвертировать PlanLimits в Pydantic model
# plans.py
from pydantic import BaseModel

class PlanLimits(BaseModel):
    repos: int
    requests_per_day: int
    # ...
```

**Критерии приёмки:**
- [ ] Сериализация работает без ошибок
- [ ] API возвращает корректный JSON

---

## Phase 2.5 Improvements

---

## E9-26: Отсутствует Snapshot Retrieval API endpoint

**Оценка:** 3h | **Приоритет:** P1 (недостающий функционал)

**Проблема:**
В Phase 2.5 PF2-3 требуется endpoint `GET /repos/{id}/graph/{sha}` для получения графа из snapshot, но он не реализован. SnapshotService и PostgresSnapshotStorage существуют, но API endpoint отсутствует.

**Файлы:**
- `src/codex_aura/snapshot/snapshot_service.py` — существует
- `src/codex_aura/storage/postgres_snapshots.py` — существует
- API endpoint — **отсутствует**

**Решение:**
```python
# src/codex_aura/api/snapshots.py
from fastapi import APIRouter, HTTPException, Path
from typing import Optional
from ..snapshot.snapshot_service import SnapshotService
from ..storage.postgres_snapshots import PostgresSnapshotStorage

router = APIRouter(prefix="/api/v1/repos", tags=["snapshots"])

class SnapshotGraphResponse(BaseModel):
    """Response model for snapshot graph."""
    snapshot_id: str
    repo_id: str
    sha: str
    created_at: datetime
    nodes: List[NodeSummary]
    edges: List[EdgeSummary]
    node_count: int
    edge_count: int

@router.get("/{repo_id}/graph/{sha}", response_model=SnapshotGraphResponse)
async def get_graph_snapshot(
    repo_id: str = Path(..., description="Repository identifier"),
    sha: str = Path(..., description="Git SHA of the snapshot")
):
    """
    Get graph for a specific repository snapshot.

    Returns the full graph (nodes and edges) from a historical snapshot.
    """
    try:
        storage = PostgresSnapshotStorage()

        # Find snapshot by repo_id and sha
        snapshots = await storage.get_snapshots_for_repo(repo_id)
        snapshot = next((s for s in snapshots if s.sha == sha), None)

        if not snapshot:
            raise HTTPException(status_code=404, detail=f"Snapshot not found for SHA: {sha}")

        # Get nodes and edges
        nodes = await storage.get_snapshot_nodes(snapshot.snapshot_id)
        edges = await storage.get_snapshot_edges(snapshot.snapshot_id)

        return SnapshotGraphResponse(
            snapshot_id=snapshot.snapshot_id,
            repo_id=snapshot.repo_id,
            sha=snapshot.sha,
            created_at=snapshot.created_at,
            nodes=[NodeSummary(**n) for n in nodes],
            edges=[EdgeSummary(**e) for e in edges],
            node_count=len(nodes),
            edge_count=len(edges)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve snapshot: {str(e)}")

@router.get("/{repo_id}/snapshots", response_model=List[SnapshotMetadata])
async def list_repo_snapshots(repo_id: str = Path(..., description="Repository identifier")):
    """List all available snapshots for a repository."""
    storage = PostgresSnapshotStorage()
    snapshots = await storage.get_snapshots_for_repo(repo_id)
    return [SnapshotMetadata(
        snapshot_id=s.snapshot_id,
        sha=s.sha,
        created_at=s.created_at,
        node_count=s.node_count,
        edge_count=s.edge_count
    ) for s in snapshots]
```

**Критерии приёмки:**
- [ ] `GET /repos/{id}/graph/{sha}` возвращает полный граф
- [ ] `GET /repos/{id}/snapshots` возвращает список доступных snapshots
- [ ] 404 если snapshot не найден
- [ ] Интеграция с существующим PostgresSnapshotStorage

---

## E9-27: Context Clustering не реализован

**Оценка:** 6h | **Приоритет:** P2 (premium feature)

**Проблема:**
В Phase 2.5 PF2-11 требуется группировка nodes в кластеры по embedding similarity (k-means или HDBSCAN), но функционал не реализован.

**Файлы:**
- `src/codex_aura/context/` — clustering отсутствует

**Решение:**
```python
# src/codex_aura/context/clustering.py
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from sklearn.cluster import KMeans, HDBSCAN
from sklearn.preprocessing import normalize

from ..models.node import Node
from ..search.embeddings import EmbeddingService

@dataclass
class NodeCluster:
    """A cluster of semantically related nodes."""
    cluster_id: int
    label: str  # Auto-generated or inferred label
    nodes: List[Node]
    centroid: Optional[np.ndarray] = None
    coherence_score: float = 0.0  # How tightly clustered

@dataclass
class ClusteringResult:
    """Result of clustering operation."""
    clusters: List[NodeCluster]
    noise_nodes: List[Node]  # Nodes not assigned to any cluster (HDBSCAN)
    algorithm: str
    num_clusters: int
    silhouette_score: float

class ContextClusterer:
    """Groups nodes into semantic clusters based on embedding similarity."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        algorithm: str = "hdbscan",  # "kmeans" or "hdbscan"
        min_cluster_size: int = 3,
        n_clusters: int = 5  # For kmeans only
    ):
        self.embeddings = embedding_service
        self.algorithm = algorithm
        self.min_cluster_size = min_cluster_size
        self.n_clusters = n_clusters

    async def cluster_nodes(
        self,
        nodes: List[Node],
        precomputed_embeddings: Optional[Dict[str, np.ndarray]] = None
    ) -> ClusteringResult:
        """
        Cluster nodes by embedding similarity.

        Args:
            nodes: List of nodes to cluster
            precomputed_embeddings: Optional dict of node_id -> embedding

        Returns:
            ClusteringResult with clusters and metadata
        """
        if len(nodes) < self.min_cluster_size:
            # Too few nodes to cluster
            return ClusteringResult(
                clusters=[NodeCluster(0, "all", nodes)],
                noise_nodes=[],
                algorithm=self.algorithm,
                num_clusters=1,
                silhouette_score=0.0
            )

        # Get embeddings
        embeddings = await self._get_embeddings(nodes, precomputed_embeddings)

        # Normalize embeddings for better clustering
        embeddings_matrix = normalize(np.array(embeddings))

        # Perform clustering
        if self.algorithm == "hdbscan":
            return self._cluster_hdbscan(nodes, embeddings_matrix)
        else:
            return self._cluster_kmeans(nodes, embeddings_matrix)

    def _cluster_hdbscan(
        self,
        nodes: List[Node],
        embeddings: np.ndarray
    ) -> ClusteringResult:
        """Cluster using HDBSCAN (density-based, automatic k)."""
        clusterer = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            min_samples=2,
            metric='euclidean'
        )
        labels = clusterer.fit_predict(embeddings)

        # Group nodes by cluster
        clusters = {}
        noise_nodes = []

        for node, label, emb in zip(nodes, labels, embeddings):
            if label == -1:
                noise_nodes.append(node)
            else:
                if label not in clusters:
                    clusters[label] = {"nodes": [], "embeddings": []}
                clusters[label]["nodes"].append(node)
                clusters[label]["embeddings"].append(emb)

        # Create NodeCluster objects with centroids
        node_clusters = []
        for label, data in clusters.items():
            centroid = np.mean(data["embeddings"], axis=0)
            coherence = self._calculate_coherence(data["embeddings"], centroid)
            cluster_label = self._generate_cluster_label(data["nodes"])

            node_clusters.append(NodeCluster(
                cluster_id=label,
                label=cluster_label,
                nodes=data["nodes"],
                centroid=centroid,
                coherence_score=coherence
            ))

        silhouette = self._calculate_silhouette(embeddings, labels) if len(clusters) > 1 else 0.0

        return ClusteringResult(
            clusters=node_clusters,
            noise_nodes=noise_nodes,
            algorithm="hdbscan",
            num_clusters=len(clusters),
            silhouette_score=silhouette
        )

    def _cluster_kmeans(
        self,
        nodes: List[Node],
        embeddings: np.ndarray
    ) -> ClusteringResult:
        """Cluster using K-Means (fixed k)."""
        # Adjust n_clusters if we have fewer nodes
        k = min(self.n_clusters, len(nodes))

        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(embeddings)

        # Group nodes by cluster
        clusters = {i: {"nodes": [], "embeddings": []} for i in range(k)}

        for node, label, emb in zip(nodes, labels, embeddings):
            clusters[label]["nodes"].append(node)
            clusters[label]["embeddings"].append(emb)

        # Create NodeCluster objects
        node_clusters = []
        for label, data in clusters.items():
            if data["nodes"]:  # Skip empty clusters
                centroid = kmeans.cluster_centers_[label]
                coherence = self._calculate_coherence(data["embeddings"], centroid)
                cluster_label = self._generate_cluster_label(data["nodes"])

                node_clusters.append(NodeCluster(
                    cluster_id=label,
                    label=cluster_label,
                    nodes=data["nodes"],
                    centroid=centroid,
                    coherence_score=coherence
                ))

        silhouette = self._calculate_silhouette(embeddings, labels) if k > 1 else 0.0

        return ClusteringResult(
            clusters=node_clusters,
            noise_nodes=[],
            algorithm="kmeans",
            num_clusters=len(node_clusters),
            silhouette_score=silhouette
        )

    def _generate_cluster_label(self, nodes: List[Node]) -> str:
        """Generate a descriptive label for a cluster based on its nodes."""
        # Use most common path prefix or node type
        if not nodes:
            return "empty"

        # Extract common path patterns
        paths = [n.path for n in nodes if n.path]
        if paths:
            common_prefix = os.path.commonpath(paths) if len(paths) > 1 else paths[0]
            return f"cluster_{common_prefix.replace('/', '_')[:30]}"

        # Fallback to node types
        types = [n.type for n in nodes]
        most_common = max(set(types), key=types.count)
        return f"cluster_{most_common}"

    async def _get_embeddings(
        self,
        nodes: List[Node],
        precomputed: Optional[Dict[str, np.ndarray]]
    ) -> List[np.ndarray]:
        """Get embeddings for nodes, using precomputed when available."""
        embeddings = []
        to_compute = []

        for node in nodes:
            if precomputed and node.id in precomputed:
                embeddings.append(precomputed[node.id])
            else:
                to_compute.append(node)
                embeddings.append(None)  # Placeholder

        if to_compute:
            # Compute missing embeddings
            texts = [n.content or n.name for n in to_compute]
            computed = await self.embeddings.embed_batch(texts)

            # Fill in placeholders
            computed_iter = iter(computed)
            for i, emb in enumerate(embeddings):
                if emb is None:
                    embeddings[i] = np.array(next(computed_iter))

        return embeddings

    def _calculate_coherence(self, embeddings: List, centroid: np.ndarray) -> float:
        """Calculate cluster coherence (inverse of average distance to centroid)."""
        if not embeddings:
            return 0.0
        distances = [np.linalg.norm(np.array(e) - centroid) for e in embeddings]
        avg_distance = np.mean(distances)
        return 1.0 / (1.0 + avg_distance)  # Higher = more coherent

    def _calculate_silhouette(self, embeddings: np.ndarray, labels: np.ndarray) -> float:
        """Calculate silhouette score for clustering quality."""
        from sklearn.metrics import silhouette_score
        try:
            return float(silhouette_score(embeddings, labels))
        except:
            return 0.0
```

**Критерии приёмки:**
- [ ] ContextClusterer с поддержкой K-Means и HDBSCAN
- [ ] Автоматическая генерация cluster labels
- [ ] Coherence и silhouette метрики
- [ ] Интеграция с pipeline (опционально при запросе)
- [ ] Unit tests для clustering logic

---

## E9-28: Улучшить обработку отсутствующих методов в storage backends

**Оценка:** 2h | **Приоритет:** P1 (runtime stability)

**Проблема:**
В `context/pipeline.py:288-291` вызываются методы `self.graph.get_node()`, `get_nodes_in_file()`, `get_node_at_line()`, `find_nodes_by_glob()`, которые не определены в базовом классе `GraphStorage`.

**Файлы:**
- `src/codex_aura/context/pipeline.py:288-291, 389-414`
- `src/codex_aura/storage/storage_abstraction.py`

**Текущий код в pipeline.py:**
```python
entry_node = await self.graph.get_node(repo_id, fqn)  # Метод не существует!
nodes = await self.graph.get_nodes_in_file(repo_id, candidate)  # Метод не существует!
```

**Решение:**
```python
# storage_abstraction.py - добавить абстрактные методы
class GraphStorage(ABC):
    # ... existing methods

    @abstractmethod
    async def get_node(self, repo_id: str, fqn: str) -> Optional[Node]:
        """Get node by FQN."""
        pass

    @abstractmethod
    async def get_nodes_in_file(self, repo_id: str, file_path: str) -> List[Node]:
        """Get all nodes in a file."""
        pass

    @abstractmethod
    async def get_node_at_line(self, repo_id: str, file_path: str, line: int) -> Optional[Node]:
        """Get node at specific line."""
        pass

    @abstractmethod
    async def find_nodes_by_glob(self, repo_id: str, pattern: str) -> List[Node]:
        """Find nodes matching glob pattern."""
        pass

# Implement in each backend: SQLiteStorageBackend, Neo4jStorageBackend, PostgresStorageBackend
```

**Критерии приёмки:**
- [ ] Методы добавлены в GraphStorage ABC
- [ ] Реализованы во всех storage backends
- [ ] Pipeline использует только определённые методы
- [ ] Unit tests для новых методов

---

## E7-*: Dashboard не реализован

**Оценка:** 20h | **Приоритет:** P2 (отдельная milestone)

**Проблема:**
Директория `dashboard/` не существует. Все 10 задач E7-1 до E7-10 не начаты:
- E7-1: Tech Stack & Project Setup
- E7-2: Authentication (Clerk)
- E7-3: Repository List View
- E7-4: Graph Visualization
- E7-5: Node Details Panel
- E7-6: Search Interface
- E7-7: Hotspot Map
- E7-8: Code Authorship
- E7-9: API Usage Stats
- E7-10: Settings & Billing Portal

**Рекомендация:**
Dashboard — это отдельный frontend проект. Рекомендуется создать Phase 2.5 специально для Dashboard implementation вместо добавления в Phase 2.6 improvements.

**Критерии приёмки:**
- [ ] Создан phase_2.5.md для Dashboard
- [ ] Dashboard выделен в отдельный milestone
