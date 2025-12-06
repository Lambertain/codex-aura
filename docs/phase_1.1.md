# 📋 Фаза 1: Open Source MVP — Детальный План Задач

**Длительность:** 6-8 недель
**Цель:** Публичный релиз open source ядра
**Результат:** `pip install codex-aura` + HTTP Server + VS Code Extension

---

## 📊 Обзор эпиков

| # | Эпик | Задач | Оценка | Приоритет |
|---|------|-------|--------|-----------|
| E1 | Расширение анализатора | 10 | 24h | P0 |
| E2 | Graph Storage (SQLite) | 6 | 12h | P0 |
| E3 | HTTP Server (FastAPI) | 8 | 16h | P0 |
| E4 | API Endpoints | 9 | 20h | P0 |
| E5 | VS Code Extension | 8 | 20h | P1 |
| E6 | GitHub Action | 5 | 8h | P1 |
| E7 | Документация | 7 | 12h | P0 |
| E8 | Тестирование | 6 | 16h | P0 |
| E9 | Публикация | 5 | 8h | P0 |
| | **ИТОГО** | **64** | **~136h** | |

---

## E1: 🔍 Расширение Анализатора

### E1-1: Рефакторинг архитектуры анализатора
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** Phase 0

**Описание:**
Подготовить анализатор к поддержке нескольких типов рёбер.

**Действия:**
- [ ] Выделить `EdgeExtractor` как отдельный компонент
- [ ] Создать `EdgeType` enum с типами рёбер
- [ ] Реализовать паттерн Registry для edge extractors
- [ ] Добавить конфигурацию включения/выключения типов

**Структура:**
```
src/codex_aura/analyzer/
├── __init__.py
├── base.py
├── python/
│   ├── __init__.py
│   ├── analyzer.py        # PythonAnalyzer
│   ├── node_extractors.py # Файлы, классы, функции
│   └── edge_extractors/
│       ├── __init__.py
│       ├── base.py        # BaseEdgeExtractor
│       ├── imports.py     # ImportsExtractor
│       ├── calls.py       # CallsExtractor
│       └── extends.py     # ExtendsExtractor
└── utils.py
```

**Критерии приёмки:**
- [ ] Каждый тип ребра — отдельный extractor
- [ ] Extractors можно включать/выключать через конфиг
- [ ] Существующие тесты проходят

---

### E1-2: CALLS Edge Extractor — базовая реализация
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E1-1

**Описание:**
Обнаружение вызовов функций внутри функций.

**Что детектируем:**
```python
def process_order(order_id):
    order = get_order(order_id)        # CALLS: process_order -> get_order
    validate_order(order)               # CALLS: process_order -> validate_order
    result = calculate_total(order)     # CALLS: process_order -> calculate_total
    send_notification(order.user_id)    # CALLS: process_order -> send_notification
    return result
```

**AST Nodes для анализа:**
- `ast.Call` — вызов функции
- `ast.Attribute` — вызов метода (obj.method())
- `ast.Name` — имя вызываемой функции

**API:**
```python
class CallsExtractor(BaseEdgeExtractor):
    def extract(
        self, 
        tree: ast.AST, 
        file_path: Path,
        known_functions: dict[str, Node]
    ) -> list[Edge]:
        """Extract function call edges."""
```

**Критерии приёмки:**
- [ ] Детектируются прямые вызовы функций
- [ ] Детектируются вызовы методов
- [ ] Игнорируются вызовы built-in функций (len, print, etc.)

---

### E1-3: CALLS Edge — разрешение имён
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E1-2

**Описание:**
Связывание вызова с определением функции.

**Сложные случаи:**
```python
from utils import helper           # helper определён в другом файле
from services import UserService   # метод класса

def main():
    helper()                        # -> utils.py::helper
    svc = UserService()
    svc.create_user()               # -> services.py::UserService::create_user
    
    local_func()                    # -> current_file::local_func (локальная)
```

**Действия:**
- [ ] Построить scope chain для каждой функции
- [ ] Отслеживать imports и их aliases
- [ ] Резолвить method calls через тип объекта (если возможно)
- [ ] Fallback: создавать "unresolved" edge

