## P0-1 — Smart Context API (POST /context)
Goal: единый API, который принимает задачу и возвращает оптимально подобранный контекст.
Description

Реализовать API-endpoint:

POST /api/v1/context


который:

Принимает:

repo_id

task (текст)

max_tokens

model

Выполняет pipeline:

semantic search

graph expansion

ranking

token budgeting

summarization

Возвращает структурированный контекст:

{
  "nodes": [...],
  "total_tokens": ...,
  "graph_expansion": {...},
  "semantic_matches": [...],
  "model": "gpt-4o"
}

Dependencies

Semantic Ranking Engine (P0-2)

Budgeting (already done)

Search + Graph queries (already done)

Acceptance Criteria

 Endpoint существует и принимает JSON

 Возвращает структурированный контекст

 Никогда не превышает указанное max_tokens

 Обрабатывает плохие запросы

 Работает < 500ms на типичном запросе

## P0-2 — Semantic Ranking Engine
Goal: Объединить семантическое сходство + графовые зависимости в единый scoring.
Description

Создать модуль:

src/codex_aura/context/ranking.py


который вычисляет итоговый score ∈ [0;1] для каждого node, используя:

semantic similarity (cosine)

distance from focal nodes в графе

file frequency

token cost

"criticality" (contracts, controllers, imports)

Output

Функция:

ranked_nodes = rank_context(query, sem_results, graph_results)


Каждый элемент:

{
  "node": Node,
  "semantic_score": 0.84,
  "graph_score": 0.62,
  "combined_score": 0.73,
  "tokens": 312
}

Acceptance Criteria

 Весовая модель документирована

 Выдаёт детерминированные результаты

 Производительность > 5K nodes/sec

 Тесты на разных примерах

## P0-3 — Unified Context Pipeline
Goal: собрать все компоненты в один магистральный pipeline.
Description

Создать:

src/codex_aura/context/pipeline.py


Этапы:

Semantic search

Graph expansion (breadth-first relevance)

Ranking

Budget allocation

Summarization

Final formatting

Output
pipeline.run(repo_id, task, max_tokens, model) 
→ ContextResult

Acceptance Criteria

 Pipeline работает как black-box

 Логирует каждый шаг

 Гарантирует max_tokens

 Покрыт unit-тестами

## P0-4 — Backend Authentication Integration
Goal: связать Clerk (frontend) с backend логикой.
Tasks

JWT middleware для FastAPI

Extract user from Bearer token

Привязка репозиториев к user_id

Ограничение доступа к чужим данным

