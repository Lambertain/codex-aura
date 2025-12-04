# Plugin API Reference

## Обзор

Codex Aura предоставляет расширяемый API для создания плагинов, которые могут анализировать код и предоставлять контекст для AI агентов.

## Базовые классы

### ContextPlugin

Базовый класс для плагинов ранжирования контекста.

```python
from codex_aura.plugins.base import ContextPlugin

class MyContextPlugin(ContextPlugin):
    name = "my_plugin"
    version = "1.0.0"
```

#### Методы

##### rank_nodes(nodes, task=None, max_tokens=None)

Ранжирует список узлов по релевантности для предоставления контекста.

**Параметры:**
- `nodes` (List[Node]) - Список узлов для ранжирования
- `task` (Optional[str]) - Описание задачи для понимания контекста
- `max_tokens` (Optional[int]) - Максимальное количество токенов

**Возвращает:** List[Node] - Отранжированный список узлов

##### get_capabilities()

Возвращает словарь с возможностями плагина.

**Возвращает:** Dict[str, bool]

**Пример:**
```python
{
    "semantic_ranking": True,      # Семантическое ранжирование
    "token_budgeting": False,     # Управление бюджетом токенов
    "task_understanding": True    # Понимание задач
}
```

### ImpactPlugin

Базовый класс для плагинов анализа влияния изменений.

```python
from codex_aura.plugins.base import ImpactPlugin

class MyImpactPlugin(ImpactPlugin):
    name = "my_plugin"
    version = "1.0.0"
```

#### Методы

##### analyze_impact(changed_files, graph, depth=3)

Анализирует влияние изменений файлов на кодовую базу.

**Параметры:**
- `changed_files` (List[str]) - Список измененных файлов
- `graph` (Graph) - Граф зависимостей проекта
- `depth` (int) - Максимальная глубина анализа (по умолчанию 3)

**Возвращает:** ImpactReport

##### get_capabilities()

Возвращает словарь с возможностями плагина.

**Возвращает:** Dict[str, bool]

**Пример:**
```python
{
    "deep_analysis": True,         # Глубокий анализ
    "performance_tracking": False, # Отслеживание производительности
    "risk_assessment": True       # Оценка рисков
}
```

## Модели данных

### Node

Представляет узел в графе зависимостей.

**Атрибуты:**
- `id` (str) - Уникальный идентификатор
- `type` (str) - Тип узла (function, class, module, etc.)
- `name` (str) - Имя узла
- `file_path` (str) - Путь к файлу
- `content` (str) - Содержимое узла
- `metadata` (Dict) - Дополнительные метаданные

### Graph

Представляет граф зависимостей проекта.

**Методы:**
- `get_node(node_id)` - Получить узел по ID
- `get_neighbors(node_id)` - Получить соседние узлы
- `find_path(start_id, end_id)` - Найти путь между узлами

### ImpactReport

Отчет об анализе влияния изменений.

**Атрибуты:**
- `affected_files` (List[str]) - Затронутые файлы
- `risk_level` (str) - Уровень риска (low, medium, high)

## Регистрация плагинов

### Декораторы

```python
from codex_aura.plugins.registry import PluginRegistry

@PluginRegistry.register_context("my_plugin")
class MyContextPlugin(ContextPlugin):
    pass

@PluginRegistry.register_impact("my_plugin")
class MyImpactPlugin(ImpactPlugin):
    pass
```

### Entry Points

Плагины могут быть зарегистрированы через entry points в setup.py:

```python
setup(
    entry_points={
        "codex_aura.plugins.context": [
            "my_plugin = my_package.module:MyContextPlugin",
        ],
        "codex_aura.plugins.impact": [
            "my_plugin = my_package.module:MyImpactPlugin",
        ],
    }
)
```

## PluginRegistry

Центральный реестр для управления плагинами.

### Методы класса

#### list_context_plugins()

Возвращает список имен всех зарегистрированных context плагинов.

**Возвращает:** List[str]

#### list_impact_plugins()

Возвращает список имен всех зарегистрированных impact плагинов.

**Возвращает:** List[str]

#### get_context_plugin(name)

Возвращает класс context плагина по имени.

**Параметры:**
- `name` (str) - Имя плагина

**Возвращает:** Optional[Type]

#### get_impact_plugin(name)

Возвращает класс impact плагина по имени.

**Параметры:**
- `name` (str) - Имя плагина

**Возвращает:** Optional[Type]

#### get_all_capabilities()

Возвращает возможности всех зарегистрированных плагинов.

**Возвращает:** Dict[str, Any]

## Конфигурация плагинов

Плагины настраиваются через файл `.codex-aura/plugins.yaml`:

```yaml
plugins:
  context:
    default: "my_context_plugin"
    fallback: "basic"
  impact:
    default: "my_impact_plugin"
  analyzers:
    python: "my_python_analyzer"
```

### PluginConfig

Класс для загрузки конфигурации плагинов.

#### Методы

##### get_context_plugin()

Возвращает имя плагина для ранжирования контекста.

**Возвращает:** str

##### get_impact_plugin()

Возвращает имя плагина для анализа влияния.

**Возвращает:** str

##### get_analyzer_plugin(language)

Возвращает имя анализатора для указанного языка.

**Параметры:**
- `language` (str) - Язык программирования

**Возвращает:** Optional[str]

## Обработка ошибок

Плагины должны корректно обрабатывать ошибки и логировать их:

```python
import logging

logger = logging.getLogger(__name__)

try:
    # Код плагина
    pass
except Exception as e:
    logger.error(f"Plugin error: {e}")
    raise
```

## Лучшие практики

1. **Наследование от базовых классов** - Всегда наследуйтесь от `ContextPlugin` или `ImpactPlugin`

2. **Документирование** - Добавляйте docstrings ко всем методам

3. **Обработка ошибок** - Корректно обрабатывайте исключения

4. **Логирование** - Используйте logging для отладки

5. **Тестирование** - Создавайте unit тесты для плагинов

6. **Версионирование** - Указывайте версию плагина

7. **Возможности** - Честно описывайте возможности плагина в `get_capabilities()`

## Примеры

### Простой Context Plugin

```python
from typing import Dict, List, Optional
from codex_aura.plugins.base import ContextPlugin
from codex_aura.models.node import Node

class SimpleContextPlugin(ContextPlugin):
    name = "simple"
    version = "1.0.0"

    def rank_nodes(self, nodes: List[Node], task: Optional[str] = None, max_tokens: Optional[int] = None) -> List[Node]:
        # Простое ранжирование по расстоянию
        return sorted(nodes, key=lambda n: getattr(n, 'distance', 0))

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "semantic_ranking": False,
            "token_budgeting": True,
            "task_understanding": False
        }
```

### Простой Impact Plugin

```python
from typing import Dict, List
from codex_aura.plugins.base import ImpactPlugin, ImpactReport
from codex_aura.models.graph import Graph

class SimpleImpactPlugin(ImpactPlugin):
    name = "simple"
    version = "1.0.0"

    def analyze_impact(self, changed_files: List[str], graph: Graph, depth: int = 3) -> ImpactReport:
        affected = []
        for file in changed_files:
            # Найти зависимые файлы
            node = graph.find_node_by_file(file)
            if node:
                neighbors = graph.get_neighbors(node.id, depth=depth)
                affected.extend([n.file_path for n in neighbors if n.file_path != file])

        risk_level = "low" if len(affected) < 5 else "medium"
        return ImpactReport(list(set(affected)), risk_level)

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "deep_analysis": True,
            "performance_tracking": False,
            "risk_assessment": True
        }