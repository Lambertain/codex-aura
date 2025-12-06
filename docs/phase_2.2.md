# 📋 Phase 2.2: Incremental Sync & Webhooks

## E3-5: Incremental Graph Update
**Оценка:** 4h | **Приоритет:** P0 | **Зависимости:** E3-4

### Описание
Обновление графа только для изменённых файлов без полного rebuild. Это критично для production — полный rebuild на 10K файлов занимает минуты, incremental update должен быть < 5 сек.

### Реализация

```python
# src/codex_aura/sync/incremental.py

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import asyncio

class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"

@dataclass
class FileChange:
    path: str
    change_type: ChangeType
    old_path: str | None = None  # для renamed

@dataclass
class IncrementalUpdateResult:
    nodes_added: int
    nodes_updated: int
    nodes_deleted: int
    edges_recalculated: int
    duration_ms: int
    errors: list[str]

class IncrementalGraphUpdater:
    """Updates graph incrementally based on file changes."""
    
    def __init__(
        self,
        graph_storage: GraphStorage,
        analyzer: CodeAnalyzer,
        vector_store: VectorStore,
        embedding_service: EmbeddingService
    ):
        self.storage = graph_storage
        self.analyzer = analyzer
        self.vectors = vector_store
        self.embeddings = embedding_service
    
    async def update(
        self,
        repo_id: str,
        changes: list[FileChange],
        repo_path: Path
    ) -> IncrementalUpdateResult:
        """
        Apply incremental updates to graph based on file changes.
        
        Strategy:
        1. Delete nodes for removed/modified files
        2. Re-analyze added/modified files
        3. Recalculate edges for affected nodes
        4. Update vector index for changed chunks
        """
        start_time = asyncio.get_event_loop().time()
        result = IncrementalUpdateResult(
            nodes_added=0, nodes_updated=0, nodes_deleted=0,
            edges_recalculated=0, duration_ms=0, errors=[]
        )
        
        try:
            # Group changes by type for efficient processing
            deleted_files = [c.path for c in changes if c.change_type == ChangeType.DELETED]
            modified_files = [c.path for c in changes if c.change_type == ChangeType.MODIFIED]
            added_files = [c.path for c in changes if c.change_type == ChangeType.ADDED]
            renamed_files = [c for c in changes if c.change_type == ChangeType.RENAMED]
            
            async with self.storage.transaction(repo_id) as txn:
                # Step 1: Handle deletions
                for file_path in deleted_files:
                    deleted_count = await self._delete_file_nodes(txn, file_path)
                    result.nodes_deleted += deleted_count
                
                # Step 2: Handle renames (delete old, analyze new)
                for change in renamed_files:
                    await self._delete_file_nodes(txn, change.old_path)
                    added_files.append(change.path)
                
                # Step 3: Handle modifications (delete old nodes, re-analyze)
                for file_path in modified_files:
                    await self._delete_file_nodes(txn, file_path)
                
                # Step 4: Analyze new/modified files
                files_to_analyze = added_files + modified_files
                for file_path in files_to_analyze:
                    full_path = repo_path / file_path
                    if not full_path.exists():
                        result.errors.append(f"File not found: {file_path}")
                        continue
                    
                    try:
                        nodes = await self.analyzer.analyze_file(full_path)
                        for node in nodes:
                            await txn.upsert_node(node)
                            result.nodes_added += 1
                    except Exception as e:
                        result.errors.append(f"Analysis failed for {file_path}: {e}")
                
                # Step 5: Recalculate edges for affected files
                all_affected = set(deleted_files + modified_files + added_files)
                edges_count = await self._recalculate_edges(txn, all_affected)
                result.edges_recalculated = edges_count
                
                # Step 6: Update vector index
                await self._update_vector_index(
                    repo_id, 
                    files_to_analyze,
                    deleted_files,
                    repo_path
                )
        
        except Exception as e:
            result.errors.append(f"Update failed: {e}")
            raise
        
        end_time = asyncio.get_event_loop().time()
        result.duration_ms = int((end_time - start_time) * 1000)
        
        return result
    
    async def _delete_file_nodes(self, txn, file_path: str) -> int:
        """Delete all nodes belonging to a file."""
        query = """
        MATCH (n:Node {file_path: $file_path})
        WITH n, count(n) as cnt
        DETACH DELETE n
        RETURN cnt
        """
        result = await txn.run(query, file_path=file_path)
        record = await result.single()
        return record["cnt"] if record else 0
    
    async def _recalculate_edges(
        self, 
        txn, 
        affected_files: set[str]
    ) -> int:
        """
        Recalculate edges for nodes in affected files.
        
        This is the tricky part:
        - IMPORTS edges: re-resolve import statements
        - CALLS edges: re-analyze function calls
        - EXTENDS edges: re-check inheritance
        """
        edges_created = 0
        
        # Get all nodes from affected files
        query = """
        MATCH (n:Node)
        WHERE n.file_path IN $files
        RETURN n
        """
        result = await txn.run(query, files=list(affected_files))
        affected_nodes = [record["n"] async for record in result]
        
        for node in affected_nodes:
            # Re-resolve references for this node
            references = await self.analyzer.resolve_references(node)
            
            for ref in references:
                # Find target node
                target = await txn.find_node_by_fqn(ref.target_fqn)
                if target:
                    await txn.create_edge(
                        source_fqn=node["fqn"],
                        target_fqn=target["fqn"],
                        edge_type=ref.edge_type
                    )
                    edges_created += 1
        
        return edges_created
    
    async def _update_vector_index(
        self,
        repo_id: str,
        updated_files: list[str],
        deleted_files: list[str],
        repo_path: Path
    ):
        """Update Qdrant index for changed files."""
        collection = f"repo_{repo_id}"
        
        # Delete vectors for removed/modified files
        all_removed = set(updated_files + deleted_files)
        if all_removed:
            await self.vectors.delete_by_filter(
                collection,
                {"file_path": {"$in": list(all_removed)}}
            )
        
        # Re-embed updated files
        for file_path in updated_files:
            full_path = repo_path / file_path
            if not full_path.exists():
                continue
            
            content = full_path.read_text()
            chunks = self.chunker.chunk_file(content, file_path)
            
            if chunks:
                embeddings = await self.embeddings.embed_batch(
                    [c.content for c in chunks]
                )
                await self.vectors.upsert_chunks(
                    collection, chunks, embeddings
                )
```

