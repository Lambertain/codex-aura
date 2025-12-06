# 📋 Phase 1.3: Усиление и Доработки

**Длительность:** 3-4 недели
**Цель:** Укрепить core, добавить недостающие компоненты, подготовить к Phase 2
**Предусловие:** Phase 0 и Phase 1 завершены

---

## 📊 Обзор эпиков

| # | Эпик | Задач | Оценка |
|---|------|-------|--------|
| E1 | Plugin Architecture | 7 | 16h |
| E2 | Project Configuration | 6 | 10h |
| E3 | Git Integration (Advanced) | 5 | 10h |
| E4 | Security Hardening | 6 | 12h |
| E5 | AI Agent SDK & Testing | 8 | 20h |
| E6 | VS Code Extension (Enhanced) | 8 | 20h |
| E7 | GitHub Action (Enhanced) | 6 | 12h |
| E8 | MCP Protocol Specification | 5 | 10h |
| E9 | Observability & Metrics | 5 | 8h |
| | **ИТОГО** | **56** | **~118h** |

---

## E1: 🔌 Plugin Architecture

### E1-1: Определение Plugin Interfaces
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Создать абстрактные интерфейсы для всех типов плагинов.

**Интерфейсы:**
```python
# src/codex_aura/plugins/interfaces.py

from typing import Protocol, runtime_checkable

@runtime_checkable
class ContextPlugin(Protocol):
    """Plugin for context ranking and filtering."""
    
    name: str
    version: str
    
    def rank_nodes(
        self,
        nodes: list[Node],
        task: str,
        max_tokens: int | None = None
    ) -> list[Node]: ...
    
    def get_capabilities(self) -> dict[str, bool]: ...

@runtime_checkable
class ImpactPlugin(Protocol):
    """Plugin for impact analysis."""
    
    def analyze_impact(
        self,
        changed_files: list[Path],
        graph: Graph,
        depth: int = 3
    ) -> ImpactReport: ...

@runtime_checkable
class AnalyzerPlugin(Protocol):
    """Plugin for language-specific analysis."""
    
    supported_extensions: list[str]
    
    def analyze_file(self, file_path: Path) -> list[Node]: ...
    def extract_edges(self, nodes: list[Node]) -> list[Edge]: ...
```

**Критерии приёмки:**
- [ ] Все интерфейсы используют Protocol (structural typing)
- [ ] runtime_checkable для isinstance проверок
- [ ] Docstrings для каждого метода

---

### E1-2: Plugin Registry & Loader
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Система регистрации и загрузки плагинов.

**Реализация:**
```python
# src/codex_aura/plugins/registry.py

class PluginRegistry:
    _context_plugins: dict[str, type[ContextPlugin]] = {}
    _impact_plugins: dict[str, type[ImpactPlugin]] = {}
    _analyzer_plugins: dict[str, type[AnalyzerPlugin]] = {}
    
    @classmethod
    def register_context(cls, name: str):
        def decorator(plugin_cls):
            cls._context_plugins[name] = plugin_cls
            return plugin_cls
        return decorator
    
    @classmethod
    def get_context_plugin(cls, name: str) -> ContextPlugin:
        if name not in cls._context_plugins:
            raise PluginNotFoundError(name)
        return cls._context_plugins[name]()
    
    @classmethod
    def load_from_config(cls, config: PluginConfig):
        """Load plugins specified in config."""
        for plugin_path in config.enabled_plugins:
            module = importlib.import_module(plugin_path)
            # Auto-registration via decorators
```

**Критерии приёмки:**
- [ ] Декораторы для регистрации
- [ ] Загрузка по имени модуля
- [ ] Graceful fallback при ошибке загрузки

---

### E1-3: Basic Plugins Implementation
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Реализовать базовые плагины (open source версии).

**Плагины:**
```python
# src/codex_aura/plugins/builtin/context_basic.py

@PluginRegistry.register_context("basic")
class BasicContextPlugin:
    name = "basic"
    version = "1.0.0"
    
    def rank_nodes(self, nodes, task, max_tokens=None):
        # Sort by graph distance
        sorted_nodes = sorted(nodes, key=lambda n: n.distance)
        
        if max_tokens:
            # Simple truncation (no smart budgeting)
            return sorted_nodes[:self._estimate_count(max_tokens)]
        return sorted_nodes
    
    def get_capabilities(self):
        return {
            "semantic_ranking": False,
            "token_budgeting": False,
            "task_understanding": False
        }
```

```python
# src/codex_aura/plugins/builtin/impact_basic.py

@PluginRegistry.register_impact("basic")
class BasicImpactPlugin:
    def analyze_impact(self, changed_files, graph, depth=3):
        affected = set()
        for file in changed_files:
            affected.update(
                graph.get_dependents(file, max_depth=depth)
            )
        return ImpactReport(
            affected_files=list(affected),
            risk_level=self._calculate_risk(affected)
        )
```

**Критерии приёмки:**
- [ ] BasicContextPlugin работает
- [ ] BasicImpactPlugin работает
- [ ] Оба зарегистрированы в registry

---

### E1-4: Plugin Configuration
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Конфигурация плагинов через файл и environment.

