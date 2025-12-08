# 📋 Фаза 1: Open Source MVP — Часть 2

## E4: 🔌 API Endpoints

### E4-1: Health & Ready endpoints
**Оценка:** 30min | **Приоритет:** P0 | **Зависимости:** E3-1

**Endpoints:**
```http
GET /health          # Сервер жив
GET /ready           # Сервер готов принимать запросы
GET /api/v1/info     # Информация о сервере
```

**Response /api/v1/info:**
```json
{
  "version": "0.1.0",
  "supported_languages": ["python"],
  "supported_edge_types": ["IMPORTS", "CALLS", "EXTENDS"],
  "storage_backend": "sqlite"
}
```

**Критерии приёмки:**
- [ ] Kubernetes liveness/readiness probes работают
- [ ] Info endpoint возвращает capabilities

---

### E4-2: POST /api/v1/analyze
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E3-3

**Описание:**
Запуск анализа репозитория через API.

**Request:**
```http
POST /api/v1/analyze
Content-Type: application/json

{
  "repo_path": "/path/to/repo",
  "edge_types": ["IMPORTS", "CALLS", "EXTENDS"],
  "options": {
    "include_complexity": true,
    "ignore_patterns": ["**/tests/**", "**/__pycache__/**"]
  }
}
```

**Response:**
```json
{
  "graph_id": "g_abc123",
  "status": "completed",
  "stats": {
    "files": 42,
    "classes": 15,
    "functions": 128,
    "edges": {
      "IMPORTS": 67,
      "CALLS": 234,
      "EXTENDS": 12
    }
  },
  "duration_ms": 1250
}
```

**Критерии приёмки:**
- [ ] Анализ запускается
- [ ] Граф сохраняется в storage
- [ ] Возвращается graph_id

---

### E4-3: GET /api/v1/graphs
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E4-2

**Описание:**
Список всех графов.

**Request:**
```http
GET /api/v1/graphs
GET /api/v1/graphs?repo_path=/path/to/repo
```

**Response:**
```json
{
  "graphs": [
    {
      "id": "g_abc123",
      "repo_name": "my-project",
      "repo_path": "/path/to/repo",
      "sha": "abc123...",
      "created_at": "2024-01-15T10:30:00Z",
      "node_count": 185,
      "edge_count": 313
    }
  ]
}
```

**Критерии приёмки:**
- [ ] Список графов возвращается
- [ ] Фильтрация по repo_path

---

### E4-4: GET /api/v1/graph/{graph_id}
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E4-2

**Описание:**
Получение полного графа.

**Response:**
```json
{
  "id": "g_abc123",
  "repo_name": "my-project",
  "created_at": "2024-01-15T10:30:00Z",
  "nodes": [...],
  "edges": [...],
  "stats": {...}
}
```

**Query params:**
- `include_code=true` — включить код узлов
- `node_types=file,class` — фильтр по типам
- `edge_types=IMPORTS` — фильтр по рёбрам

**Критерии приёмки:**
- [ ] Полный граф возвращается
- [ ] Фильтрация работает
- [ ] 404 для несуществующего

---

### E4-5: GET /api/v1/graph/{graph_id}/node/{node_id}
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E4-4

**Описание:**
Получение информации об узле.

**Response:**
```json
{
  "node": {
    "id": "src/auth/jwt.py::validate_token",
    "type": "function",
    "name": "validate_token",
    "path": "src/auth/jwt.py",
    "lines": [45, 89],
    "signature": "def validate_token(token: str) -> Claims",
    "docstring": "Validates JWT token...",
    "code": "def validate_token(token: str) -> Claims:\n    ..."
  },
  "edges": {
    "incoming": [
      {"source": "src/api/auth.py::login", "type": "CALLS"}
    ],
    "outgoing": [
      {"target": "src/utils/crypto.py::decode_jwt", "type": "CALLS"}
    ]
  }
}
```

**Критерии приёмки:**
- [ ] Узел с кодом возвращается
- [ ] Входящие/исходящие рёбра включены

---

### E4-6: GET /api/v1/graph/{graph_id}/dependencies
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E4-5

**Описание:**
Получение зависимостей файла/функции.

**Request:**
```http
GET /api/v1/graph/{graph_id}/dependencies?node_id={id}&depth=2&direction=both
```

