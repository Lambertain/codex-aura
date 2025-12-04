"""Tests for configuration system."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from codex_aura.config.parser import (
    ConfigSource,
    ProjectConfig,
    _merge_configs,
    _parse_env_vars,
    load_config,
    load_config_simple,
)


class TestConfigParsing:
    """Test configuration parsing functionality."""

    def test_parse_env_vars_simple(self):
        """Test parsing simple environment variables."""
        # Set up test environment
        test_env = {
            "CODEX_AURA_PROJECT__NAME": "test-project",
            "CODEX_AURA_ANALYZER__LANGUAGES": "python,javascript",
            "CODEX_AURA_SERVER__PORT": "9000",
            "CODEX_AURA_CONTEXT__DEFAULT_DEPTH": "5",
        }

        # Mock environment
        original_env = os.environ.copy()
        os.environ.update(test_env)

        try:
            result = _parse_env_vars()
            expected = {
                "project": {"name": "test-project"},
                "analyzer": {"languages": ["python", "javascript"]},
                "server": {"port": 9000},
                "context": {"default_depth": 5},
            }
            assert result == expected
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)

    def test_parse_env_vars_boolean(self):
        """Test parsing boolean environment variables."""
        test_env = {
            "CODEX_AURA_CONTEXT__INCLUDE_DOCSTRINGS": "true",
            "CODEX_AURA_CONTEXT__INCLUDE_CODE": "false",
        }

        original_env = os.environ.copy()
        os.environ.update(test_env)

        try:
            result = _parse_env_vars()
            expected = {
                "context": {
                    "include_docstrings": True,
                    "include_code": False,
                }
            }
            assert result == expected
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_merge_configs(self):
        """Test merging multiple configurations."""
        config1 = {"version": "1.0", "project": {"name": "default"}}
        config2 = {"project": {"name": "override", "description": "test"}}
        config3 = {"server": {"port": 9000}}

        result = _merge_configs(config1, config2, config3)

        expected = {
            "version": "1.0",
            "project": {"name": "override", "description": "test"},
            "server": {"port": 9000},
        }

        assert result == expected


class TestConfigLoading:
    """Test configuration loading from different sources."""

    def test_load_config_defaults_only(self):
        """Test loading config with defaults only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            config, sources = load_config(repo_path)

            assert isinstance(config, ProjectConfig)
            assert config.version == "1.0"
            assert config.project.name == "my-project"
            assert len(sources) == 1
            assert sources[0].name == "defaults"

    def test_load_config_with_file(self):
        """Test loading config with config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            # Create .codex-aura directory and config file
            codex_dir = repo_path / ".codex-aura"
            codex_dir.mkdir()
            config_file = codex_dir / "config.yaml"

            test_config = {
                "version": "1.0",
                "project": {
                    "name": "test-project",
                    "description": "Test project",
                },
                "analyzer": {
                    "languages": ["python", "javascript"],
                },
            }

            with open(config_file, "w") as f:
                yaml.safe_dump(test_config, f)

            config, sources = load_config(repo_path)

            assert config.project.name == "test-project"
            assert config.project.description == "Test project"
            assert config.analyzer.languages == ["python", "javascript"]
            assert len(sources) == 2
            assert sources[0].name == "defaults"
            assert sources[1].name == "config.yaml"

    def test_load_config_with_env_vars(self):
        """Test loading config with environment variables."""
        test_env = {
            "CODEX_AURA_PROJECT__NAME": "env-project",
            "CODEX_AURA_SERVER__PORT": "9000",
        }

        original_env = os.environ.copy()
        os.environ.update(test_env)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir)

                config, sources = load_config(repo_path)

                assert config.project.name == "env-project"
                assert config.server.port == 9000
                assert len(sources) == 2
                assert sources[0].name == "defaults"
                assert sources[1].name == "environment"
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_load_config_with_cli_overrides(self):
        """Test loading config with CLI overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            cli_overrides = {
                "analyzer": {"languages": ["typescript"]},
                "server": {"port": 8080},
            }

            config, sources = load_config(repo_path, cli_overrides)

            assert config.analyzer.languages == ["typescript"]
            assert config.server.port == 8080
            assert len(sources) == 2
            assert sources[0].name == "defaults"
            assert sources[1].name == "cli"

    def test_load_config_priority_order(self):
        """Test that config sources follow priority order."""
        # Set up environment
        test_env = {
            "CODEX_AURA_PROJECT__NAME": "env-name",
            "CODEX_AURA_SERVER__PORT": "9000",
        }

        original_env = os.environ.copy()
        os.environ.update(test_env)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                repo_path = Path(tmpdir)

                # Create config file
                codex_dir = repo_path / ".codex-aura"
                codex_dir.mkdir()
                config_file = codex_dir / "config.yaml"

                file_config = {
                    "project": {"name": "file-name", "description": "from file"},
                    "server": {"port": 8000},
                }

                with open(config_file, "w") as f:
                    yaml.safe_dump(file_config, f)

                # CLI overrides
                cli_overrides = {
                    "server": {"port": 8080},
                }

                config, sources = load_config(repo_path, cli_overrides)

                # Check priority: defaults < file < env < cli
                assert config.project.name == "env-name"  # env overrides file
                assert config.project.description == "from file"  # file provides this
                assert config.server.port == 8080  # cli overrides env
                assert len(sources) == 4

        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_load_config_simple_backwards_compatibility(self):
        """Test load_config_simple for backwards compatibility."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)

            config = load_config_simple(repo_path)

            assert isinstance(config, ProjectConfig)
            assert config.version == "1.0"


class TestConfigValidation:
    """Test configuration validation."""

    def test_config_validation_basic(self):
        """Test basic config validation."""
        config = ProjectConfig()
        # Should not raise exception
        assert config.version == "1.0"

    def test_config_validation_invalid(self):
        """Test config validation with invalid data."""
        with pytest.raises(ValueError):
            ProjectConfig(analyzer={"languages": 123})  # languages should be a list