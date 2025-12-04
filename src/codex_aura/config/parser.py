"""Configuration parser with Pydantic validation."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import BaseModel, Field


class ProjectSettings(BaseModel):
    """Project-specific settings."""

    name: str = "my-project"
    description: str = "Codex Aura project"
    language: str = "python"


class AnalyzerSettings(BaseModel):
    """Analyzer configuration."""

    languages: List[str] = Field(default_factory=lambda: ["python"])
    edge_types: List[str] = Field(default_factory=lambda: ["IMPORTS", "CALLS", "EXTENDS"])
    include_patterns: List[str] = Field(default_factory=lambda: ["src/**/*.py"])
    exclude_patterns: List[str] = Field(default_factory=lambda: [
        "**/tests/**",
        "**/__pycache__/**",
        ".venv/**",
        "node_modules/**"
    ])


class ContextSettings(BaseModel):
    """Context analysis settings."""

    default_depth: int = 2
    default_max_nodes: int = 100
    include_docstrings: bool = True
    include_code: bool = True
    include_comments: bool = False
    max_tokens_per_node: int = 500


class ServerSettings(BaseModel):
    """API server settings."""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    workers: int = 1
    log_level: str = "INFO"


class PluginSettings(BaseModel):
    """Plugin configuration."""

    context: dict = Field(default_factory=lambda: {"default": "basic", "fallback": "basic"})
    impact: dict = Field(default_factory=lambda: {"default": "basic", "fallback": "basic"})
    analyzers: dict = Field(default_factory=lambda: {"python": "codex_aura.plugins.builtin.python"})


class ConfigSource:
    """Configuration source tracking."""

    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data


class ProjectConfig(BaseModel):
    """Main project configuration."""

    version: str = "1.0"
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    analyzer: AnalyzerSettings = Field(default_factory=AnalyzerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)


def _parse_env_vars() -> Dict[str, Any]:
    """Parse CODEX_AURA_* environment variables."""
    env_config = {}
    prefix = "CODEX_AURA_"

    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Remove prefix and convert to lowercase with underscores
            config_key = key[len(prefix):].lower()

            # Handle nested keys with double underscores
            if "__" in config_key:
                parts = config_key.split("__")
                if len(parts) == 2:
                    section, field = parts
                    if section not in env_config:
                        env_config[section] = {}
                    env_config[section][field] = _parse_env_value(value)
            else:
                env_config[config_key] = _parse_env_value(value)

    return env_config


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value to appropriate type."""
    # Handle comma-separated lists
    if "," in value:
        return [item.strip() for item in value.split(",")]

    # Handle booleans
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # Handle numbers
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    # Return as string
    return value


def _merge_configs(*configs: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple config dictionaries with later ones taking precedence."""
    result = {}

    for config in configs:
        _deep_merge(result, config)

    return result


def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """Deep merge source into target."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def load_config(repo_path: Path, cli_overrides: Optional[Dict[str, Any]] = None) -> Tuple[ProjectConfig, List[ConfigSource]]:
    """Load configuration with inheritance: defaults < config.yaml < env vars < CLI args."""
    sources = []

    # 1. Built-in defaults
    defaults = ProjectConfig().model_dump()
    sources.append(ConfigSource("defaults", defaults))

    # 2. Config file
    config_path = repo_path / ".codex-aura" / "config.yaml"
    file_config = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            file_config = yaml.safe_load(f) or {}
        sources.append(ConfigSource("config.yaml", file_config))

    # 3. Environment variables
    env_config = _parse_env_vars()
    if env_config:
        sources.append(ConfigSource("environment", env_config))

    # 4. CLI overrides
    cli_config = cli_overrides or {}
    if cli_config:
        sources.append(ConfigSource("cli", cli_config))

    # Merge all configs in priority order
    merged_config = _merge_configs(defaults, file_config, env_config, cli_config)

    # Create final config
    config = ProjectConfig(**merged_config)

    return config, sources


def load_config_simple(repo_path: Path, cli_overrides: Optional[Dict[str, Any]] = None) -> ProjectConfig:
    """Load configuration (backwards compatibility)."""
    config, _ = load_config(repo_path, cli_overrides)
    return config