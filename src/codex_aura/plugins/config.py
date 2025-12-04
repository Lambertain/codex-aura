"""Plugin configuration management."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class PluginConfig:
    """Configuration for plugins."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._find_config_path()
        self._config = self._load_config()

    def _find_config_path(self) -> Path:
        """Find the configuration file path."""
        # Look for .codex-aura/plugins.yaml in current directory or parent directories
        current = Path.cwd()
        for _ in range(10):  # Limit search depth
            config_path = current / ".codex-aura" / "plugins.yaml"
            if config_path.exists():
                return config_path
            current = current.parent
        # Default to current directory
        return Path.cwd() / ".codex-aura" / "plugins.yaml"

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file with environment overrides."""
        config = {}

        # Load from YAML file if it exists
        if self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

        # Apply environment overrides
        config = self._apply_env_overrides(config)

        # Validate configuration
        self._validate_config(config)

        return config

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Context plugin override
        if "CODEX_AURA_CONTEXT_PLUGIN" in os.environ:
            config.setdefault("plugins", {}).setdefault("context", {})
            config["plugins"]["context"]["default"] = os.environ["CODEX_AURA_CONTEXT_PLUGIN"]

        # Impact plugin override
        if "CODEX_AURA_IMPACT_PLUGIN" in os.environ:
            config.setdefault("plugins", {}).setdefault("impact", {})
            config["plugins"]["impact"]["default"] = os.environ["CODEX_AURA_IMPACT_PLUGIN"]

        return config

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate the configuration structure."""
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")

        plugins = config.get("plugins", {})

        # Validate context plugin config
        context_config = plugins.get("context", {})
        if "default" in context_config:
            if not isinstance(context_config["default"], str):
                raise ValueError("Context default plugin must be a string")

        if "fallback" in context_config:
            if not isinstance(context_config["fallback"], str):
                raise ValueError("Context fallback plugin must be a string")

        # Validate impact plugin config
        impact_config = plugins.get("impact", {})
        if "default" in impact_config:
            if not isinstance(impact_config["default"], str):
                raise ValueError("Impact default plugin must be a string")

        # Validate analyzers config
        analyzers_config = plugins.get("analyzers", {})
        if not isinstance(analyzers_config, dict):
            raise ValueError("Analyzers config must be a dictionary")

        # Validate premium config
        premium_config = config.get("premium", {})
        if not isinstance(premium_config, dict):
            raise ValueError("Premium config must be a dictionary")

    def get_context_plugin(self) -> str:
        """Get the default context plugin name."""
        return self._config.get("plugins", {}).get("context", {}).get("default", "basic")

    def get_context_fallback_plugin(self) -> str:
        """Get the fallback context plugin name."""
        return self._config.get("plugins", {}).get("context", {}).get("fallback", "basic")

    def get_impact_plugin(self) -> str:
        """Get the default impact plugin name."""
        return self._config.get("plugins", {}).get("impact", {}).get("default", "basic")

    def get_analyzer_plugin(self, language: str) -> Optional[str]:
        """Get the analyzer plugin for a specific language."""
        return self._config.get("plugins", {}).get("analyzers", {}).get(language)

    def get_premium_plugin(self, plugin_type: str) -> Optional[str]:
        """Get premium plugin configuration."""
        return self._config.get("premium", {}).get(plugin_type)

    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = self._load_config()

    @property
    def raw_config(self) -> Dict[str, Any]:
        """Get the raw configuration dictionary."""
        return self._config.copy()