### Оптимизации для production

```python
class BatchIncrementalUpdater(IncrementalGraphUpdater):
    """Optimized updater for large changesets."""
    
    async def update_batch(
        self,
        repo_id: str,
        changes: list[FileChange],
        repo_path: Path,
        batch_size: int = 50
    ) -> IncrementalUpdateResult:
        """Process changes in batches for memory efficiency."""
        
        total_result = IncrementalUpdateResult(...)
        
        # Process in batches
        for i in range(0, len(changes), batch_size):
            batch = changes[i:i + batch_size]
            batch_result = await self.update(repo_id, batch, repo_path)
            
            # Aggregate results
            total_result.nodes_added += batch_result.nodes_added
            total_result.nodes_deleted += batch_result.nodes_deleted
            total_result.edges_recalculated += batch_result.edges_recalculated
            total_result.errors.extend(batch_result.errors)
        
        return total_result
```

### Критерии приёмки
- [ ] Incremental update < 5 сек для типичного commit (1-10 файлов)
- [ ] Deleted files удаляют все связанные nodes и edges
- [ ] Modified files корректно обновляют nodes
- [ ] Vector index синхронизирован с графом
- [ ] Transaction rollback при ошибках
- [ ] Batch processing для больших changesets
- [ ] Логирование всех операций

### Тесты

```python
# tests/test_incremental_update.py

import pytest
from codex_aura.sync.incremental import IncrementalGraphUpdater, FileChange, ChangeType

@pytest.fixture
async def updater(graph_storage, analyzer, vector_store, embeddings):
    return IncrementalGraphUpdater(graph_storage, analyzer, vector_store, embeddings)

async def test_delete_file_removes_nodes(updater, sample_repo):
    """Deleting a file should remove all its nodes."""
    # Setup: analyze repo first
    await updater.storage.save_graph(sample_repo.graph)
    
    # Act: delete a file
    changes = [FileChange(path="src/utils.py", change_type=ChangeType.DELETED)]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)
    
    # Assert
    assert result.nodes_deleted > 0
    nodes = await updater.storage.get_nodes_for_file(sample_repo.id, "src/utils.py")
    assert len(nodes) == 0

async def test_modify_file_updates_nodes(updater, sample_repo):
    """Modifying a file should update its nodes."""
    # Modify file content
    (sample_repo.path / "src/main.py").write_text("def new_function(): pass")
    
    changes = [FileChange(path="src/main.py", change_type=ChangeType.MODIFIED)]
    result = await updater.update(sample_repo.id, changes, sample_repo.path)
    
    assert result.nodes_added > 0 or result.nodes_updated > 0

async def test_incremental_update_performance(updater, large_repo):
    """Incremental update should be fast."""
    import time
    
    changes = [FileChange(path="src/single_file.py", change_type=ChangeType.MODIFIED)]
    
    start = time.time()
    await updater.update(large_repo.id, changes, large_repo.path)
    duration = time.time() - start
    
    assert duration < 5.0, f"Update took {duration}s, expected < 5s"
```