**Формат:**
```yaml
# .codex-aura/plugins.yaml
plugins:
  context:
    default: "basic"
    fallback: "basic"
    
  impact:
    default: "basic"
    
  analyzers:
    python: "codex_aura.plugins.builtin.python"
    # Future:
    # typescript: "codex_aura.plugins.builtin.typescript"

# Для premium (загружается если установлен codex-aura-premium)
premium:
  context: "codex_aura_premium.semantic"
  impact: "codex_aura_premium.impact_advanced"
```

**Критерии приёмки:**
- [ ] YAML конфиг парсится
- [ ] Environment override работает
- [ ] Валидация конфига

---

### E1-5: Plugin Discovery (Entry Points)
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Автоматическое обнаружение плагинов через setuptools entry points.

**pyproject.toml (plugin):**
```toml
[project.entry-points."codex_aura.plugins.context"]
semantic = "codex_aura_premium.semantic:SemanticContextPlugin"

[project.entry-points."codex_aura.plugins.analyzer"]
typescript = "codex_aura_ts:TypeScriptAnalyzer"
```

**Loader:**
```python
from importlib.metadata import entry_points

def discover_plugins():
    eps = entry_points(group="codex_aura.plugins.context")
    for ep in eps:
        plugin_cls = ep.load()
        PluginRegistry.register_context(ep.name, plugin_cls)
```

**Критерии приёмки:**
- [ ] Entry points обнаруживаются
- [ ] Сторонние плагины загружаются
- [ ] Конфликты имён обрабатываются

---

### E1-6: Plugin Capability Negotiation
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
API для запроса capabilities текущих плагинов.

**Endpoint:**
```http
GET /api/v1/capabilities
```

**Response:**
```json
{
  "context_plugin": {
    "name": "basic",
    "version": "1.0.0",
    "capabilities": {
      "semantic_ranking": false,
      "token_budgeting": false,
      "task_understanding": false
    }
  },
  "impact_plugin": {
    "name": "basic",
    "capabilities": {
      "transitive_analysis": true,
      "test_detection": true,
      "risk_scoring": false
    }
  },
  "premium_available": false
}
```

**Критерии приёмки:**
- [ ] Endpoint возвращает capabilities
- [ ] Клиенты могут адаптировать запросы

---

### E1-7: Plugin Documentation & Template
**Оценка:** 3h | **Приоритет:** P1

**Описание:**
Документация и шаблон для создания плагинов.

**Deliverables:**
- [ ] `docs/plugins/creating-plugins.md`
- [ ] `docs/plugins/plugin-api.md`
- [ ] `examples/custom-plugin/` — template репозиторий
- [ ] Cookiecutter/copier template

**Критерии приёмки:**
- [ ] Разработчик может создать плагин за 30 минут
- [ ] Template проект работает

---

## E2: ⚙️ Project Configuration

### E2-1: Configuration Schema Design
**Оценка:** 1h | **Приоритет:** P0

**Описание:**
Дизайн полной схемы конфигурации.

**Схема:**
```yaml
# .codex-aura/config.yaml
version: "1.0"

project:
  name: "my-project"
  description: "Optional description"

analyzer:
  languages: 
    - python
  edge_types:
    - IMPORTS
    - CALLS
    - EXTENDS
  include_patterns:
    - "src/**/*.py"
  exclude_patterns:
    - "**/tests/**"
    - "**/__pycache__/**"
    - ".venv/**"
    - "node_modules/**"

context:
  default_depth: 2
  default_max_nodes: 100
  include_docstrings: true
  include_code: true

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins: ["*"]

plugins:
  context: "basic"
  impact: "basic"
```

**Критерии приёмки:**
- [ ] Schema полная и расширяемая
- [ ] JSON Schema для валидации

---

### E2-2: Configuration Parser
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Парсер конфигурации с валидацией.

**Реализация:**
```python
# src/codex_aura/config/parser.py

class ProjectConfig(BaseModel):
    version: str = "1.0"
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    analyzer: AnalyzerSettings = Field(default_factory=AnalyzerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)

def load_config(repo_path: Path) -> ProjectConfig:
    config_path = repo_path / ".codex-aura" / "config.yaml"
    
    if config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return ProjectConfig(**data)
    
    return ProjectConfig()  # defaults
```

**Критерии приёмки:**
- [ ] YAML парсится
- [ ] Pydantic валидация
- [ ] Defaults для всех полей

---

### E2-3: CLI `init` Command
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Команда инициализации проекта.

**Использование:**
```bash
codex-aura init
codex-aura init --force  # перезаписать существующий
codex-aura init --minimal  # только обязательные поля
```

**Создаёт:**
```
.codex-aura/
├── config.yaml
├── rules.yaml      # для будущего Code Intelligence
└── .gitignore      # игнорировать кэш и временные файлы
```

**Интерактивный режим:**
```
$ codex-aura init
Project name [my-project]: 
Primary language [python]: 
Include tests in analysis? [y/N]: n
✓ Created .codex-aura/config.yaml
✓ Created .codex-aura/rules.yaml
```

**Критерии приёмки:**
- [ ] Директория создаётся
- [ ] Интерактивный режим работает
- [ ] --minimal флаг работает

---

### E2-4: Config Inheritance & Override
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Поддержка наследования конфигов и override через env.

**Приоритет (от низшего к высшему):**
1. Built-in defaults
2. `.codex-aura/config.yaml`
3. Environment variables (`CODEX_AURA_*`)
4. CLI arguments