**Params:**
- `node_id` — ID узла
- `depth` — глубина обхода (1-5)
- `direction` — incoming, outgoing, both
- `edge_types` — фильтр типов рёбер

**Response:**
```json
{
  "root": "src/services/order.py::create_order",
  "depth": 2,
  "nodes": [...],
  "edges": [...]
}
```

**Критерии приёмки:**
- [ ] Транзитивные зависимости работают
- [ ] Depth ограничивает глубину
- [ ] Циклы обрабатываются корректно

---

### E4-7: POST /api/v1/context (Basic)
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E4-6

**Описание:**
Базовая версия context API (без семантики).

**Request:**
```http
POST /api/v1/context
Content-Type: application/json

{
  "graph_id": "g_abc123",
  "entry_points": ["src/services/order.py"],
  "depth": 2,
  "include_code": true,
  "max_nodes": 50
}
```

**Response:**
```json
{
  "context_nodes": [
    {
      "id": "src/services/order.py::create_order",
      "type": "function",
      "path": "src/services/order.py",
      "code": "...",
      "relevance": 1.0
    },
    {
      "id": "src/repositories/order_repo.py::save",
      "type": "function",
      "relevance": 0.8
    }
  ],
  "total_nodes": 23,
  "truncated": false
}
```

**Алгоритм (Basic):**
1. Начать с entry_points
2. BFS по графу до depth
3. Сортировать по расстоянию от entry
4. Ограничить max_nodes

**Критерии приёмки:**
- [ ] BFS обход работает
- [ ] Код узлов включается
- [ ] Ограничение по количеству

---

### E4-8: GET /api/v1/graph/{graph_id}/impact
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E4-6

**Описание:**
Базовый impact analysis.

**Request:**
```http
GET /api/v1/graph/{graph_id}/impact?files=src/utils.py,src/models/user.py
```

**Response:**
```json
{
  "changed_files": ["src/utils.py", "src/models/user.py"],
  "affected_files": [
    {
      "path": "src/services/user_service.py",
      "impact_type": "direct",
      "edges": ["IMPORTS", "CALLS"]
    },
    {
      "path": "src/api/users.py",
      "impact_type": "transitive",
      "distance": 2
    }
  ],
  "affected_tests": [
    "tests/test_user_service.py"
  ]
}
```

**Критерии приёмки:**
- [ ] Direct impact определяется
- [ ] Transitive impact до depth=3
- [ ] Тесты идентифицируются

---

### E4-9: DELETE /api/v1/graph/{graph_id}
**Оценка:** 30min | **Приоритет:** P1 | **Зависимости:** E4-3

**Описание:**
Удаление графа.

**Response:**
```json
{
  "deleted": true,
  "graph_id": "g_abc123"
}
```

**Критерии приёмки:**
- [ ] Граф удаляется
- [ ] 404 для несуществующего

---

## E5: 🔧 VS Code Extension

### E5-1: Scaffold расширения
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** —

**Описание:**
Создать базовую структуру VS Code extension.

**Структура:**
```
vscode-codex-aura/
├── package.json
├── tsconfig.json
├── src/
│   ├── extension.ts      # Entry point
│   ├── api/
│   │   └── client.ts     # API client
│   ├── views/
│   │   ├── graphView.ts  # WebView для графа
│   │   └── nodeView.ts   # Panel с деталями
│   └── commands/
│       └── commands.ts
├── media/
│   └── graph.css
└── README.md
```

**package.json (ключевое):**
```json
{
  "name": "codex-aura",
  "displayName": "Codex Aura",
  "description": "Code context visualization",
  "version": "0.1.0",
  "engines": {"vscode": "^1.85.0"},
  "categories": ["Other"],
  "activationEvents": ["onCommand:codexAura.showGraph"],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      {"command": "codexAura.showGraph", "title": "Show Code Graph"},
      {"command": "codexAura.analyze", "title": "Analyze Workspace"}
    ],
    "configuration": {
      "title": "Codex Aura",
      "properties": {
        "codexAura.serverUrl": {
          "type": "string",
          "default": "http://localhost:8000"
        }
      }
    }
  }
}
```

**Критерии приёмки:**
- [ ] Extension компилируется
- [ ] Можно установить в VS Code
- [ ] Команды появляются в Command Palette

