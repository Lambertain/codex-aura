# Codex Aura Custom Plugin

Пример кастомного плагина для Codex Aura - системы анализа кода и контекста для AI агентов.

## Что такое плагины Codex Aura?

Codex Aura поддерживает два типа плагинов:

- **Context Plugins** - ранжируют контекст для предоставления наиболее релевантной информации
- **Impact Plugins** - анализируют влияние изменений на кодовую базу

## Установка

```bash
# Клонируйте репозиторий
git clone https://github.com/yourusername/codex-aura-custom-plugin.git
cd codex-aura-custom-plugin

# Установите плагин
pip install -e .
```

## Использование

После установки плагин будет автоматически зарегистрирован в Codex Aura.

### Настройка

Создайте файл `.codex-aura/plugins.yaml` в вашем проекте:

```yaml
plugins:
  context:
    default: "custom_context"
  impact:
    default: "custom_impact"
```

### Проверка установки

```bash
# Проверьте доступные плагины
python -c "from codex_aura.plugins.registry import PluginRegistry; print('Context plugins:', PluginRegistry.list_context_plugins()); print('Impact plugins:', PluginRegistry.list_impact_plugins())"
```

## Структура проекта

```
codex_aura_custom_plugin/
├── __init__.py              # Экспорт плагинов
├── context.py               # Context Plugin реализация
├── impact.py                # Impact Plugin реализация
└── config.py                # Конфигурация плагина (опционально)
```

## Разработка

### Тестирование

```bash
# Запустите тесты
pytest tests/

# С отчётом о покрытии
pytest --cov=codex_aura_custom_plugin --cov-report=html
```

### Линтинг

```bash
# Проверьте код
black codex_aura_custom_plugin/
isort codex_aura_custom_plugin/
flake8 codex_aura_custom_plugin/
```

## API Reference

### CustomContextPlugin

Плагин для ранжирования контекста с использованием семантического анализа.

**Методы:**
- `rank_nodes(nodes, task, max_tokens)` - ранжирует узлы по релевантности
- `get_capabilities()` - возвращает возможности плагина

### CustomImpactPlugin

Плагин для анализа влияния изменений с оценкой рисков.

**Методы:**
- `analyze_impact(changed_files, graph, depth)` - анализирует влияние изменений
- `get_capabilities()` - возвращает возможности плагина

## Расширение

### Добавление новых возможностей

1. Добавьте методы в классы плагинов
2. Обновите `get_capabilities()` для отражения новых возможностей
3. Добавьте тесты для новых функций
4. Обновите документацию

### Кастомная конфигурация

Добавьте файл `config.py` для управления настройками плагина:

```python
class PluginConfig:
    def __init__(self):
        self.max_depth = 5
        self.confidence_threshold = 0.8
```

## Лицензия

MIT License - см. файл LICENSE для деталей.

## Вклад в проект

1. Fork репозиторий
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Создайте Pull Request

## Поддержка

Если у вас возникли вопросы или проблемы:

1. Проверьте [документацию Codex Aura](https://codex-aura.readthedocs.io/)
2. Создайте issue в этом репозитории
3. Свяжитесь с командой разработки