**Environment mapping:**
```
CODEX_AURA_ANALYZER_LANGUAGES=python,typescript
CODEX_AURA_SERVER_PORT=9000
CODEX_AURA_CONTEXT_DEFAULT_DEPTH=3
```

**Критерии приёмки:**
- [ ] Env override работает
- [ ] CLI override работает
- [ ] Приоритет соблюдается

---

### E2-5: Config Validation Command
**Оценка:** 1h | **Приоритет:** P1

**Описание:**
Команда проверки конфигурации.

```bash
codex-aura config validate
codex-aura config show  # показать effective config
codex-aura config show --json
```

**Вывод:**
```
$ codex-aura config validate
✓ Config file: .codex-aura/config.yaml
✓ Version: 1.0 (supported)
✓ Analyzer settings: valid
✓ Plugin 'basic' found
⚠ Warning: exclude_patterns is empty

$ codex-aura config show
project.name: my-project
analyzer.languages: [python]
analyzer.edge_types: [IMPORTS, CALLS, EXTENDS]
server.port: 8000 (from env: CODEX_AURA_SERVER_PORT)
...
```

**Критерии приёмки:**
- [ ] Валидация выводит ошибки понятно
- [ ] show показывает источник каждого значения

---

### E2-6: Ignore Patterns Support
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Полноценная поддержка gitignore-style паттернов.

**Реализация:**
```python
from pathspec import PathSpec

def load_ignore_patterns(repo_path: Path) -> PathSpec:
    patterns = []
    
    # Built-in
    patterns.extend([
        "__pycache__/",
        "*.pyc",
        ".git/",
        ".venv/",
        "venv/",
        "node_modules/",
    ])
    
    # From config
    config = load_config(repo_path)
    patterns.extend(config.analyzer.exclude_patterns)
    
    # From .codex-aura/.ignore
    ignore_file = repo_path / ".codex-aura" / ".ignore"
    if ignore_file.exists():
        patterns.extend(ignore_file.read_text().splitlines())
    
    return PathSpec.from_lines("gitwildmatch", patterns)
```

**Критерии приёмки:**
- [ ] Gitignore syntax поддерживается
- [ ] .codex-aura/.ignore читается
- [ ] Патерны из конфига применяются

---

## E3: 🔀 Git Integration (Advanced)

### E3-1: Git Blame Integration
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Получение информации об авторстве для каждого файла.

**Реализация:**
```python
import subprocess

def get_file_blame(file_path: Path, repo_path: Path) -> BlameInfo:
    result = subprocess.run(
        ["git", "blame", "--line-porcelain", str(file_path)],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    
    authors = Counter()
    for line in result.stdout.split("\n"):
        if line.startswith("author "):
            authors[line[7:]] += 1
    
    return BlameInfo(
        primary_author=authors.most_common(1)[0][0],
        contributors=list(authors.keys()),
        author_distribution=dict(authors)
    )
```

**Добавить в Node:**
```python
class Node(BaseModel):
    # ... existing fields ...
    blame: BlameInfo | None = None
```

**Критерии приёмки:**
- [ ] Primary author определяется
- [ ] Список контрибьюторов
- [ ] Graceful fallback если не git repo

---

### E3-2: Change Frequency Analysis
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Анализ частоты изменений файлов (hot spots).

**Реализация:**
```python
def get_change_frequency(
    file_path: Path, 
    repo_path: Path,
    days: int = 90
) -> ChangeFrequency:
    since_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    result = subprocess.run(
        ["git", "log", "--since", since_date, "--format=%H", "--", str(file_path)],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    
    commits = [c for c in result.stdout.strip().split("\n") if c]
    
    return ChangeFrequency(
        commits_count=len(commits),
        period_days=days,
        is_hot_spot=len(commits) > 10  # threshold
    )
```

**Критерии приёмки:**
- [ ] Количество коммитов за период
- [ ] Hot spot detection
- [ ] Настраиваемый период

---

### E3-3: Branch & Tag Detection
**Оценка:** 1h | **Приоритет:** P1

**Описание:**
Определение текущей ветки и ближайшего тега.

**Реализация:**
```python
def get_git_info(repo_path: Path) -> GitInfo:
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()
    
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path, capture_output=True, text=True
    ).stdout.strip()
    
    tag = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=repo_path, capture_output=True, text=True
    ).stdout.strip() or None
    
    return GitInfo(branch=branch, sha=sha, tag=tag)
```

**Критерии приёмки:**
- [ ] Branch определяется
- [ ] SHA полный
- [ ] Tag если есть

---

### E3-4: Diff Analysis for Incremental Updates
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Определение изменённых файлов между SHA для incremental анализа.

**Реализация:**
```python
def get_changed_files(
    repo_path: Path,
    from_sha: str,
    to_sha: str = "HEAD"
) -> ChangedFiles:
    result = subprocess.run(
        ["git", "diff", "--name-status", from_sha, to_sha],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    
    added, modified, deleted = [], [], []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        status, path = line.split("\t", 1)
        if status == "A":
            added.append(path)
        elif status == "M":
            modified.append(path)
        elif status == "D":
            deleted.append(path)
    
    return ChangedFiles(added=added, modified=modified, deleted=deleted)
```

