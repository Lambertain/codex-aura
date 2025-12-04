"""Configuration parser with Pydantic validation."""

from pathlib import Path
from typing import List, Optional

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


class ProjectConfig(BaseModel):
    """Main project configuration."""

    version: str = "1.0"
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    analyzer: AnalyzerSettings = Field(default_factory=AnalyzerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)


def load_config(repo_path: Path) -> ProjectConfig:
    """Load configuration from .codex-aura/config.yaml or return defaults."""
    config_path = repo_path / ".codex-aura" / "config.yaml"

    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return ProjectConfig(**data)

    return ProjectConfig()  # defaults