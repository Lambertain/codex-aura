# Codex Aura - TODO List

**Дата генерации:** 2025-12-05
**На основе:** Phase 0 (~88% complete), Phase 1.1 (~95% complete)

---

## Phase 0: Proof of Concept

### E1: Инфраструктура проекта

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E1-6 | **ЧАСТИЧНО** | P0 | Тестовые репозитории - нужно добавить `examples/flask_mini/` |

### E2: Спецификация графа

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E2-4 | **✅ ВЫПОЛНЕНО** | P1 | JSON Schema файл - обновлен `docs/schema/graph-v0.1.json` |

### E5: Demo Script

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E5-2 | **НЕ ВЫПОЛНЕНО** | P2 | ASCII-визуализация графа в терминале |
| E5-3 | **✅ ВЫПОЛНЕНО** | P1 | Benchmark скрипт - уже существует `examples/benchmark.py` |

### E6: Тестирование

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E6-4 | **✅ ВЫПОЛНЕНО** | P1 | Тесты на реальных проектах - `tests/test_real_projects.py` |
| E6-5 | **✅ ВЫПОЛНЕНО** | P1 | Edge cases тесты - расширен `tests/test_edge_cases.py` |

---

## Phase 1.1: Open Source MVP

### E1: Расширение Анализатора

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E1-6 | **НЕ ВЫПОЛНЕНО** | P2 | IMPLEMENTS Edge Extractor (Protocol/ABC) |
| E1-8 | **НЕ ВЫПОЛНЕНО** | P2 | Cyclomatic Complexity с библиотекой radon |

### E7: Документация

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E7-X | **НЕ ВЫПОЛНЕНО** | P1 | Architecture docs - создать `docs/architecture.md` с диаграммами |

### E8: Тестирование

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E8-6 | **✅ ВЫПОЛНЕНО** | P1 | Performance тесты - уже существует `tests/test_performance.py` |

### E9: Публикация

| Задача | Статус | Приоритет | Описание |
|--------|--------|-----------|----------|
| E9-3 | **НЕ ВЫПОЛНЕНО** | P1 | Публикация VS Code extension в marketplace |

---

## Сводка по приоритетам

### P0 (Критические) - 0 задач
Все P0 задачи выполнены!

### P1 (Важные) - 7 задач

1. **JSON Schema** - `docs/schema/graph-v0.1.json`
2. **Benchmark скрипт** - `examples/benchmark.py`
3. **Тесты на реальных проектах** - Flask, FastAPI, Requests
4. **Edge cases тесты** - циклические импорты, большие файлы
5. **Architecture docs** - `docs/architecture.md`
6. **Performance тесты** - для 100K+ LOC
7. **VS Code marketplace** - публикация расширения

### P2 (Желательные) - 3 задачи

1. **ASCII визуализация** - древовидный вывод в терминале
2. **IMPLEMENTS edges** - Protocol/ABC обнаружение
3. **Cyclomatic Complexity** - интеграция с radon

---

## Детальные требования

### 1. JSON Schema (`docs/schema/graph-v0.1.json`)

```python
# Генерация из Pydantic модели:
from codex_aura.models import Graph
schema = Graph.model_json_schema()
# Сохранить в docs/schema/graph-v0.1.json
```

**Критерии приёмки:**
- [ ] JSON Schema файл валиден
- [ ] Можно валидировать JSON-граф против schema

---

### 2. Benchmark скрипт (`examples/benchmark.py`)

**Функционал:**
```bash
python examples/benchmark.py /path/to/large/repo
```

**Вывод:**
```
Benchmark: flask (127 files, 45K LOC)
  Scan files:    0.05s
  Parse AST:     0.82s
  Build graph:   0.15s
  Total:         1.02s

Performance: 44K LOC/sec
```

**Критерии приёмки:**
- [ ] Измеряет время каждого этапа
- [ ] Выводит LOC/sec метрику

---

### 3. Тесты на реальных проектах

**Целевые метрики:**
| Репозиторий | LOC | Целевое время |
|-------------|-----|---------------|
| Flask | ~50K | < 10 сек |
| FastAPI | ~30K | < 5 сек |
| Requests | ~10K | < 2 сек |

**Критерии приёмки:**
- [ ] Все репозитории анализируются без ошибок
- [ ] Время соответствует целевым метрикам

---

### 4. Architecture docs (`docs/architecture.md`)

**Секции:**
- [ ] Общая архитектура системы (диаграмма)
- [ ] Компоненты и их взаимодействие
- [ ] Data flow (анализ → storage → API)
- [ ] Plugin architecture
- [ ] Extension points

---

### 5. Performance тесты

**Сценарии:**
- [ ] Анализ репозитория 100K+ LOC
- [ ] Concurrent API запросы (load testing)
- [ ] Memory usage при больших графах
- [ ] SQLite query performance

**Инструменты:**
- pytest-benchmark
- locust (для API)
- memory_profiler

---

### 6. VS Code Extension публикация

**Шаги:**
- [ ] Создать Azure DevOps account (для marketplace)
- [ ] Настроить vsce (VS Code Extension Manager)
- [ ] Обновить package.json с publisher info
- [ ] Создать README для marketplace
- [ ] Добавить скриншоты/демо GIF
- [ ] Опубликовать через `vsce publish`

---

### 7. ASCII визуализация (P2)

**Пример вывода:**
```
src/main.py
├── imports: src/utils.py
│   └── imports: src/config.py
├── imports: src/services/user.py
│   ├── imports: src/utils.py
│   └── imports: src/models/user.py
```

---

### 8. IMPLEMENTS edges (P2)

**Что детектировать:**
```python
from typing import Protocol

class Drawable(Protocol):
    def draw(self) -> None: ...

class Circle:  # IMPLEMENTS: Circle -> Drawable
    def draw(self) -> None:
        pass
```

---

### 9. Cyclomatic Complexity (P2)

**Интеграция:**
```bash
codex-aura analyze . --complexity
```

**Формула:**
```
CC = 1 + if + elif + for + while + except + and + or + ternary
```

---

## Оценка трудозатрат

| Приоритет | Задач | Оценка |
|-----------|-------|--------|
| P1 | 7 | ~20h |
| P2 | 3 | ~6h |
| **ИТОГО** | **10** | **~26h** |

---

## Порядок выполнения (рекомендуемый)

1. **JSON Schema** (E2-4) - 1h - база для валидации
2. **Benchmark скрипт** (E5-3) - 1h - измерение baseline
3. **Тесты на реальных проектах** (E6-4) - 2h - валидация качества
4. **Edge cases тесты** (E6-5) - 2h - robustness
5. **Performance тесты** (E8-6) - 4h - оптимизация
6. **Architecture docs** (E7-X) - 3h - документация
7. **VS Code marketplace** (E9-3) - 3h - публикация
8. *(P2)* ASCII визуализация - 2h
9. *(P2)* IMPLEMENTS edges - 2h
10. *(P2)* Cyclomatic Complexity - 2h