Переделка всех запросов /repos/*, /context, /sync

Acceptance Criteria

 Любой запрос без токена — 401

 Пользователь видит только свои репозитории

 API корректно обрабатывает logout

## P0-5 — Billing System (Stripe)
Goal: полноценная монетизация SaaS.
Tasks

Stripe Checkout session

Stripe Customer creation

Stripe Webhooks:

invoice.paid

customer.subscription.updated

DB schema:

users(plan, billing_id, limits)

usage(api_calls, repos_count)

Limits:

Free: 1 repo, 100 ctx requests

Pro: 5 repos, 10K ctx

Team: 20 repos

Acceptance Criteria

 Рабочая оплата через Stripe

 Автоматический upgrade/downgrade

 Списание usage по API вызовам

 Пользователь видит свой план в Dashboard

## P0-6 — Usage Telemetry
Goal: сбор данных о работе системы.
Tasks

Логировать:

context request

semantic search usage

incremental sync events

Хранить aggregated usage в PostgreSQL

API: /api/v1/usage/me

Acceptance Criteria

 Метрики обновляются автоматически

 Dashboard отображает usage

 Влияние на performance < 3%

 # 🟧 P1 — PRODUCT ENHANCEMENTS (для полноценного SaaS)
## P1-1 — Dashboard: Repo Overview Page
Tasks

Graph stats summary

Last sync events

Codebase summary

Health indicators

Acceptance Criteria

 Открывается мгновенно

 Показывает реальное состояние репозитория

## P1-2 — Dashboard: Semantic Search UI
Tasks

Input field

Show ranked results

Show code previews

Highlight relevance score

Acceptance Criteria

 UX как в Sourcegraph / CodeNav

 <150ms UI render

## P1-3 — Dashboard: Graph Visualization Enhancements
Tasks

Node details panel

focus-on-node

edge highlighting

type filtering

Acceptance Criteria

 Граф крупного репо (3K nodes) работает без лагов

 Пользователь может кликать, исследовать, фильтровать

## P1-4 — Dashboard: Billing UI
Tasks

Show active plan

Usage breakdown

“Upgrade plan” button

Payment history

## P1-5 — Dashboard: API Keys page
Tasks

Generate API key

Revoke API key

Display examples for curl + agents

## PF2-1 — Create Graph Snapshot Schema
Goal: хранить граф кода для любого SHA.
Description

Добавить таблицы и структуры:

graph_snapshots (
    snapshot_id UUID,
    repo_id UUID,
    sha TEXT,
    created_at TIMESTAMP,
    node_count INT,
    edge_count INT
)

snapshot_nodes (...)
snapshot_edges (...)

Dependencies

Existing graph schema

Incremental sync

Acceptance Criteria

 Можно сохранить граф для конкретного SHA

 Метаданные хранятся в PostgreSQL

 Узлы и рёбра хранятся эффективно (batch insert)

## PF2-2 — Snapshot Generator
Goal: Генерация snapshot при поступлении webhook push event.
Description

Реализовать:

snapshot_service.create_snapshot(repo_id, sha)


Механика:

Получить текущее состояние Neo4j для repo

Экспортировать nodes + edges

Сохранить в PostgreSQL snapshot таблицы

Записать метаданные

Acceptance Criteria

 Snapshot создаётся < 3 сек для репо < 5K nodes

 Ошибки логируются

 Snapshot ID возвращается

## PF2-3 — Snapshot Retrieval API
Goal: выдавать граф для любого SHA.
Description

Endpoint:

GET /api/v1/repos/{repo_id}/graph/{sha}


Возвращает:

{
  "sha": "...",
  "nodes": [...],
  "edges": [...],
  "stats": {...}
}

Acceptance Criteria

 Работает быстро (кеширование)

 SHA not found → 404

 Полностью совместим с Dashboard

## PF2-4 — Graph Diff Engine
Goal: сравнение двух графов (SHA1 vs SHA2).
Description

Создать:

graph_diff.calculate(sha_old, sha_new)


Возвращает:

{
  "added_nodes": [...],
  "removed_nodes": [...],
  "changed_nodes": [...],
  "added_edges": [...],
  "removed_edges": [...],
}

Acceptance Criteria

 Difference calculation < 1 sec for mid-size repo

 Поддержка changed nodes на основе properties hash

# 🟦 PREMIUM FEATURE 2 — MULTI-REPO LINKS
Roadmap reference: Phase 2 → Premium → Multi-repo — связи между репозиториями (микросервисы)

codex_aura_roadmap

## PF2-5 — Multi-Repo Dependency Scanner
Goal: находить связи между сервисами по import/HTTP calls/queue events.
Description

Анализировать:

requests.get("<service>/...")

gRPC clients

Kafka topics

Import-like references across repos

Формировать межреповые edges:

(:ServiceA)-[:CALLS]->(:ServiceB)

Acceptance Criteria

 Edge создаётся при нахождении cross-repo call

 Поддерживает Python/TS (минимально)

 Хранится в Neo4j

## PF2-6 — Service Registry
Goal: хранить информацию о сервисах.
Description
services (
   service_id UUID,
   name TEXT,
   repo_id UUID,
   description TEXT
)

Acceptance Criteria

 Каждый repo привязан к сервису

 Межсервисные edges агрегируются

## PF2-7 — Cross-Repo Graph API
Goal: API для получения межсервисного графа.
Endpoint
GET /api/v1/services/graph


Возвращает:

nodes: [{service_id, name}]
edges: [{source, target, type}]

Acceptance Criteria

 Можно визуализировать в Dashboard

 Производительность: < 200ms

# 🟦 PREMIUM FEATURE 3 — IMPACT ANALYSIS
Roadmap reference: Phase 2 → Premium → Impact Analysis — Predicted affected files

codex_aura_roadmap

## PF2-8 — Impact Rule Engine (rule-based, non-ML)
Goal: прогнозировать, какие файлы затронет изменение.
Description

Правила:

If function A calls B → изменение A влияет на B

If file imports X → изменение X влияет на file

If class extends Y → изменение Y влияет на class

Depth limit = 3

API:

impact = impact_engine.predict(file_path, repo_id)


Возвращает отсортированные impacted files.

Acceptance Criteria

 Нет ML, только детерминированные правила

 Работает всегда одинаково

 Производительность высокая

## PF2-9 — Impact Visualization API
Goal: граф зависимых файлов для Dashboard.
Endpoint
GET /api/v1/repos/{id}/impact?file=path

Returns
{
  "direct": [...],
  "indirect": [...],
  "graph": {...}
}

Acceptance Criteria

 Поддержка прямых + косвенных зависимостей

 Depth-limit корректно работает

## PF2-10 — Integration with PR Systems
Goal: вывод impacted files в CI pipelines (GitHub Actions).
Description

Генерировать:

список impacted files

комментарий в PR

уровень риска: low / medium / high

Acceptance Criteria

 GitHub Action готов

 API: /api/v1/impact/pr

 Полностью автономно

# 🟦 PREMIUM FEATURE 4 — ENHANCED SEMANTIC CONTEXT

(в roadmap Phase 2 как "Semantic Context" и "Token Budgeting", но часть ещё необработана)

## PF2-11 — Context Clustering
Goal: группировать nodes по темам/модулям.
Description

Использовать embeddings:

clusters = cluster_nodes(nodes, k=8)


Алгоритмы: k-means / hdbscan.

Acceptance Criteria

 Cluster labels генерируются

 Отображается в Dashboard search

## PF2-12 — Weighted Graph Expansion
Goal: добавлять соседей на основе веса, а не фиксированного depth.
Description

Вес = f(type, frequency, semantic relevance).
Например:

CALLS = 0.9

IMPORTS = 0.6

EXTENDS = 1.0

Останавливать expansion при суммарном весе < threshold.

Acceptance Criteria

 Stable и детерминированное поведение

 Улучшает качество контекста