---

## E3-6: Webhook Registration API
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E3-1

### Описание
API для автоматической настройки webhooks в GitHub/GitLab. Генерирует secret, возвращает URL и инструкции.

### Реализация

```python
# src/codex_aura/api/webhooks.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import secrets
import hashlib

router = APIRouter(prefix="/api/v1/repos/{repo_id}/webhooks", tags=["webhooks"])

class WebhookSetupRequest(BaseModel):
    platform: Literal["github", "gitlab", "bitbucket"] = "github"
    events: list[str] = ["push", "pull_request"]

class WebhookSetupResponse(BaseModel):
    webhook_url: str
    secret: str
    events: list[str]
    platform: str
    instructions: str
    curl_example: str

class WebhookStatus(BaseModel):
    is_configured: bool
    last_received: datetime | None
    events_received_24h: int
    health: Literal["healthy", "stale", "error"]

@router.post("/setup", response_model=WebhookSetupResponse)
async def setup_webhook(
    repo_id: str,
    request: WebhookSetupRequest,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate webhook configuration for a repository.
    
    Returns the webhook URL, secret, and setup instructions.
    """
    # Verify repo ownership
    repo = await db.get_repo(repo_id)
    if not repo or repo.owner_id != current_user.id:
        raise HTTPException(404, "Repository not found")
    
    # Generate secure secret
    secret = secrets.token_urlsafe(32)
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()
    
    # Store secret hash (not the secret itself)
    await db.store_webhook_secret(repo_id, secret_hash, request.platform)
    
    # Build webhook URL
    base_url = settings.API_BASE_URL
    webhook_url = f"{base_url}/webhooks/{request.platform}/{repo_id}"
    
    # Generate platform-specific instructions
    instructions = _generate_instructions(request.platform, webhook_url, request.events)
    curl_example = _generate_curl_example(request.platform, webhook_url, secret)
    
    return WebhookSetupResponse(
        webhook_url=webhook_url,
        secret=secret,
        events=request.events,
        platform=request.platform,
        instructions=instructions,
        curl_example=curl_example
    )

@router.get("/status", response_model=WebhookStatus)
async def get_webhook_status(
    repo_id: str,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get webhook health status for a repository."""
    
    webhook_config = await db.get_webhook_config(repo_id)
    if not webhook_config:
        return WebhookStatus(
            is_configured=False,
            last_received=None,
            events_received_24h=0,
            health="error"
        )
    
    # Get recent events
    events_24h = await db.count_webhook_events(
        repo_id, 
        since=datetime.utcnow() - timedelta(hours=24)
    )
    
    # Determine health
    if webhook_config.last_received is None:
        health = "stale"
    elif (datetime.utcnow() - webhook_config.last_received).days > 7:
        health = "stale"
    else:
        health = "healthy"
    
    return WebhookStatus(
        is_configured=True,
        last_received=webhook_config.last_received,
        events_received_24h=events_24h,
        health=health
    )

@router.delete("/")
async def delete_webhook(
    repo_id: str,
    db: Database = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove webhook configuration."""
    await db.delete_webhook_config(repo_id)
    return {"status": "deleted"}

@router.post("/test")
async def test_webhook(
    repo_id: str,
    db: Database = Depends(get_db)
):
    """Send a test event to verify webhook is working."""
    # Queue a test event
    await webhook_queue.enqueue(
        WebhookEvent(
            repo_id=repo_id,
            event="ping",
            data={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
    )
    return {"status": "test_queued"}


def _generate_instructions(platform: str, url: str, events: list[str]) -> str:
    """Generate platform-specific setup instructions."""
    
    if platform == "github":
        return f"""
## GitHub Webhook Setup

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure:
   - **Payload URL:** `{url}`
   - **Content type:** `application/json`
   - **Secret:** (use the secret provided above)
   - **Events:** Select {', '.join(events)}
4. Click **Add webhook**

The webhook will start receiving events immediately.
"""
    
    elif platform == "gitlab":
        return f"""
## GitLab Webhook Setup

1. Go to your project on GitLab
2. Navigate to **Settings** → **Webhooks**
3. Configure:
   - **URL:** `{url}`
   - **Secret token:** (use the secret provided above)
   - **Trigger:** Select {', '.join(events)}
4. Click **Add webhook**
"""
    
    return "Platform not supported"


def _generate_curl_example(platform: str, url: str, secret: str) -> str:
    """Generate curl command to test webhook."""
    
    if platform == "github":
        payload = '{"ref":"refs/heads/main","commits":[{"id":"abc123","message":"test"}]}'
        signature = _compute_github_signature(payload, secret)
        return f"""
curl -X POST {url} \\
  -H "Content-Type: application/json" \\
  -H "X-GitHub-Event: push" \\
  -H "X-Hub-Signature-256: sha256={signature}" \\
  -d '{payload}'
"""
    return ""
```

