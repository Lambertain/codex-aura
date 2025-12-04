"""Plugin registry for managing context and impact plugins."""

import importlib
import logging
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger("codex_aura")


class PluginRegistry:
    """Registry for managing plugins."""

    _context_plugins: Dict[str, Type] = {}
    _impact_plugins: Dict[str, Type] = {}

    @classmethod
    def register_context(cls, name: str):
        """Decorator to register a context plugin."""
        def decorator(plugin_class: Type) -> Type:
            cls._context_plugins[name] = plugin_class
            logger.info(f"Registered context plugin: {name}")
            return plugin_class
        return decorator

    @classmethod
    def register_impact(cls, name: str):
        """Decorator to register an impact plugin."""
        def decorator(plugin_class: Type) -> Type:
            cls._impact_plugins[name] = plugin_class
            logger.info(f"Registered impact plugin: {name}")
            return plugin_class
        return decorator

    @classmethod
    def get_context_plugin(cls, name: str) -> Optional[Type]:
        """Get a context plugin by name."""
        return cls._context_plugins.get(name)

    @classmethod
    def get_impact_plugin(cls, name: str) -> Optional[Type]:
        """Get an impact plugin by name."""
        return cls._impact_plugins.get(name)

    @classmethod
    def list_context_plugins(cls) -> List[str]:
        """List all registered context plugin names."""
        return list(cls._context_plugins.keys())

    @classmethod
    def list_impact_plugins(cls) -> List[str]:
        """List all registered impact plugin names."""
        return list(cls._impact_plugins.keys())

    @classmethod
    def load_plugin(cls, module_path: str, class_name: str) -> Type:
        """Load a plugin class from a module path."""
        try:
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            return plugin_class
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load plugin {module_path}.{class_name}: {e}")
            raise