---

### E5-2: API Client
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E5-1, E4-4

**Описание:**
TypeScript клиент для Codex Aura API.

**client.ts:**
```typescript
export class CodexAuraClient {
  constructor(private baseUrl: string) {}
  
  async getGraphs(): Promise<Graph[]> {
    const resp = await fetch(`${this.baseUrl}/api/v1/graphs`);
    return resp.json();
  }
  
  async getGraph(graphId: string): Promise<Graph> {
    const resp = await fetch(`${this.baseUrl}/api/v1/graph/${graphId}`);
    return resp.json();
  }
  
  async getNode(graphId: string, nodeId: string): Promise<NodeDetails> {
    const resp = await fetch(
      `${this.baseUrl}/api/v1/graph/${graphId}/node/${encodeURIComponent(nodeId)}`
    );
    return resp.json();
  }
  
  async getDependencies(graphId: string, nodeId: string, depth: number): Promise<SubGraph> {
    // ...
  }
}
```

**Критерии приёмки:**
- [ ] Все API методы реализованы
- [ ] Error handling
- [ ] Типизация полная

---

### E5-3: Graph Visualization (WebView)
**Оценка:** 4h | **Приоритет:** P1 | **Зависимости:** E5-2

**Описание:**
Визуализация графа с использованием D3.js или vis.js.

**Функциональность:**
- [ ] Отображение узлов с иконками по типу
- [ ] Рёбра с разными цветами по типу
- [ ] Zoom & Pan
- [ ] Клик на узел → показать детали
- [ ] Highlight зависимостей при наведении

**Реализация:**
```typescript
// graphView.ts
export class GraphViewProvider implements vscode.WebviewViewProvider {
  resolveWebviewView(webviewView: vscode.WebviewView) {
    webviewView.webview.html = this.getHtmlForWebview(webviewView.webview);
    
    // Handle messages from webview
    webviewView.webview.onDidReceiveMessage(message => {
      if (message.command === 'nodeClicked') {
        this.showNodeDetails(message.nodeId);
      }
    });
  }
  
  private getHtmlForWebview(webview: vscode.Webview): string {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <script src="https://d3js.org/d3.v7.min.js"></script>
      </head>
      <body>
        <div id="graph"></div>
        <script>
          // D3 force-directed graph
        </script>
      </body>
      </html>
    `;
  }
}
```

**Критерии приёмки:**
- [ ] Граф рендерится
- [ ] Интерактивность работает
- [ ] Производительность на 200+ узлах

---

### E5-4: Node Details Panel
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E5-3

**Описание:**
Панель с деталями выбранного узла.

**Отображает:**
- Имя и тип
- Путь к файлу (кликабельный)
- Docstring
- Сигнатура
- Список зависимостей
- Код (syntax highlighted)

**Критерии приёмки:**
- [ ] Клик на узел открывает панель
- [ ] Клик на путь открывает файл
- [ ] Код с подсветкой

---

### E5-5: Команда "Analyze Workspace"
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E5-2

**Описание:**
Запуск анализа текущего workspace.

**Flow:**
1. Пользователь запускает команду
2. Extension вызывает POST /api/v1/analyze
3. Показывает progress
4. По завершению открывает граф

```typescript
async function analyzeWorkspace() {
  const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
  if (!workspaceFolder) {
    vscode.window.showErrorMessage('No workspace open');
    return;
  }
  
  await vscode.window.withProgress({
    location: vscode.ProgressLocation.Notification,
    title: "Analyzing codebase...",
  }, async () => {
    const result = await client.analyze(workspaceFolder.uri.fsPath);
    vscode.commands.executeCommand('codexAura.showGraph', result.graph_id);
  });
}
```

**Критерии приёмки:**
- [ ] Анализ запускается
- [ ] Progress отображается
- [ ] Результат открывается

---

### E5-6: "Show Dependencies" для текущего файла
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E5-3

**Описание:**
Показать зависимости для активного файла.

**Context menu:**
- Right-click на файл → "Show Dependencies"
- Right-click на функцию → "Show Function Dependencies"

**Критерии приёмки:**
- [ ] Контекстное меню работает
- [ ] Граф фокусируется на выбранном узле
- [ ] Highlight связанных узлов

---

### E5-7: Status Bar Item
**Оценка:** 1h | **Приоритет:** P2 | **Зависимости:** E5-2

**Описание:**
Индикатор статуса в status bar.

**Состояния:**
- `$(database) Codex Aura: Ready` — сервер доступен
- `$(warning) Codex Aura: Not Connected` — сервер недоступен
- `$(sync~spin) Analyzing...` — идёт анализ

**Критерии приёмки:**
- [ ] Статус отображается
- [ ] Клик открывает настройки

---

### E5-8: Публикация в Marketplace
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E5-1-E5-7

**Описание:**
Подготовка и публикация в VS Code Marketplace.

**Действия:**
- [ ] Создать publisher аккаунт
- [ ] Добавить иконку и README
- [ ] Добавить screenshots
- [ ] Настроить CI для публикации
- [ ] Опубликовать

**Критерии приёмки:**
- [ ] Extension доступен в Marketplace
- [ ] README с инструкциями

---

## E6: ⚙️ GitHub Action

### E6-1: Scaffold Action
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** —

**Описание:**
Создать базовую структуру GitHub Action.

**Структура:**
```
github-action-codex-aura/
├── action.yml
├── Dockerfile
├── entrypoint.sh
└── README.md
```

**action.yml:**
```yaml
name: 'Codex Aura Analyze'
description: 'Analyze codebase and generate dependency graph'
branding:
  icon: 'git-branch'
  color: 'purple'