### Критерии приёмки
- [ ] POST /setup генерирует уникальный secret
- [ ] Secret хранится как hash, не plaintext
- [ ] Instructions для GitHub, GitLab, Bitbucket
- [ ] GET /status показывает health
- [ ] POST /test отправляет тестовое событие
- [ ] DELETE / удаляет конфигурацию

---

## E4: Incremental Sync (Полная реализация)

### E4-1: Change Detection
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** Phase 1 E3-4

### Описание
Определение изменений между двумя commits с использованием git diff.

### Реализация

```python
# src/codex_aura/sync/change_detection.py

import subprocess
import asyncio
from dataclasses import dataclass
from pathlib import Path

@dataclass
class GitDiff:
    old_sha: str
    new_sha: str
    changes: list[FileChange]
    stats: DiffStats

@dataclass  
class DiffStats:
    files_changed: int
    insertions: int
    deletions: int

class ChangeDetector:
    """Detect file changes between git commits."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
    
    async def detect_changes(
        self, 
        old_sha: str, 
        new_sha: str
    ) -> GitDiff:
        """
        Get list of changed files between two commits.
        
        Uses `git diff --name-status` for file-level changes.
        """
        # Run git diff
        cmd = [
            "git", "diff", "--name-status", 
            "--no-renames",  # Handle renames separately
            old_sha, new_sha
        ]
        
        result = await self._run_git(cmd)
        changes = self._parse_diff_output(result)
        
        # Get stats
        stats_cmd = ["git", "diff", "--stat", old_sha, new_sha]
        stats_result = await self._run_git(stats_cmd)
        stats = self._parse_stats(stats_result)
        
        return GitDiff(
            old_sha=old_sha,
            new_sha=new_sha,
            changes=changes,
            stats=stats
        )
    
    async def detect_renames(
        self, 
        old_sha: str, 
        new_sha: str,
        similarity_threshold: int = 50
    ) -> list[FileChange]:
        """Detect renamed files using git's rename detection."""
        cmd = [
            "git", "diff", "--name-status",
            f"-M{similarity_threshold}%",  # Rename detection threshold
            "--diff-filter=R",  # Only renames
            old_sha, new_sha
        ]
        
        result = await self._run_git(cmd)
        renames = []
        
        for line in result.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].startswith("R"):
                renames.append(FileChange(
                    path=parts[2],  # new path
                    old_path=parts[1],  # old path
                    change_type=ChangeType.RENAMED
                ))
        
        return renames
    
    async def get_file_at_commit(
        self, 
        file_path: str, 
        sha: str
    ) -> str | None:
        """Get file content at a specific commit."""
        cmd = ["git", "show", f"{sha}:{file_path}"]
        try:
            return await self._run_git(cmd)
        except subprocess.CalledProcessError:
            return None  # File didn't exist at this commit
    
    async def get_changed_lines(
        self,
        file_path: str,
        old_sha: str,
        new_sha: str
    ) -> tuple[list[int], list[int]]:
        """
        Get specific line numbers that changed.
        Returns (added_lines, removed_lines).
        """
        cmd = [
            "git", "diff", 
            "--unified=0",  # No context lines
            old_sha, new_sha,
            "--", file_path
        ]
        
        result = await self._run_git(cmd)
        return self._parse_line_changes(result)
    
    async def _run_git(self, cmd: list[str]) -> str:
        """Run git command asynchronously."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, stderr.decode()
            )
        
        return stdout.decode()
    
    def _parse_diff_output(self, output: str) -> list[FileChange]:
        """Parse git diff --name-status output."""
        changes = []
        
        for line in output.strip().split("\n"):
            if not line:
                continue
            
            parts = line.split("\t")
            status = parts[0]
            path = parts[1] if len(parts) > 1 else ""
            
            change_type = {
                "A": ChangeType.ADDED,
                "M": ChangeType.MODIFIED,
                "D": ChangeType.DELETED,
            }.get(status[0], ChangeType.MODIFIED)
            
            changes.append(FileChange(path=path, change_type=change_type))
        
        return changes
    
    def _parse_stats(self, output: str) -> DiffStats:
        """Parse git diff --stat output."""
        lines = output.strip().split("\n")
        if not lines:
            return DiffStats(0, 0, 0)
        
        # Last line contains summary
        summary = lines[-1]
        # "3 files changed, 10 insertions(+), 5 deletions(-)"
        
        import re
        files = re.search(r"(\d+) files? changed", summary)
        insertions = re.search(r"(\d+) insertions?", summary)
        deletions = re.search(r"(\d+) deletions?", summary)
        
        return DiffStats(
            files_changed=int(files.group(1)) if files else 0,
            insertions=int(insertions.group(1)) if insertions else 0,
            deletions=int(deletions.group(1)) if deletions else 0
        )
    
    def _parse_line_changes(self, diff_output: str) -> tuple[list[int], list[int]]:
        """Parse unified diff to get changed line numbers."""
        added_lines = []
        removed_lines = []
        
        import re
        # Match @@ -start,count +start,count @@
        hunk_pattern = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
        
        current_old_line = 0
        current_new_line = 0
        
        for line in diff_output.split("\n"):
            hunk_match = hunk_pattern.match(line)
            if hunk_match:
                current_old_line = int(hunk_match.group(1))
                current_new_line = int(hunk_match.group(3))
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(current_new_line)
                current_new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(current_old_line)
                current_old_line += 1
            elif not line.startswith("\\"):
                current_old_line += 1
                current_new_line += 1
        
        return added_lines, removed_lines
```

