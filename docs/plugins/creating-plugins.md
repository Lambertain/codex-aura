# Создание плагинов для Codex Aura

## Обзор

Codex Aura поддерживает плагины для расширения функциональности анализа кода и контекста. Существует два типа плагинов:

- **Context Plugins** - плагины для ранжирования контекста
- **Impact Plugins** - плагины для анализа влияния изменений

## Быстрый старт

Создайте новый плагин за 30 минут, следуя этому руководству.

### 1. Создайте структуру проекта

```bash
mkdir my-custom-plugin
cd my-custom-plugin
```

### 2. Создайте setup.py или pyproject.toml

```python
# setup.py
from setuptools import setup

setup(
    name="my-custom-plugin",
    version="0.1.0",
    packages=["my_plugin"],
    entry_points={
        "codex_aura.plugins.context": [
            "my_context = my_plugin.context:MyContextPlugin",
        ],
        "codex_aura.plugins.impact": [
            "my_impact = my_plugin.impact:MyImpactPlugin",
        ],
    },
    install_requires=["codex-aura"],
)
```

### 3. Создайте базовые классы плагинов

```python
# my_plugin/__init__.py
from .context import MyContextPlugin
from .impact import MyImpactPlugin

__all__ = ["MyContextPlugin", "MyImpactPlugin"]
```

### 4. Реализуйте Context Plugin

```python
# my_plugin/context.py
from typing import Dict, List, Optional
from codex_aura.plugins.base import ContextPlugin
from codex_aura.models.node import Node

class MyContextPlugin(ContextPlugin):
    """Мой кастомный плагин для ранжирования контекста."""

    name = "my_context"
    version = "0.1.0"

    def rank_nodes(self, nodes: List[Node], task: Optional[str] = None, max_tokens: Optional[int] = None) -> List[Node]:
        """Ранжировать узлы по релевантности."""
        # Ваша логика ранжирования здесь
        return sorted(nodes, key=lambda n: getattr(n, 'distance', 0))

    def get_capabilities(self) -> Dict[str, bool]:
        """Вернуть возможности плагина."""
        return {
            "semantic_ranking": True,
            "token_budgeting": False,
            "task_understanding": True
        }
```

### 5. Реализуйте Impact Plugin

```python
# my_plugin/impact.py
from typing import Dict, List
from codex_aura.plugins.base import ImpactPlugin, ImpactReport
from codex_aura.models.graph import Graph

class MyImpactPlugin(ImpactPlugin):
    """Мой кастомный плагин для анализа влияния."""

    name = "my_impact"
    version = "0.1.0"

    def analyze_impact(self, changed_files: List[str], graph: Graph, depth: int = 3) -> ImpactReport:
        """Анализировать влияние изменений."""
        # Ваша логика анализа здесь
        affected_files = []  # Найденные затронутые файлы
        risk_level = "medium"  # low, medium, high

        return ImpactReport(affected_files, risk_level)

    def get_capabilities(self) -> Dict[str, bool]:
        """Вернуть возможности плагина."""
        return {
            "deep_analysis": True,
            "performance_tracking": False,
            "risk_assessment": True
        }
```

### 6. Установите плагин

```bash
pip install -e .
```

### 7. Настройте использование плагина

Создайте `.codex-aura/plugins.yaml` в вашем проекте:

```yaml
plugins:
  context:
    default: "my_context"
  impact:
    default: "my_impact"
```

## Типы плагинов

### Context Plugins

Отвечают за ранжирование узлов графа зависимостей для предоставления наиболее релевантного контекста.

**Методы:**
- `rank_nodes()` - ранжирует узлы
- `get_capabilities()` - возвращает возможности

### Impact Plugins

Анализируют влияние изменений на другие части кодовой базы.

**Методы:**
- `analyze_impact()` - анализирует влияние
- `get_capabilities()` - возвращает возможности

## Регистрация плагинов

Плагины регистрируются через entry points в setup.py:

```python
entry_points={
    "codex_aura.plugins.context": [
        "my_plugin = my_package.module:MyPluginClass",
    ],
    "codex_aura.plugins.impact": [
        "my_plugin = my_package.module:MyPluginClass",
    ],
}
```

## Тестирование

Создайте тесты для вашего плагина:

```python
# tests/test_my_plugin.py
import pytest
from my_plugin.context import MyContextPlugin
from my_plugin.impact import MyImpactPlugin

def test_context_plugin():
    plugin = MyContextPlugin()
    nodes = []  # Создайте тестовые узлы
    ranked = plugin.rank_nodes(nodes)
    assert len(ranked) == len(nodes)

def test_impact_plugin():
    plugin = MyImpactPlugin()
    # Тест логики анализа влияния
    pass
```

## Публикация

Опубликуйте ваш плагин на PyPI для использования другими разработчиками.

## Примеры

Посмотрите примеры плагинов в директории `examples/custom-plugin/`.