inputs:
  path:
    description: 'Path to analyze'
    required: false
    default: '.'
  edge-types:
    description: 'Edge types to extract'
    required: false
    default: 'imports,calls,extends'
  output:
    description: 'Output file path'
    required: false
    default: 'codex-aura-graph.json'

outputs:
  graph-file:
    description: 'Path to generated graph file'
  node-count:
    description: 'Number of nodes in graph'
  edge-count:
    description: 'Number of edges in graph'

runs:
  using: 'docker'
  image: 'Dockerfile'
  args:
    - ${{ inputs.path }}
    - ${{ inputs.edge-types }}
    - ${{ inputs.output }}
```

**Критерии приёмки:**
- [ ] Action структура валидна
- [ ] Dockerfile работает

---

### E6-2: Entrypoint Script
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** E6-1

**Описание:**
Скрипт выполнения анализа.

**entrypoint.sh:**
```bash
#!/bin/bash
set -e

PATH_TO_ANALYZE=$1
EDGE_TYPES=$2
OUTPUT_FILE=$3

echo "::group::Installing Codex Aura"
pip install codex-aura
echo "::endgroup::"

echo "::group::Analyzing $PATH_TO_ANALYZE"
codex-aura analyze "$PATH_TO_ANALYZE" \
  --edges "$EDGE_TYPES" \
  --format json \
  --output "$OUTPUT_FILE"
echo "::endgroup::"

# Set outputs
NODE_COUNT=$(jq '.stats.total_nodes' "$OUTPUT_FILE")
EDGE_COUNT=$(jq '.stats.total_edges' "$OUTPUT_FILE")

echo "graph-file=$OUTPUT_FILE" >> $GITHUB_OUTPUT
echo "node-count=$NODE_COUNT" >> $GITHUB_OUTPUT
echo "edge-count=$EDGE_COUNT" >> $GITHUB_OUTPUT

echo "✅ Analysis complete: $NODE_COUNT nodes, $EDGE_COUNT edges"
```

**Критерии приёмки:**
- [ ] Анализ выполняется
- [ ] Outputs устанавливаются
- [ ] Логи структурированы

---

### E6-3: PR Comment с результатами
**Оценка:** 2h | **Приоритет:** P2 | **Зависимости:** E6-2

**Описание:**
Добавить комментарий к PR с результатами анализа.

**Добавить input:**
```yaml
inputs:
  comment-on-pr:
    description: 'Add comment to PR with results'
    required: false
    default: 'false'
```

**Комментарий:**
```markdown
## 📊 Codex Aura Analysis

| Metric | Value |
|--------|-------|
| Files | 42 |
| Classes | 15 |
| Functions | 128 |
| Dependencies | 313 |

### Changed Files Impact
- `src/utils.py` → affects 5 files
- `src/models/user.py` → affects 3 files