### Критерии приёмки
- [ ] Корректно определяет A/M/D файлы
- [ ] Обнаруживает переименования
- [ ] Получает контент файла на любом commit
- [ ] Определяет изменённые строки
- [ ] Async execution

---

### E4-2: Partial Re-analysis
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E4-1

### Описание
Анализ только изменённых частей файлов для максимальной эффективности.

### Реализация

```python
# src/codex_aura/sync/partial_analysis.py

class PartialAnalyzer:
    """Analyze only changed portions of files."""
    
    def __init__(self, analyzer: CodeAnalyzer):
        self.analyzer = analyzer
    
    async def analyze_changes(
        self,
        file_path: Path,
        old_content: str | None,
        new_content: str,
        changed_lines: list[int]
    ) -> PartialAnalysisResult:
        """
        Smart analysis that focuses on changed code regions.
        
        Strategy:
        1. Parse both old and new AST
        2. Find nodes that contain changed lines
        3. Only re-analyze those nodes
        4. Keep unchanged nodes from old analysis
        """
        result = PartialAnalysisResult(
            updated_nodes=[],
            deleted_nodes=[],
            unchanged_nodes=[]
        )
        
        # Parse new content
        new_tree = ast.parse(new_content)
        new_nodes = self._extract_nodes(new_tree, file_path, new_content)
        
        if old_content is None:
            # New file - all nodes are new
            result.updated_nodes = new_nodes
            return result
        
        # Parse old content
        try:
            old_tree = ast.parse(old_content)
            old_nodes = self._extract_nodes(old_tree, file_path, old_content)
        except SyntaxError:
            # Old content had syntax error - treat as full update
            result.updated_nodes = new_nodes
            return result
        
        old_nodes_map = {n.fqn: n for n in old_nodes}
        new_nodes_map = {n.fqn: n for n in new_nodes}
        
        # Find affected nodes
        affected_fqns = self._find_affected_nodes(new_nodes, changed_lines)
        
        for fqn, node in new_nodes_map.items():
            if fqn in affected_fqns:
                # Node was changed
                result.updated_nodes.append(node)
            elif fqn in old_nodes_map:
                # Node unchanged, keep old analysis
                result.unchanged_nodes.append(old_nodes_map[fqn])
            else:
                # New node
                result.updated_nodes.append(node)
        
        # Find deleted nodes
        for fqn in old_nodes_map:
            if fqn not in new_nodes_map:
                result.deleted_nodes.append(old_nodes_map[fqn])
        
        return result
    
    def _find_affected_nodes(
        self, 
        nodes: list[Node], 
        changed_lines: list[int]
    ) -> set[str]:
        """Find nodes that contain any changed line."""
        affected = set()
        changed_set = set(changed_lines)
        
        for node in nodes:
            node_lines = set(range(node.start_line, node.end_line + 1))
            if node_lines & changed_set:
                affected.add(node.fqn)
        
        return affected
    
    def _extract_nodes(
        self, 
        tree: ast.AST, 
        file_path: Path, 
        content: str
    ) -> list[Node]:
        """Extract all analyzable nodes from AST."""
        nodes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                nodes.append(self._node_from_ast(node, "function", file_path, content))
            elif isinstance(node, ast.ClassDef):
                nodes.append(self._node_from_ast(node, "class", file_path, content))
        
        return nodes
```