**Структура Edge:**
```json
{
  "source": "src/main.py::main",
  "target": "src/utils.py::helper",
  "type": "CALLS",
  "metadata": {
    "line": 5,
    "resolved": true
  }
}
```

**Критерии приёмки:**
- [ ] Локальные функции резолвятся
- [ ] Импортированные функции резолвятся
- [ ] Нерезолвленные помечаются как `resolved: false`

---

### E1-4: EXTENDS Edge Extractor
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E1-1

**Описание:**
Обнаружение наследования классов.

**Что детектируем:**
```python
class Animal:                          # базовый класс
    pass

class Dog(Animal):                     # EXTENDS: Dog -> Animal
    pass

class ServiceDog(Dog, Trainable):      # EXTENDS: ServiceDog -> Dog
                                       # EXTENDS: ServiceDog -> Trainable (если в проекте)
    pass

from abc import ABC
class MyInterface(ABC):                # EXTENDS: MyInterface -> ABC (внешний, игнорируем)
    pass
```

**API:**
```python
class ExtendsExtractor(BaseEdgeExtractor):
    def extract(
        self,
        tree: ast.AST,
        file_path: Path,
        known_classes: dict[str, Node]
    ) -> list[Edge]:
        """Extract inheritance edges."""
```

**Критерии приёмки:**
- [ ] Одиночное наследование детектируется
- [ ] Множественное наследование детектируется
- [ ] Внешние базовые классы (ABC, Exception) игнорируются

---

### E1-5: EXTENDS Edge — разрешение имён
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E1-4

**Описание:**
Связывание наследования с определением базового класса.

**Случаи:**
```python
# file: models/user.py
from .base import BaseModel            # импорт базового класса

class User(BaseModel):                  # -> models/base.py::BaseModel
    pass

class Admin(User):                      # -> models/user.py::User (тот же файл)
    pass
```

**Критерии приёмки:**
- [ ] Локальные классы резолвятся
- [ ] Импортированные классы резолвятся
- [ ] Generic типы (List, Dict) игнорируются

---

### E1-6: IMPLEMENTS Edge Extractor (опционально)
**Оценка:** 2h | **Приоритет:** P2 | **Зависимости:** E1-4

**Описание:**
Обнаружение реализации Protocol/ABC интерфейсов.

**Что детектируем:**
```python
from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:                          # IMPLEMENTS: Circle -> Drawable
    def draw(self) -> None:            # (если реализует все методы Protocol)
        pass
```

**Критерии приёмки:**
- [ ] ABC наследование детектируется как IMPLEMENTS
- [ ] Protocol реализация детектируется (duck typing analysis)

---

### E1-7: Метаданные узлов — расширение
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E1-2

**Описание:**
Добавить дополнительные метаданные в Node.

**Новые поля:**
```python
class Node(BaseModel):
    # ... существующие поля ...
    
    # Новые:
    signature: str | None          # "def func(a: int, b: str) -> bool"
    decorators: list[str]          # ["@staticmethod", "@cache"]
    is_async: bool                 # async def
    is_private: bool               # starts with _
    complexity: int | None         # cyclomatic complexity (опционально)
    parameters: list[Parameter]    # список параметров функции
```

**Критерии приёмки:**
- [ ] Сигнатура функций/методов извлекается
- [ ] Декораторы извлекаются
- [ ] async функции помечаются

---

### E1-8: Cyclomatic Complexity (опционально)
**Оценка:** 2h | **Приоритет:** P2 | **Зависимости:** E1-7

**Описание:**
Вычисление цикломатической сложности функций.

**Формула:**
```
CC = 1 + if + elif + for + while + except + and + or + ternary
```

**Действия:**
- [ ] Использовать библиотеку `radon` или реализовать свой visitor
- [ ] Добавить поле `complexity` в Node
- [ ] Добавить флаг `--complexity` в CLI

**Критерии приёмки:**
- [ ] Complexity вычисляется для функций
- [ ] Значения соответствуют radon

---

### E1-9: Интеграция всех extractors
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E1-3, E1-5

**Описание:**
Объединить все extractors в единый pipeline.