**Критерии приёмки:**
- [ ] Added/Modified/Deleted определяются
- [ ] Renamed файлы обрабатываются
- [ ] Работает с merge commits

---

### E3-5: Incremental Graph Update
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Обновление графа только для изменённых файлов.

**API:**
```python
def update_graph_incremental(
    graph: Graph,
    repo_path: Path,
    from_sha: str
) -> Graph:
    changes = get_changed_files(repo_path, from_sha)
    
    # Remove deleted nodes and their edges
    for path in changes.deleted:
        graph.remove_nodes_by_path(path)
    
    # Re-analyze modified and added
    for path in changes.added + changes.modified:
        new_nodes = analyzer.analyze_file(path)
        graph.replace_nodes_for_path(path, new_nodes)
    
    # Rebuild edges for affected nodes
    graph.rebuild_edges_for_paths(changes.added + changes.modified)
    
    graph.sha = get_current_sha(repo_path)
    return graph
```

**Критерии приёмки:**
- [ ] Удалённые файлы убираются из графа
- [ ] Изменённые пере-анализируются
- [ ] Рёбра перестраиваются

---

## E4: 🔒 Security Hardening

### E4-1: Input Validation Middleware
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Строгая валидация всех входных данных.

**Реализация:**
```python
from pydantic import validator, constr

class AnalyzeRequest(BaseModel):
    repo_path: constr(max_length=1000)
    edge_types: list[EdgeType] = Field(max_items=10)
    
    @validator("repo_path")
    def validate_path(cls, v):
        path = Path(v).resolve()
        
        # No path traversal
        if ".." in str(path):
            raise ValueError("Path traversal not allowed")
        
        # Must exist
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        
        # Must be directory
        if not path.is_dir():
            raise ValueError("Path must be a directory")
        
        return str(path)
```

**Критерии приёмки:**
- [ ] Все endpoints имеют Pydantic models
- [ ] Path traversal блокируется
- [ ] Max lengths установлены

---

### E4-2: Path Traversal Protection
**Оценка:** 1h | **Приоритет:** P0

**Описание:**
Защита от path traversal атак.

**Реализация:**
```python
ALLOWED_ROOTS = [
    Path.home(),
    Path("/tmp"),
    # Add more as needed
]

def validate_repo_path(path: str) -> Path:
    resolved = Path(path).resolve()
    
    # Check against allowed roots
    is_allowed = any(
        resolved.is_relative_to(root) 
        for root in ALLOWED_ROOTS
    )
    
    if not is_allowed:
        raise SecurityError(f"Path not in allowed directories: {path}")
    
    return resolved
```

**Критерии приёмки:**
- [ ] Whitelist подход
- [ ] Symlinks разрешаются безопасно

---

### E4-3: Rate Limiting
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Базовый rate limiting для API.

**Реализация:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/v1/analyze")
@limiter.limit("10/minute")
async def analyze(request: Request, body: AnalyzeRequest):
    ...

@app.post("/api/v1/context")
@limiter.limit("60/minute")
async def context(request: Request, body: ContextRequest):
    ...
```

**Конфигурация:**
```yaml
# config.yaml
server:
  rate_limits:
    analyze: "10/minute"
    context: "60/minute"
    default: "100/minute"
```

**Критерии приёмки:**
- [ ] Per-endpoint limits
- [ ] Configurable
- [ ] 429 response with Retry-After

---

### E4-4: Request Size Limits
**Оценка:** 30min | **Приоритет:** P0

**Описание:**
Ограничение размера запросов.

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_size = max_size
    
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            return JSONResponse(
                status_code=413,
                content={"error": "Request too large"}
            )
        return await call_next(request)
```

**Критерии приёмки:**
- [ ] 413 для больших запросов
- [ ] Настраиваемый лимит

---

### E4-5: Security Headers
**Оценка:** 30min | **Приоритет:** P1

**Описание:**
Добавление security headers.

```python
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
```

**Критерии приёмки:**
- [ ] Headers добавляются ко всем ответам

---

### E4-6: Dependency Audit
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Аудит зависимостей на уязвимости.

**Действия:**
- [ ] Добавить `pip-audit` в CI
- [ ] Добавить `safety` check
- [ ] Настроить Dependabot
- [ ] Документировать процесс обновления

**CI:**
```yaml
- name: Security audit
  run: |
    pip install pip-audit safety
    pip-audit
    safety check
```

**Критерии приёмки:**
- [ ] CI проверяет зависимости
- [ ] Dependabot настроен
- [ ] Нет known vulnerabilities

---

## E5: 🤖 AI Agent SDK & Testing

### E5-1: Python SDK Design
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Дизайн удобного Python SDK для агентов.

**API:**
```python
from codex_aura import CodexAura

# Инициализация
ca = CodexAura(
    server_url="http://localhost:8000",
    # или
    repo_path="/path/to/repo"  # локальный режим
)

# Анализ
graph = ca.analyze()

# Получение контекста
context = ca.get_context(
    task="Fix the authentication bug",
    entry_points=["src/auth/login.py"],
    depth=2,
    max_tokens=8000
)

# Использование в промпте
prompt = context.to_prompt()
prompt = context.to_prompt(format="markdown")
prompt = context.to_prompt(include_tree=True)

# Impact analysis
impact = ca.analyze_impact(["src/utils.py"])
print(impact.affected_files)
print(impact.suggested_tests)
```

