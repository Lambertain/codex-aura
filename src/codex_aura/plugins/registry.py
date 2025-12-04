"""Plugin registry for managing context and impact plugins."""

import importlib
import importlib.metadata
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
    def get_context_plugin_capabilities(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get capabilities of a context plugin."""
        plugin_cls = cls.get_context_plugin(name)
        if plugin_cls and hasattr(plugin_cls, 'get_capabilities'):
            instance = plugin_cls()
            return {
                "name": getattr(instance, 'name', name),
                "version": getattr(instance, 'version', 'unknown'),
                "capabilities": instance.get_capabilities()
            }
        return None

    @classmethod
    def get_impact_plugin_capabilities(cls, name: str) -> Optional[Dict[str, Any]]:
        """Get capabilities of an impact plugin."""
        plugin_cls = cls.get_impact_plugin(name)
        if plugin_cls and hasattr(plugin_cls, 'get_capabilities'):
            instance = plugin_cls()
            return {
                "name": getattr(instance, 'name', name),
                "version": getattr(instance, 'version', 'unknown'),
                "capabilities": instance.get_capabilities()
            }
        return None

    @classmethod
    def get_all_capabilities(cls) -> Dict[str, Any]:
        """Get capabilities of all registered plugins."""
        context_plugins = {}
        impact_plugins = {}

        for name in cls.list_context_plugins():
            caps = cls.get_context_plugin_capabilities(name)
            if caps:
                context_plugins[name] = caps

        for name in cls.list_impact_plugins():
            caps = cls.get_impact_plugin_capabilities(name)
            if caps:
                impact_plugins[name] = caps

        return {
            "context_plugin": next(iter(context_plugins.values()), None),
            "impact_plugin": next(iter(impact_plugins.values()), None),
            "premium_available": False  # Will be updated when premium plugins are available
        }

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

    @classmethod
    def discover_plugins(cls):
        """Discover and load plugins from entry points."""
        # Discover context plugins
        context_eps = importlib.metadata.entry_points(group="codex_aura.plugins.context")
        for ep in context_eps:
            try:
                plugin_cls = ep.load()
                if ep.name in cls._context_plugins:
                    logger.warning(f"Context plugin '{ep.name}' already registered, skipping entry point")
                    continue
                cls._context_plugins[ep.name] = plugin_cls
                logger.info(f"Discovered and registered context plugin: {ep.name} from {ep.value}")
            except Exception as e:
                logger.error(f"Failed to load context plugin '{ep.name}' from {ep.value}: {e}")

        # Discover impact plugins
        impact_eps = importlib.metadata.entry_points(group="codex_aura.plugins.impact")
        for ep in impact_eps:
            try:
                plugin_cls = ep.load()
                if ep.name in cls._impact_plugins:
                    logger.warning(f"Impact plugin '{ep.name}' already registered, skipping entry point")
                    continue
                cls._impact_plugins[ep.name] = plugin_cls
                logger.info(f"Discovered and registered impact plugin: {ep.name} from {ep.value}")
            except Exception as e:
                logger.error(f"Failed to load impact plugin '{ep.name}' from {ep.value}: {e}")