**Конфигурация:**
```python
# Через CLI
codex-aura analyze . --edges imports,calls,extends

# Через Python API
analyzer = PythonAnalyzer(
    edge_types=[EdgeType.IMPORTS, EdgeType.CALLS, EdgeType.EXTENDS]
)
```

**Критерии приёмки:**
- [ ] Все edge types работают вместе
- [ ] Можно выбирать нужные типы
- [ ] Статистика показывает breakdown по типам

---

### E1-10: Производительность анализатора
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E1-9

**Описание:**
Оптимизация скорости анализа.

**Действия:**
- [ ] Профилирование на большом репозитории (Flask, Django)
- [ ] Кэширование AST parse результатов
- [ ] Параллельный анализ файлов (multiprocessing)
- [ ] Ленивая загрузка edge extractors

**Цели:**
- 100K LOC < 30 сек
- 10K LOC < 5 сек

**Критерии приёмки:**
- [ ] Benchmark скрипт показывает улучшение
- [ ] Целевые метрики достигнуты

---

## E2: 💾 Graph Storage (SQLite)

### E2-1: Дизайн схемы SQLite
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E1-9

**Описание:**
Спроектировать SQLite схему для хранения графа.

**Схема:**
```sql
-- Метаданные графа
CREATE TABLE graphs (
    id TEXT PRIMARY KEY,
    repo_path TEXT NOT NULL,
    repo_name TEXT,
    sha TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    node_count INTEGER,
    edge_count INTEGER
);

-- Узлы
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    graph_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- file, class, function
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    signature TEXT,
    docstring TEXT,
    is_async BOOLEAN DEFAULT FALSE,
    is_private BOOLEAN DEFAULT FALSE,
    complexity INTEGER,
    metadata JSON,
    FOREIGN KEY (graph_id) REFERENCES graphs(id)
);

-- Рёбра
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    graph_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    type TEXT NOT NULL,  -- IMPORTS, CALLS, EXTENDS
    line INTEGER,
    resolved BOOLEAN DEFAULT TRUE,
    metadata JSON,
    FOREIGN KEY (graph_id) REFERENCES graphs(id),
    FOREIGN KEY (source_id) REFERENCES nodes(id),
    FOREIGN KEY (target_id) REFERENCES nodes(id)
);

-- Индексы
CREATE INDEX idx_nodes_graph ON nodes(graph_id);
CREATE INDEX idx_nodes_path ON nodes(path);
CREATE INDEX idx_edges_graph ON edges(graph_id);
CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_edges_type ON edges(type);
```

**Критерии приёмки:**
- [ ] Схема поддерживает все типы узлов и рёбер
- [ ] Индексы для частых запросов

---

### E2-2: Repository pattern для storage
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E2-1

**Описание:**
Абстракция над storage для возможности замены.

**Интерфейс:**
```python
class GraphRepository(Protocol):
    def save(self, graph: Graph) -> str:
        """Save graph and return ID."""
        
    def load(self, graph_id: str) -> Graph | None:
        """Load graph by ID."""
        
    def find_by_repo(self, repo_path: str) -> list[GraphMeta]:
        """Find all graphs for repository."""
        
    def delete(self, graph_id: str) -> bool:
        """Delete graph."""
```

**Реализации:**
```
src/codex_aura/storage/
├── __init__.py
├── base.py          # Protocol
├── sqlite.py        # SQLiteGraphRepository
├── json_file.py     # JSONFileRepository (для совместимости)
└── memory.py        # InMemoryRepository (для тестов)
```

**Критерии приёмки:**
- [ ] SQLite реализация работает
- [ ] JSON файл реализация для обратной совместимости
- [ ] Легко добавить новые storage backends

---

### E2-3: SQLite Repository реализация
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E2-2

**Описание:**
Полная реализация SQLite storage.

**API:**
```python
class SQLiteGraphRepository(GraphRepository):
    def __init__(self, db_path: Path = Path(".codex-aura/graphs.db")):
        self.db_path = db_path
        self._init_db()
    
    def save(self, graph: Graph) -> str:
        # Транзакция: insert graph, nodes, edges
        
    def load(self, graph_id: str) -> Graph | None:
        # JOIN запрос + сборка Graph объекта
```