**Критерии приёмки:**
- [ ] API интуитивный
- [ ] Поддержка локального и remote режима
- [ ] Type hints полные

---

### E5-2: SDK Implementation
**Оценка:** 4h | **Приоритет:** P0

**Описание:**
Реализация Python SDK.

**Структура:**
```
src/codex_aura/sdk/
├── __init__.py
├── client.py        # CodexAura class
├── context.py       # Context result wrapper
├── impact.py        # Impact result wrapper
├── formatters.py    # to_prompt implementations
└── exceptions.py
```

**Критерии приёмки:**
- [ ] Все методы реализованы
- [ ] Retry logic для сетевых ошибок
- [ ] Timeout configuration

---

### E5-3: Context Formatters
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Форматирование контекста для разных LLM.

**Форматы:**
```python
class Context:
    def to_prompt(
        self,
        format: Literal["plain", "markdown", "xml"] = "markdown",
        include_tree: bool = False,
        include_edges: bool = False,
        max_chars: int | None = None
    ) -> str:
        ...

# Markdown (default):
"""
## Relevant Code Context

### src/auth/login.py

```python
def login(username: str, password: str) -> User:
    '''Authenticate user and return User object.'''
    user = get_user(username)
    if not verify_password(password, user.password_hash):
        raise AuthenticationError()
    return user
```

Dependencies: `get_user`, `verify_password`
"""

# XML (для Claude):
"""
<context>
  <file path="src/auth/login.py">
    <function name="login" lines="10-25">
      <code>def login(username: str, password: str) -> User:...</code>
      <docstring>Authenticate user and return User object.</docstring>
      <calls>get_user, verify_password</calls>
    </function>
  </file>
</context>
"""
```

**Критерии приёмки:**
- [ ] 3+ форматов
- [ ] Truncation по max_chars
- [ ] Tree view опционально

---

### E5-4: Example: Claude Agent
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Пример интеграции с Claude.

**examples/agents/claude_agent.py:**
```python
from anthropic import Anthropic
from codex_aura import CodexAura

def fix_bug_with_claude(
    repo_path: str,
    bug_description: str,
    file_hint: str | None = None
):
    # Initialize
    ca = CodexAura(repo_path=repo_path)
    anthropic = Anthropic()
    
    # Get context
    context = ca.get_context(
        task=bug_description,
        entry_points=[file_hint] if file_hint else None,
        max_tokens=6000
    )
    
    # Build prompt
    prompt = f"""You are a senior developer fixing a bug.

## Bug Description
{bug_description}

## Relevant Code Context
{context.to_prompt(format="markdown")}

## Instructions
1. Analyze the code and identify the bug
2. Provide a fix with explanation
3. Suggest tests to prevent regression

Respond with the fix."""

    # Call Claude
    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.content[0].text

if __name__ == "__main__":
    fix = fix_bug_with_claude(
        repo_path=".",
        bug_description="JWT tokens are not validated correctly",
        file_hint="src/auth/jwt.py"
    )
    print(fix)
```

**Критерии приёмки:**
- [ ] Пример работает
- [ ] README с инструкциями
- [ ] Показывает token savings

---

### E5-5: Example: OpenAI Agent
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Пример интеграции с OpenAI.

**examples/agents/openai_agent.py:**
```python
from openai import OpenAI
from codex_aura import CodexAura

def code_review_with_gpt(repo_path: str, pr_files: list[str]):
    ca = CodexAura(repo_path=repo_path)
    client = OpenAI()
    
    # Get impact of changed files
    impact = ca.analyze_impact(pr_files)
    
    # Get context for affected area
    context = ca.get_context(
        task="Code review for changes",
        entry_points=pr_files,
        depth=1,
        max_tokens=4000
    )
    
    prompt = f"""Review these code changes.

Changed files: {pr_files}
Affected files: {impact.affected_files}

Context:
{context.to_prompt()}

Provide:
1. Potential issues
2. Suggestions for improvement
3. Security concerns if any"""

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content
```

**Критерии приёмки:**
- [ ] Пример работает
- [ ] Показывает impact analysis

---

### E5-6: Token Usage Benchmark
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Скрипт для измерения экономии токенов.

**examples/benchmarks/token_savings.py:**
```python
import tiktoken
from codex_aura import CodexAura

def benchmark_token_savings(repo_path: str, tasks: list[str]):
    ca = CodexAura(repo_path=repo_path)
    enc = tiktoken.get_encoding("cl100k_base")
    
    results = []
    
    for task in tasks:
        # Full repo context
        full_repo_tokens = count_all_python_files(repo_path, enc)
        
        # Codex Aura context
        context = ca.get_context(task=task, max_tokens=8000)
        ca_tokens = len(enc.encode(context.to_prompt()))
        
        savings = (1 - ca_tokens / full_repo_tokens) * 100
        
        results.append({
            "task": task,
            "full_repo_tokens": full_repo_tokens,
            "codex_aura_tokens": ca_tokens,
            "savings_percent": savings
        })
    
    return results

# Output:
# | Task                  | Full Repo | Codex Aura | Savings |
# |-----------------------|-----------|------------|---------|
# | Fix auth bug          | 125,000   | 3,200      | 97.4%   |
# | Add user endpoint     | 125,000   | 5,100      | 95.9%   |
```