### Критерии приёмки
- [ ] Только затронутые nodes re-analyzed
- [ ] Unchanged nodes сохраняются
- [ ] Deleted nodes определяются
- [ ] Работает с syntax errors в старом коде

---

### E4-3: Edge Recalculation
**Оценка:** 4h | **Приоритет:** P0 | **Зависимости:** E4-2

### Описание
Умный пересчёт рёбер только для затронутых nodes.

### Реализация

```python
# src/codex_aura/sync/edge_recalc.py

class EdgeRecalculator:
    """Recalculate edges affected by node changes."""
    
    async def recalculate(
        self,
        graph: Graph,
        updated_nodes: list[Node],
        deleted_nodes: list[Node]
    ) -> EdgeRecalcResult:
        """
        Recalculate edges for changed nodes.
        
        Strategy:
        1. Remove all edges FROM deleted nodes
        2. Remove all edges TO deleted nodes  
        3. Re-analyze edges FROM updated nodes
        4. Keep edges TO updated nodes (they're still valid targets)
        """
        result = EdgeRecalcResult(
            edges_added=0,
            edges_removed=0,
            edges_updated=0
        )
        
        deleted_fqns = {n.fqn for n in deleted_nodes}
        updated_fqns = {n.fqn for n in updated_nodes}
        
        async with graph.transaction() as txn:
            # Step 1: Remove edges from/to deleted nodes
            for fqn in deleted_fqns:
                removed = await txn.delete_edges_for_node(fqn)
                result.edges_removed += removed
            
            # Step 2: Remove outgoing edges from updated nodes
            # (incoming edges are still valid - other nodes still reference us)
            for fqn in updated_fqns:
                removed = await txn.delete_outgoing_edges(fqn)
                result.edges_removed += removed
            
            # Step 3: Re-analyze edges from updated nodes
            for node in updated_nodes:
                references = await self._analyze_references(node)
                
                for ref in references:
                    # Check if target exists in graph
                    target_exists = await txn.node_exists(ref.target_fqn)
                    
                    if target_exists:
                        await txn.create_edge(
                            source=node.fqn,
                            target=ref.target_fqn,
                            edge_type=ref.type,
                            metadata=ref.metadata
                        )
                        result.edges_added += 1
                    else:
                        # External reference - create placeholder or skip
                        if self.track_external:
                            await txn.create_external_ref(node.fqn, ref)
        
        return result
    
    async def _analyze_references(self, node: Node) -> list[Reference]:
        """Analyze code to find references to other nodes."""
        references = []
        
        tree = ast.parse(node.content)
        
        for child in ast.walk(tree):
            # Import statements
            if isinstance(child, ast.Import):
                for alias in child.names:
                    references.append(Reference(
                        target_fqn=alias.name,
                        type=EdgeType.IMPORTS,
                        line=child.lineno
                    ))
            
            elif isinstance(child, ast.ImportFrom):
                module = child.module or ""
                for alias in child.names:
                    references.append(Reference(
                        target_fqn=f"{module}.{alias.name}",
                        type=EdgeType.IMPORTS,
                        line=child.lineno
                    ))
            
            # Function calls
            elif isinstance(child, ast.Call):
                call_target = self._resolve_call_target(child)
                if call_target:
                    references.append(Reference(
                        target_fqn=call_target,
                        type=EdgeType.CALLS,
                        line=child.lineno
                    ))
            
            # Class inheritance
            elif isinstance(child, ast.ClassDef):
                for base in child.bases:
                    base_name = self._resolve_base_class(base)
                    if base_name:
                        references.append(Reference(
                            target_fqn=base_name,
                            type=EdgeType.EXTENDS,
                            line=child.lineno
                        ))
        
        return references
```