**Критерии приёмки:**
- [ ] CRUD операции работают
- [ ] Транзакции атомарны
- [ ] Большой граф (10K nodes) сохраняется < 5 сек

---

### E2-4: Query методы для графа
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E2-3

**Описание:**
Методы для запросов по графу.

**API:**
```python
class SQLiteGraphRepository:
    # ... save/load ...
    
    def get_node(self, graph_id: str, node_id: str) -> Node | None:
        """Get single node."""
        
    def get_edges_from(self, graph_id: str, node_id: str) -> list[Edge]:
        """Get outgoing edges from node."""
        
    def get_edges_to(self, graph_id: str, node_id: str) -> list[Edge]:
        """Get incoming edges to node."""
        
    def find_nodes(
        self, 
        graph_id: str,
        type: NodeType | None = None,
        path_pattern: str | None = None
    ) -> list[Node]:
        """Search nodes with filters."""
        
    def get_dependencies(
        self,
        graph_id: str,
        node_id: str,
        depth: int = 1,
        edge_types: list[EdgeType] | None = None
    ) -> list[Node]:
        """Get transitive dependencies."""
```

**Критерии приёмки:**
- [ ] Все query методы работают
- [ ] depth параметр для transitive queries
- [ ] Фильтрация по edge type

---

### E2-5: Миграции схемы
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** E2-3

**Описание:**
Система миграций для эволюции схемы.

**Подход:**
```python
MIGRATIONS = [
    ("001_initial", """
        CREATE TABLE graphs (...);
        CREATE TABLE nodes (...);
        CREATE TABLE edges (...);
    """),
    ("002_add_complexity", """
        ALTER TABLE nodes ADD COLUMN complexity INTEGER;
    """),
]

def migrate(db_path: Path):
    """Apply pending migrations."""
```

**Критерии приёмки:**
- [ ] Миграции применяются автоматически
- [ ] Трекинг применённых миграций
- [ ] Rollback (опционально)

---

### E2-6: CLI интеграция с SQLite
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E2-3

**Описание:**
Обновить CLI для работы с SQLite.

**Новые опции:**
```bash
# Сохранить в SQLite (по умолчанию)
codex-aura analyze .

# Сохранить в JSON (legacy)
codex-aura analyze . --format json --output graph.json

# Указать путь к БД
codex-aura analyze . --db ~/.codex-aura/my-project.db

# Просмотр сохранённых графов
codex-aura list
codex-aura list --repo /path/to/repo

# Удаление
codex-aura delete <graph_id>
```

**Критерии приёмки:**
- [ ] SQLite — storage по умолчанию
- [ ] JSON export всё ещё работает
- [ ] Команды list/delete работают

---

## E3: 🌐 HTTP Server (FastAPI)

### E3-1: Базовая структура сервера
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E2-4

**Описание:**
Создать FastAPI приложение.

**Структура:**
```
src/codex_aura/server/
├── __init__.py
├── app.py           # FastAPI app factory
├── config.py        # Settings (pydantic-settings)
├── routes/
│   ├── __init__.py
│   ├── health.py    # /health, /ready
│   ├── graph.py     # /api/v1/graph/*
│   └── context.py   # /api/v1/context
├── middleware/
│   ├── __init__.py
│   ├── logging.py
│   └── errors.py
├── schemas/
│   ├── __init__.py
│   ├── requests.py
│   └── responses.py
└── dependencies.py  # DI for repository, etc.
```

**app.py:**
```python
from fastapi import FastAPI
from codex_aura.server.routes import health, graph, context

def create_app() -> FastAPI:
    app = FastAPI(
        title="Codex Aura API",
        version="0.1.0",
        description="Code context for AI agents"
    )
    
    app.include_router(health.router)
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(context.router, prefix="/api/v1")
    
    return app
```

**Критерии приёмки:**
- [ ] Сервер запускается
- [ ] OpenAPI docs доступны на /docs
- [ ] Структура модульная

---

### E3-2: Конфигурация сервера
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E3-1

**Описание:**
Настройка через environment variables.