**Критерии приёмки:**
- [ ] Измерение корректное
- [ ] Отчёт в markdown
- [ ] Сравнение на реальных repos

---

### E5-7: Agent Accuracy Test
**Оценка:** 3h | **Приоритет:** P1

**Описание:**
Тест качества ответов агента с Codex Aura vs без.

**Методология:**
1. Подготовить 10 задач (bug fixes, feature additions)
2. Запустить агента с полным репо
3. Запустить агента с Codex Aura контекстом
4. Оценить качество (вручную или автоматически)

**examples/benchmarks/accuracy_test.py:**
```python
TASKS = [
    {
        "description": "Fix: login returns wrong error code",
        "expected_files": ["src/auth/login.py", "src/auth/errors.py"],
        "ground_truth_fix": "...",
    },
    # ... more tasks
]

def run_accuracy_test():
    results = []
    
    for task in TASKS:
        # With Codex Aura
        ca_context = get_codex_aura_context(task)
        ca_result = run_agent(ca_context)
        ca_score = evaluate_result(ca_result, task["ground_truth_fix"])
        
        # Without (full repo or random sample)
        full_context = get_full_repo_context()
        full_result = run_agent(full_context)
        full_score = evaluate_result(full_result, task["ground_truth_fix"])
        
        results.append({
            "task": task["description"],
            "ca_score": ca_score,
            "full_score": full_score,
            "ca_tokens": len(ca_context),
            "full_tokens": len(full_context)
        })
    
    return results
```

**Критерии приёмки:**
- [ ] 10+ тестовых задач
- [ ] Метрика качества определена
- [ ] Результаты документированы

---

### E5-8: SDK Documentation
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Документация по использованию SDK с агентами.

**Страницы:**
- [ ] `docs/sdk/getting-started.md`
- [ ] `docs/sdk/api-reference.md`
- [ ] `docs/sdk/claude-integration.md`
- [ ] `docs/sdk/openai-integration.md`
- [ ] `docs/sdk/best-practices.md`

**Критерии приёмки:**
- [ ] Копируемые примеры
- [ ] Troubleshooting секция
- [ ] API reference полный

---

## E6: 🔧 VS Code Extension (Enhanced)

### E6-1: Full Graph Visualization
**Оценка:** 4h | **Приоритет:** P1

**Описание:**
Интерактивный граф с D3.js/vis.js.

**Функциональность:**
- [ ] Force-directed layout
- [ ] Zoom & Pan
- [ ] Node coloring по типу
- [ ] Edge styling по типу
- [ ] Mini-map для больших графов
- [ ] Search nodes

**Критерии приёмки:**
- [ ] 500+ nodes рендерятся плавно
- [ ] Клик на node показывает детали
- [ ] Filter по типу nodes/edges

---

### E6-2: Node Details Panel
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Панель с полной информацией о выбранном узле.

**Содержимое:**
- Имя и тип
- Путь (кликабельный → открыть файл)
- Signature
- Docstring
- Code preview (syntax highlighted)
- Dependencies list
- Dependents list
- Git blame info
- Change frequency indicator

**Критерии приёмки:**
- [ ] Вся информация отображается
- [ ] Клик по пути открывает файл
- [ ] Code highlighting работает

---

### E6-3: Impact Preview
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Предпросмотр impact при изменении файла.

**Функциональность:**
- Hover на файл в tree view → tooltip с affected files
- Command: "Preview Impact of This File"
- Highlight affected files в graph view
- Badge на файлах с high impact

**Критерии приёмки:**
- [ ] Hover tooltip работает
- [ ] Graph highlighting работает
- [ ] Impact count в sidebar

---

### E6-4: "Get Context for Task" Command
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Команда для получения контекста и копирования в clipboard.

**Flow:**
1. User: Ctrl+Shift+P → "Codex Aura: Get Context"
2. Input box: "Describe your task"
3. Extension вызывает /context API
4. Показывает preview контекста
5. Кнопки: "Copy to Clipboard", "Insert at Cursor", "Open in New File"

**Критерии приёмки:**
- [ ] Task input работает
- [ ] Preview показывается
- [ ] Copy to clipboard работает
- [ ] Format selection (Markdown/XML)

---

### E6-5: Inline Decorations
**Оценка:** 2h | **Приоритет:** P2

**Описание:**
Inline decorations в редакторе.

**Показывать:**
- Количество зависимостей функции (gutter icon)
- "Hot spot" индикатор для часто меняющихся
- Import count над файлом

**Пример:**
```python
# ← 5 dependents | 3 dependencies
def process_order(order_id):  # 🔥 Hot spot
    ...
```

**Критерии приёмки:**
- [ ] Gutter icons работают
- [ ] Hover показывает детали
- [ ] Настраиваемость (on/off)

---

### E6-6: Settings UI
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
UI для настроек расширения.

**Settings:**
```json
{
  "codexAura.serverUrl": "http://localhost:8000",
  "codexAura.autoAnalyze": true,
  "codexAura.showInlineDecorations": true,
  "codexAura.defaultContextDepth": 2,
  "codexAura.defaultMaxTokens": 8000,
  "codexAura.contextFormat": "markdown"
}
```

**Критерии приёмки:**
- [ ] Все settings работают
- [ ] Validation
- [ ] UI в Settings editor

---