[Download full graph](link-to-artifact)
```

**Критерии приёмки:**
- [ ] Комментарий создаётся
- [ ] Impact analysis включён
- [ ] Ссылка на артефакт

---

### E6-4: Cache для ускорения
**Оценка:** 1h | **Приоритет:** P2 | **Зависимости:** E6-2

**Описание:**
Кэширование pip пакетов.

```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: codex-aura-${{ hashFiles('**/pyproject.toml') }}
```

**Критерии приёмки:**
- [ ] Повторные запуски быстрее
- [ ] Cache hit отображается в логах

---

### E6-5: Публикация Action
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** E6-1-E6-4

**Описание:**
Публикация в GitHub Marketplace.

**Действия:**
- [ ] Создать releases с semver
- [ ] Добавить action в Marketplace
- [ ] README с примерами использования

**Пример использования:**
```yaml
name: Analyze Codebase
on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: codex-aura/analyze-action@v1
        with:
          path: '.'
          comment-on-pr: 'true'
```

**Критерии приёмки:**
- [ ] Action в Marketplace
- [ ] Версионирование работает

---

## E7: 📚 Документация

### E7-1: Docs Site (MkDocs/Docusaurus)
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** —

**Описание:**
Создать сайт документации.

**Структура:**
```
docs/
├── mkdocs.yml
├── docs/
│   ├── index.md           # Home
│   ├── getting-started/
│   │   ├── installation.md
│   │   ├── quick-start.md
│   │   └── configuration.md
│   ├── cli/
│   │   ├── analyze.md
│   │   ├── serve.md
│   │   └── commands.md
│   ├── api/
│   │   ├── overview.md
│   │   ├── endpoints.md
│   │   └── schemas.md
│   ├── integrations/
│   │   ├── vscode.md
│   │   └── github-action.md
│   └── development/
│       ├── contributing.md
│       └── architecture.md
```

**Критерии приёмки:**
- [ ] Docs site собирается
- [ ] Навигация интуитивная
- [ ] Поиск работает

---

### E7-2: API Reference (OpenAPI)
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E4-*

**Описание:**
Автогенерация API docs из FastAPI.

**Действия:**
- [ ] Настроить OpenAPI metadata
- [ ] Добавить descriptions ко всем endpoints
- [ ] Добавить примеры requests/responses
- [ ] Экспортировать openapi.json

**Критерии приёмки:**
- [ ] /docs (Swagger UI) полноценная
- [ ] /redoc как альтернатива
- [ ] openapi.json экспортируется

---

### E7-3: Getting Started Tutorial
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E7-1

**Описание:**
Пошаговый туториал для новых пользователей.

**Содержание:**
1. Установка
2. Первый анализ (CLI)
3. Запуск сервера
4. Использование API
5. VS Code extension
6. GitHub Action

**Критерии приёмки:**
- [ ] Можно пройти за 15 минут
- [ ] Copy-paste команды работают
- [ ] Screenshots актуальные

---

### E7-4: Architecture Decision Records
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** —

**Описание:**
Документация архитектурных решений.

**ADRs:**
- ADR-001: Выбор SQLite для storage
- ADR-002: Plugin architecture
- ADR-003: Edge type система
- ADR-004: API versioning

**Критерии приёмки:**
- [ ] Ключевые решения задокументированы
- [ ] Формат ADR соблюдён

---

### E7-5: JSON Schema Documentation
**Оценка:** 1h | **Приоритет:** P0 | **Зависимости:** E2-1

**Описание:**
Документация формата графа.

**Содержание:**
- Описание Node schema
- Описание Edge schema
- Описание Graph schema
- Примеры

**Критерии приёмки:**
- [ ] Schema версионирована
- [ ] Примеры для каждого типа

---

### E7-6: Changelog
**Оценка:** 30min | **Приоритет:** P0 | **Зависимости:** —

**Критерии приёмки:**
- [ ] CHANGELOG.md в Keep a Changelog формате
- [ ] Все изменения задокументированы

---

### E7-7: Contributing Guide
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** —

**Содержание:**
- Development setup
- Code style
- Testing
- PR process
- Issue templates

**Критерии приёмки:**
- [ ] Новый контрибьютор может начать
- [ ] Issue templates созданы

---

## E8: 🧪 Тестирование

### E8-1: Unit тесты для новых edge extractors
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E1-*

**Тесты:**
- [ ] `test_calls_extractor_simple`
- [ ] `test_calls_extractor_method_calls`
- [ ] `test_calls_extractor_imported_functions`
- [ ] `test_extends_extractor_single`
- [ ] `test_extends_extractor_multiple`
- [ ] `test_extends_extractor_cross_file`

**Coverage target:** > 90%

---

### E8-2: Unit тесты для storage
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E2-*

**Тесты:**
- [ ] `test_sqlite_save_load`
- [ ] `test_sqlite_query_nodes`
- [ ] `test_sqlite_query_edges`
- [ ] `test_sqlite_dependencies`
- [ ] `test_migrations`

---

### E8-3: API Integration тесты
**Оценка:** 3h | **Приоритет:** P0 | **Зависимости:** E4-*

**Тесты:**
```python
# tests/api/test_endpoints.py
from fastapi.testclient import TestClient

