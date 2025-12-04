"""Plugin system for codex-aura."""

from .registry import PluginRegistry

# Discover plugins from entry points on import
PluginRegistry.discover_plugins()

__all__ = ["PluginRegistry"]