### E6-7: Workspace Multi-Root Support
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Поддержка multi-root workspaces.

**Функциональность:**
- Каждый root — отдельный граф
- Переключатель между графами
- Cross-root dependencies (optional)

**Критерии приёмки:**
- [ ] Multi-root workspace работает
- [ ] Selector для активного root

---

### E6-8: Extension Telemetry (Opt-in)
**Оценка:** 2h | **Приоритет:** P2

**Описание:**
Анонимная телеметрия для улучшения extension.

**Собирать (opt-in):**
- Какие команды используются
- Размер графов (node count)
- Errors

**Критерии приёмки:**
- [ ] Opt-in при первом запуске
- [ ] Settings для отключения
- [ ] Privacy policy

---

## E7: ⚙️ GitHub Action (Enhanced)

### E7-1: PR Comment with Impact Analysis
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Комментарий к PR с полным impact analysis.

**Формат комментария:**
```markdown
## 📊 Codex Aura Analysis

### Changed Files
- `src/auth/login.py` (modified)
- `src/utils/helpers.py` (modified)

### Impact Assessment

| Metric | Value |
|--------|-------|
| Directly affected files | 5 |
| Transitively affected | 12 |
| Affected tests | 3 |
| Risk level | ⚠️ Medium |

### Affected Files
<details>
<summary>Show 5 affected files</summary>

- `src/api/auth_router.py` (CALLS login)
- `src/services/user_service.py` (IMPORTS helpers)
- ...

</details>

### Recommended Tests
```bash
pytest tests/test_auth.py tests/test_user_service.py
```
```

**Критерии приёмки:**
- [ ] Комментарий создаётся/обновляется
- [ ] Impact корректный
- [ ] Collapsible для длинных списков

---

### E7-2: Risk-Based PR Blocking
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Опциональная блокировка merge для high-risk PR.

**Inputs:**
```yaml
inputs:
  fail-on-risk:
    description: 'Risk level to fail on (low/medium/high/critical)'
    required: false
    default: 'critical'
```

**Логика:**
- `critical`: > 50% кодовой базы affected
- `high`: > 20% affected
- `medium`: > 10% affected
- `low`: > 5% affected

**Критерии приёмки:**
- [ ] Exit code 1 при превышении
- [ ] Ясное сообщение об ошибке
- [ ] Configurable thresholds

---

### E7-3: Graph Artifact Upload
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Загрузка графа как artifact для скачивания.

```yaml
- uses: codex-aura/analyze-action@v1
  with:
    upload-artifact: true
    artifact-name: 'codex-aura-graph'
    artifact-retention-days: 30
```

**Критерии приёмки:**
- [ ] JSON граф загружается
- [ ] Retention настраивается
- [ ] Ссылка в PR comment

---

### E7-4: Scheduled Analysis
**Оценка:** 2h | **Приоритет:** P2

**Описание:**
Поддержка scheduled runs для tracking трендов.

**Пример использования:**
```yaml
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: codex-aura/analyze-action@v1
        with:
          track-metrics: true
```

**Метрики для трекинга:**
- Total nodes
- Total edges
- Average complexity
- Hot spots count

**Критерии приёмки:**
- [ ] Metrics сохраняются
- [ ] Trend comparison в comment

---

### E7-5: Monorepo Support
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Поддержка анализа отдельных packages в monorepo.

```yaml
- uses: codex-aura/analyze-action@v1
  with:
    paths: |
      packages/auth
      packages/api
      packages/shared
    cross-package-deps: true
```

**Критерии приёмки:**
- [ ] Каждый path анализируется
- [ ] Cross-package dependencies опционально
- [ ] Отдельные comments per package

---

### E7-6: Matrix Strategy Example
**Оценка:** 1h | **Приоритет:** P2

**Описание:**
Документация и пример matrix strategy.

**Пример:**
```yaml
strategy:
  matrix:
    package: [auth, api, frontend]

steps:
  - uses: codex-aura/analyze-action@v1
    with:
      path: packages/${{ matrix.package }}
```

**Критерии приёмки:**
- [ ] Пример работает
- [ ] Документация в README

---

## E8: 📜 MCP Protocol Specification

### E8-1: Protocol Document v1.0
**Оценка:** 3h | **Приоритет:** P0

**Описание:**
Формальная спецификация протокола.

**PROTOCOL.md:**
```markdown
# Codex Aura Protocol Specification v1.0

## Overview
The Codex Aura Protocol defines a standard format for representing
code dependency graphs and APIs for querying them.

## Versioning
- Protocol version: MAJOR.MINOR
- Backward compatible changes: MINOR bump
- Breaking changes: MAJOR bump

## Data Types

### Node
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | yes | Unique identifier |
| type | enum | yes | file, class, function |
| name | string | yes | Entity name |
| path | string | yes | File path |
| lines | [int, int] | no | Start/end lines |
| ... | | | |

### Edge
...

## API Endpoints

### POST /api/v1/context
...

## Extension Points
...
```

**Критерии приёмки:**
- [ ] Все типы данных описаны
- [ ] Все endpoints описаны
- [ ] Versioning policy определена

---

### E8-2: JSON Schema Files
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
JSON Schema для всех типов.

**Файлы:**
- `schemas/node.schema.json`
- `schemas/edge.schema.json`
- `schemas/graph.schema.json`
- `schemas/context-request.schema.json`
- `schemas/context-response.schema.json`