### Критерии приёмки
- [ ] Edges от deleted nodes удаляются
- [ ] Edges к deleted nodes удаляются
- [ ] Outgoing edges от updated nodes пересчитываются
- [ ] Incoming edges к updated nodes сохраняются
- [ ] External references отслеживаются опционально

---

### E4-4: Vector Index Update
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E4-2

### Описание
Инкрементальное обновление embeddings в Qdrant.

### Реализация

```python
# src/codex_aura/sync/vector_sync.py

class VectorIndexSyncer:
    """Keep vector index in sync with graph changes."""
    
    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        chunker: CodeChunker
    ):
        self.vectors = vector_store
        self.embeddings = embedding_service
        self.chunker = chunker
    
    async def sync_changes(
        self,
        repo_id: str,
        updated_nodes: list[Node],
        deleted_nodes: list[Node]
    ) -> VectorSyncResult:
        """
        Sync vector index with graph changes.
        
        Strategy:
        1. Delete vectors for deleted nodes
        2. Delete old vectors for updated nodes
        3. Re-chunk and re-embed updated nodes
        4. Upsert new vectors
        """
        collection = f"repo_{repo_id}"
        result = VectorSyncResult(
            vectors_added=0,
            vectors_deleted=0,
            embedding_tokens=0
        )
        
        # Step 1: Delete vectors for deleted nodes
        deleted_fqns = [n.fqn for n in deleted_nodes]
        if deleted_fqns:
            deleted_count = await self.vectors.delete_by_fqns(
                collection, deleted_fqns
            )
            result.vectors_deleted += deleted_count
        
        # Step 2: Delete old vectors for updated nodes
        updated_fqns = [n.fqn for n in updated_nodes]
        if updated_fqns:
            deleted_count = await self.vectors.delete_by_fqns(
                collection, updated_fqns
            )
            result.vectors_deleted += deleted_count
        
        # Step 3: Chunk and embed updated nodes
        if updated_nodes:
            all_chunks = []
            for node in updated_nodes:
                chunks = self.chunker.chunk_node(node)
                all_chunks.extend(chunks)
            
            if all_chunks:
                # Batch embed for efficiency
                texts = [c.content for c in all_chunks]
                embeddings = await self.embeddings.embed_batch(texts)
                
                # Track token usage
                result.embedding_tokens = sum(
                    len(self.embeddings.tokenizer.encode(t)) 
                    for t in texts
                )
                
                # Upsert to vector store
                await self.vectors.upsert_chunks(
                    collection, all_chunks, embeddings
                )
                result.vectors_added = len(all_chunks)
        
        return result
    
    async def full_reindex(
        self,
        repo_id: str,
        graph: Graph,
        batch_size: int = 100
    ) -> VectorSyncResult:
        """Full reindex of all nodes (for recovery/migration)."""
        collection = f"repo_{repo_id}"
        
        # Clear existing
        await self.vectors.delete_collection(collection)
        await self.vectors.create_collection(collection)
        
        result = VectorSyncResult(...)
        
        # Process in batches
        all_nodes = await graph.get_all_nodes()
        
        for i in range(0, len(all_nodes), batch_size):
            batch = all_nodes[i:i + batch_size]
            batch_result = await self.sync_changes(repo_id, batch, [])
            result.vectors_added += batch_result.vectors_added
            result.embedding_tokens += batch_result.embedding_tokens
        
        return result
```

### Критерии приёмки
- [ ] Deleted nodes удаляются из индекса
- [ ] Updated nodes re-embedded
- [ ] Batch embedding для эффективности
- [ ] Token usage отслеживается
- [ ] Full reindex для recovery

---