def test_analyze_endpoint(client: TestClient, temp_repo):
    response = client.post("/api/v1/analyze", json={
        "repo_path": str(temp_repo)
    })
    assert response.status_code == 200
    assert "graph_id" in response.json()

def test_context_endpoint(client: TestClient, sample_graph_id):
    response = client.post("/api/v1/context", json={
        "graph_id": sample_graph_id,
        "entry_points": ["src/main.py"]
    })
    assert response.status_code == 200
    assert len(response.json()["context_nodes"]) > 0
```

---

### E8-4: E2E тесты
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E8-3

**Сценарии:**
- [ ] CLI analyze → API query → correct result
- [ ] Full flow на реальном репозитории (Flask)
- [ ] Docker container startup

---

### E8-5: Performance тесты
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E8-4

**Бенчмарки:**
- [ ] 10K LOC < 5 сек
- [ ] 100K LOC < 30 сек
- [ ] API response < 100ms (cached)
- [ ] API response < 500ms (cold)

---

### E8-6: CI Pipeline
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E8-1-E8-5

**Обновить CI:**
```yaml
jobs:
  test:
    steps:
      - run: pytest tests/unit
      - run: pytest tests/integration
      - run: pytest tests/e2e
  
  benchmark:
    steps:
      - run: python scripts/benchmark.py
```

---

## E9: 📦 Публикация

### E9-1: PyPI публикация
**Оценка:** 2h | **Приоритет:** P0 | **Зависимости:** E8-*

**Действия:**
- [ ] Настроить PyPI credentials
- [ ] Настроить GitHub Action для публикации
- [ ] Создать первый release

```yaml
# .github/workflows/publish.yml
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
```

---

### E9-2: Docker Hub публикация
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** E3-8

**Действия:**
- [ ] Настроить Docker Hub credentials
- [ ] Multi-arch builds (amd64, arm64)
- [ ] Автопубликация на release

---

### E9-3: Announcement
**Оценка:** 2h | **Приоритет:** P1 | **Зависимости:** E9-1

**Каналы:**
- [ ] GitHub Release notes
- [ ] Twitter/X
- [ ] Reddit (r/Python, r/programming)
- [ ] Hacker News
- [ ] Dev.to blog post

---

### E9-4: Feedback collection
**Оценка:** 1h | **Приоритет:** P1 | **Зависимости:** E9-3

**Действия:**
- [ ] GitHub Discussions включён
- [ ] Issue templates созданы
- [ ] Feedback form (опционально)

---

### E9-5: Metrics & Analytics
**Оценка:** 1h | **Приоритет:** P2 | **Зависимости:** E9-1

**Отслеживать:**
- [ ] PyPI downloads
- [ ] GitHub stars
- [ ] VS Code extension installs
- [ ] GitHub Action usage

---

## ✅ Definition of Done (Phase 1)

Фаза 1 считается завершённой, когда:

- [ ] `pip install codex-aura` работает
- [ ] CALLS и EXTENDS edges извлекаются
- [ ] HTTP Server запускается и отвечает
- [ ] API endpoints документированы
- [ ] VS Code extension в Marketplace
- [ ] GitHub Action в Marketplace
- [ ] Docs site опубликован
- [ ] Тесты покрывают > 80% кода
- [ ] 100+ GitHub stars (цель)
- [ ] 10+ внешних пользователей