**Критерии приёмки:**
- [ ] Все schemas валидны
- [ ] Pydantic models генерируются из schemas
- [ ] Опубликованы на schema registry (optional)

---

### E8-3: Protocol Compliance Tests
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Тесты на соответствие протоколу.

**tests/protocol/test_compliance.py:**
```python
def test_node_schema_compliance():
    node = create_sample_node()
    validate(node.dict(), load_schema("node.schema.json"))

def test_api_response_compliance():
    response = client.post("/api/v1/context", json={...})
    validate(response.json(), load_schema("context-response.schema.json"))
```

**Критерии приёмки:**
- [ ] Все responses валидируются против schemas
- [ ] CI проверяет compliance

---

### E8-4: Protocol Extension Mechanism
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Механизм расширения протокола (custom fields, custom edge types).

**Пример:**
```json
{
  "id": "...",
  "type": "function",
  "x-custom-field": "value",
  "x-company-specific": {...}
}
```

**Правила:**
- Кастомные поля начинаются с `x-`
- Кастомные edge types начинаются с `CUSTOM_`
- Backwards compatibility гарантируется

**Критерии приёмки:**
- [ ] Extension механизм документирован
- [ ] Примеры кастомных расширений

---

### E8-5: Protocol Changelog
**Оценка:** 1h | **Приоритет:** P1

**Описание:**
Changelog протокола отдельно от кода.

**PROTOCOL-CHANGELOG.md:**
```markdown
# Protocol Changelog

## [1.0.0] - 2024-XX-XX
### Added
- Initial protocol specification
- Node types: file, class, function
- Edge types: IMPORTS, CALLS, EXTENDS
- API endpoints: /context, /graph, /impact
```

**Критерии приёмки:**
- [ ] Changelog ведётся
- [ ] Breaking changes помечены

---

## E9: 📊 Observability & Metrics

### E9-1: Structured Logging
**Оценка:** 2h | **Приоритет:** P0

**Описание:**
Структурированные логи в JSON формате.

**Реализация:**
```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Usage
logger.info(
    "context_request",
    graph_id=graph_id,
    entry_points=entry_points,
    depth=depth,
    result_nodes=len(nodes),
    duration_ms=duration
)
```

**Критерии приёмки:**
- [ ] Все логи в JSON
- [ ] Request ID в каждом логе
- [ ] Configurable log level

---

### E9-2: Prometheus Metrics
**Оценка:** 2h | **Приоритет:** P1

**Описание:**
Экспорт метрик для Prometheus.

**Метрики:**
```python
from prometheus_client import Counter, Histogram

REQUESTS_TOTAL = Counter(
    "codex_aura_requests_total",
    "Total requests",
    ["endpoint", "status"]
)

REQUEST_DURATION = Histogram(
    "codex_aura_request_duration_seconds",
    "Request duration",
    ["endpoint"]
)

GRAPH_SIZE = Gauge(
    "codex_aura_graph_nodes_total",
    "Number of nodes in graph",
    ["graph_id"]
)
```

**Endpoint:**
```
GET /metrics
```

**Критерии приёмки:**
- [ ] /metrics endpoint работает
- [ ] Все ключевые метрики есть
- [ ] Grafana dashboard template

---

### E9-3: Health Check Improvements
**Оценка:** 1h | **Приоритет:** P0

**Описание:**
Улучшенные health checks.

**Endpoints:**
```http
GET /health       # Quick liveness
GET /ready        # Full readiness (DB connection, etc.)
GET /health/deep  # Deep check (analyze sample file)
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "ok",
    "analyzer": "ok",
    "disk_space": "ok"
  },
  "uptime_seconds": 3600
}
```

**Критерии приёмки:**
- [ ] Deep check проверяет всё
- [ ] Kubernetes probes работают

---

### E9-4: Request Tracing
**Оценка:** 2h | **Приоритет:** P2

**Описание:**
Distributed tracing support.

**Реализация:**
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(app)

tracer = trace.get_tracer(__name__)

async def get_context(...):
    with tracer.start_as_current_span("get_context") as span:
        span.set_attribute("graph_id", graph_id)
        span.set_attribute("depth", depth)
        ...
```

**Критерии приёмки:**
- [ ] Traces exportируются
- [ ] Jaeger/Zipkin интеграция

---

### E9-5: Usage Analytics (Opt-in)
**Оценка:** 1h | **Приоритет:** P2

**Описание:**
Анонимная аналитика использования.

**Собирать:**
- Количество анализов
- Размеры графов
- Популярные языки
- Feature usage

**Критерии приёмки:**
- [ ] Opt-in only
- [ ] Анонимизация
- [ ] Можно полностью отключить

---

## ✅ Definition of Done (Phase 1.5)

Phase 1.5 завершена когда:

- [ ] Plugin system работает и документирован
- [ ] Config file поддерживается
- [ ] Git integration полный (blame, frequency)
- [ ] Security audit пройден
- [ ] AI Agent SDK работает с Claude и OpenAI
- [ ] Token savings benchmark показывает >70%
- [ ] VS Code extension имеет graph visualization
- [ ] GitHub Action делает impact analysis в PR
- [ ] Protocol specification v1.0 опубликована
- [ ] Metrics endpoint работает
- [ ] Все examples проходят