### E4-5: Sync Status Tracking
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E4-1

### Описание
Отслеживание статуса синхронизации каждого репозитория.

### Реализация

```python
# src/codex_aura/sync/status.py

from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum

class SyncState(str, Enum):
    SYNCED = "synced"          # Up to date
    SYNCING = "syncing"        # Currently processing
    STALE = "stale"            # Behind by commits
    ERROR = "error"            # Last sync failed
    PENDING = "pending"        # Queued for sync

class SyncStatus(BaseModel):
    repo_id: str
    state: SyncState
    current_sha: str | None
    target_sha: str | None
    last_sync_at: datetime | None
    last_sync_duration_ms: int | None
    commits_behind: int
    error_message: str | None
    retry_count: int

class SyncStatusTracker:
    """Track and manage sync status for repositories."""
    
    def __init__(self, db: Database, redis: Redis):
        self.db = db
        self.redis = redis
    
    async def get_status(self, repo_id: str) -> SyncStatus:
        """Get current sync status for a repository."""
        # Check if currently syncing (in Redis)
        syncing = await self.redis.get(f"syncing:{repo_id}")
        if syncing:
            return SyncStatus(
                repo_id=repo_id,
                state=SyncState.SYNCING,
                **json.loads(syncing)
            )
        
        # Get from database
        record = await self.db.get_sync_status(repo_id)
        if not record:
            return SyncStatus(
                repo_id=repo_id,
                state=SyncState.PENDING,
                current_sha=None,
                target_sha=None,
                last_sync_at=None,
                last_sync_duration_ms=None,
                commits_behind=0,
                error_message=None,
                retry_count=0
            )
        
        return SyncStatus(**record)
    
    async def start_sync(
        self, 
        repo_id: str, 
        target_sha: str
    ):
        """Mark repository as syncing."""
        status = {
            "target_sha": target_sha,
            "started_at": datetime.utcnow().isoformat()
        }
        await self.redis.setex(
            f"syncing:{repo_id}",
            300,  # 5 min TTL (防止 stuck)
            json.dumps(status)
        )
    
    async def complete_sync(
        self,
        repo_id: str,
        new_sha: str,
        duration_ms: int,
        success: bool,
        error: str | None = None
    ):
        """Mark sync as complete."""
        # Remove syncing flag
        await self.redis.delete(f"syncing:{repo_id}")
        
        # Update database
        if success:
            await self.db.update_sync_status(
                repo_id=repo_id,
                state=SyncState.SYNCED,
                current_sha=new_sha,
                last_sync_at=datetime.utcnow(),
                last_sync_duration_ms=duration_ms,
                error_message=None,
                retry_count=0
            )
        else:
            current = await self.db.get_sync_status(repo_id)
            await self.db.update_sync_status(
                repo_id=repo_id,
                state=SyncState.ERROR,
                error_message=error,
                retry_count=(current.retry_count or 0) + 1
            )
    
    async def get_stale_repos(
        self, 
        threshold: timedelta = timedelta(hours=1)
    ) -> list[str]:
        """Find repositories that haven't synced recently."""
        cutoff = datetime.utcnow() - threshold
        return await self.db.find_repos_synced_before(cutoff)


# API endpoint
@router.get("/api/v1/repos/{repo_id}/sync/status")
async def get_sync_status(
    repo_id: str,
    tracker: SyncStatusTracker = Depends(get_tracker)
) -> SyncStatus:
    return await tracker.get_status(repo_id)

@router.post("/api/v1/repos/{repo_id}/sync/trigger")
async def trigger_sync(
    repo_id: str,
    target_sha: str | None = None,
    tracker: SyncStatusTracker = Depends(get_tracker),
    queue: WebhookQueue = Depends(get_queue)
):
    """Manually trigger sync for a repository."""
    status = await tracker.get_status(repo_id)
    
    if status.state == SyncState.SYNCING:
        raise HTTPException(409, "Sync already in progress")
    
    # Queue sync job
    await queue.enqueue(SyncJob(
        repo_id=repo_id,
        target_sha=target_sha or "HEAD"
    ))
    
    return {"status": "queued"}
```

### Критерии приёмки
- [ ] Status tracking в Redis (realtime)
- [ ] Persistent status в PostgreSQL
- [ ] GET /sync/status endpoint
- [ ] POST /sync/trigger endpoint
- [ ] Stale repo detection
- [ ] Retry count tracking