**Config:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Storage
    db_path: Path = Path(".codex-aura/graphs.db")
    
    # Limits
    max_context_nodes: int = 100
    max_request_size: int = 10_000_000  # 10MB
    
    class Config:
        env_prefix = "CODEX_AURA_"
```

**Использование:**
```bash
export CODEX_AURA_PORT=9000
export CODEX_AURA_DB_PATH=/data/graphs.db
codex-aura serve
```

**Критерии приёмки:**
- [ ] Все настройки через env vars
- [ ] Разумные defaults
- [ ] Валидация при старте

---

### E3-3: Dependency Injection
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E3-2

**Описание:**
Настроить DI для репозитория и сервисов.

**dependencies.py:**
```python
from functools import lru_cache
from fastapi import Depends

@lru_cache
def get_settings() -> Settings:
    return Settings()

def get_repository(
    settings: Settings = Depends(get_settings)
) -> GraphRepository:
    return SQLiteGraphRepository(settings.db_path)

def get_context_service(
    repo: GraphRepository = Depends(get_repository)
) -> ContextService:
    return ContextService(repo)
```

**Критерии приёмки:**
- [ ] Repository инжектится в routes
- [ ] Легко мокать в тестах

---

### E3-4: Error Handling Middleware
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E3-1

**Описание:**
Унифицированная обработка ошибок.

**Формат ошибки:**
```json
{
  "error": {
    "code": "GRAPH_NOT_FOUND",
    "message": "Graph with ID 'xxx' not found",
    "details": {
      "graph_id": "xxx"
    }
  }
}
```

**Exceptions:**
```python
class CodexAuraError(Exception):
    code: str
    status_code: int

class GraphNotFoundError(CodexAuraError):
    code = "GRAPH_NOT_FOUND"
    status_code = 404

class InvalidRequestError(CodexAuraError):
    code = "INVALID_REQUEST"
    status_code = 400
```

**Критерии приёмки:**
- [ ] Все ошибки в едином формате
- [ ] HTTP status codes корректные
- [ ] Stack trace только в debug mode

---

### E3-5: Request Logging Middleware
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** E3-1

**Описание:**
Логирование всех запросов.

**Формат лога:**
```
2024-01-15 10:30:00 INFO  [req_abc123] POST /api/v1/context 200 150ms
2024-01-15 10:30:01 WARN  [req_def456] GET /api/v1/graph/xxx 404 5ms
```

**Критерии приёмки:**
- [ ] Каждый запрос логируется
- [ ] Request ID для трейсинга
- [ ] Duration измеряется

---

### E3-6: CORS настройка
**Оценка:** 30min | **Приоритет:** P0 | **Зависимости:** E3-1

**Описание:**
Настройка CORS для работы с VS Code extension.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production ограничить
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Критерии приёмки:**
- [ ] VS Code extension может делать запросы
- [ ] Настраиваемый список origins

---

### E3-7: CLI команда `serve`
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E3-2

**Описание:**
Добавить команду запуска сервера.

```bash
# Простой запуск
codex-aura serve

# С опциями
codex-aura serve --port 9000 --host 127.0.0.1

# С auto-reload для разработки
codex-aura serve --reload
```

**Реализация:**
```python
@cli.command()
def serve(
    port: int = 8000,
    host: str = "0.0.0.0",
    reload: bool = False
):
    import uvicorn
    uvicorn.run(
        "codex_aura.server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True
    )
```

**Критерии приёмки:**
- [ ] Сервер запускается через CLI
- [ ] Hot reload работает

---

### E3-8: Docker образ
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E3-7

**Описание:**
Создать Dockerfile для сервера.

**Dockerfile:**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install .

# Copy source
COPY src/ src/

# Create data directory
RUN mkdir -p /data

ENV CODEX_AURA_DB_PATH=/data/graphs.db

EXPOSE 8000

CMD ["codex-aura", "serve", "--host", "0.0.0.0"]
```

**docker-compose.yml:**
```yaml
version: "3.8"
services:
  codex-aura:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
```

**Критерии приёмки:**
- [ ] Docker image собирается
- [ ] Контейнер запускается
- [ ] Volume для persistence