import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Directories to ignore
IGNORE_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".git",
    ".tox",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".coverage",
}


def find_python_files(repo_path: Path) -> List[Path]:
    """Find all Python files in a repository, excluding common build/dependency directories.

    Walks through the repository tree and collects all .py files, skipping
    directories that typically contain generated or third-party code.

    Args:
        repo_path: Path to the repository root directory.

    Returns:
        List of absolute paths to Python files in the repository.
    """
    python_files = []

    for root, dirs, files in repo_path.walk():
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file.endswith(".py"):
                file_path = root / file
                # Get relative path from repo root
                try:
                    file_path.relative_to(repo_path)
                    python_files.append(file_path)
                except ValueError:
                    # File is outside repo_path, skip
                    continue

    return python_files
