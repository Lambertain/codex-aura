import logging
import subprocess
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from pathspec import PathSpec

from ..config import load_config_simple
from ..models.git import ChangeFrequency, GitInfo
from ..models.node import BlameInfo

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


def find_python_files(repo_path: Path, ignore_patterns: PathSpec | None = None) -> List[Path]:
    """Find all Python files in a repository, excluding ignored patterns.

    Walks through the repository tree and collects all .py files, skipping
    files and directories that match the ignore patterns.

    Args:
        repo_path: Path to the repository root directory.
        ignore_patterns: Optional PathSpec with ignore patterns to apply.

    Returns:
        List of absolute paths to Python files in the repository.
    """
    python_files = []

    for root, dirs, files in repo_path.walk():
        # Filter out ignored directories (legacy support)
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            if file.endswith(".py"):
                file_path = root / file
                # Get relative path from repo root
                try:
                    relative_path = file_path.relative_to(repo_path)
                except ValueError:
                    # File is outside repo_path, skip
                    continue

                # Check against ignore patterns
                if ignore_patterns and ignore_patterns.match_file(str(relative_path)):
                    continue

                python_files.append(file_path)

    return python_files


def load_ignore_patterns(repo_path: Path) -> PathSpec:
    """Load ignore patterns from built-in, config, and .ignore file.

    Combines patterns from:
    - Built-in patterns (common directories like __pycache__, .git, etc.)
    - Config file exclude_patterns
    - .codex-aura/.ignore file

    Args:
        repo_path: Path to the repository root directory.

    Returns:
        PathSpec object with all ignore patterns.
    """
    patterns = []

    # Built-in patterns
    patterns.extend([
        "__pycache__/",
        "*.pyc",
        ".git/",
        ".venv/",
        "venv/",
        "node_modules/",
    ])

    # From config
    config = load_config_simple(repo_path)
    patterns.extend(config.analyzer.exclude_patterns)

    # From .codex-aura/.ignore
    ignore_file = repo_path / ".codex-aura" / ".ignore"
    if ignore_file.exists():
        patterns.extend(ignore_file.read_text().splitlines())

    return PathSpec.from_lines("gitwildmatch", patterns)


def get_file_blame(file_path: Path, repo_path: Path) -> BlameInfo | None:
    """Get git blame information for a file.

    Runs git blame to extract authorship information including
    primary author, contributors, and author distribution.

    Args:
        file_path: Path to the file to analyze.
        repo_path: Path to the repository root.

    Returns:
        BlameInfo object with authorship data, or None if not a git repo or error.
    """
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.debug(f"Not a git repository: {repo_path}")
            return None

        # Run git blame
        result = subprocess.run(
            ["git", "blame", "--line-porcelain", str(file_path)],
            cwd=repo_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.warning(f"Git blame failed for {file_path}: {result.stderr}")
            return None

        # Parse blame output
        authors = Counter()
        for line in result.stdout.split("\n"):
            if line.startswith("author "):
                author = line[7:].strip()  # Remove "author " prefix
                authors[author] += 1

        if not authors:
            logger.warning(f"No author information found for {file_path}")
            return None

        primary_author = authors.most_common(1)[0][0]

        return BlameInfo(
            primary_author=primary_author,
            contributors=list(authors.keys()),
            author_distribution=dict(authors)
        )

    except Exception as e:
        logger.warning(f"Error getting blame info for {file_path}: {e}")
        return None


def get_change_frequency(
    file_path: Path,
    repo_path: Path,
    days: int = 90
) -> ChangeFrequency | None:
    """Get change frequency information for a file.

    Analyzes git log to count commits that modified the file
    within the specified number of days, and determines if it's a hot spot.

    Args:
        file_path: Path to the file to analyze.
        repo_path: Path to the repository root.
        days: Number of days to look back (default: 90).

    Returns:
        ChangeFrequency object with commit count and hot spot status,
        or None if not a git repo or error.
    """
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.debug(f"Not a git repository: {repo_path}")
            return None

        # Calculate since date
        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Run git log to count commits
        result = subprocess.run(
            ["git", "log", "--since", since_date, "--format=%H", "--", str(file_path)],
            cwd=repo_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.warning(f"Git log failed for {file_path}: {result.stderr}")
            return None

        # Count commits (filter out empty lines)
        commits = [c for c in result.stdout.strip().split("\n") if c]
        commits_count = len(commits)

        # Determine if it's a hot spot (threshold: > 10 commits)
        is_hot_spot = commits_count > 10

        return ChangeFrequency(
            commits_count=commits_count,
            period_days=days,
            is_hot_spot=is_hot_spot
        )

    except Exception as e:
        logger.warning(f"Error getting change frequency for {file_path}: {e}")
        return None


def get_git_info(repo_path: Path) -> GitInfo | None:
    """Get Git repository information.

    Retrieves current branch name, full commit SHA, and nearest tag.

    Args:
        repo_path: Path to the repository root.

    Returns:
        GitInfo object with branch, SHA, and tag information,
        or None if not a git repo or error.
    """
    try:
        # Check if we're in a git repository
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.debug(f"Not a git repository: {repo_path}")
            return None

        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if branch_result.returncode != 0:
            logger.warning(f"Failed to get branch: {branch_result.stderr}")
            return None
        branch = branch_result.stdout.strip()

        # Get full SHA
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        if sha_result.returncode != 0:
            logger.warning(f"Failed to get SHA: {sha_result.stderr}")
            return None
        sha = sha_result.stdout.strip()

        # Get nearest tag (if exists)
        tag_result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        tag = tag_result.stdout.strip() if tag_result.returncode == 0 else None

        return GitInfo(branch=branch, sha=sha, tag=tag)

    except Exception as e:
        logger.warning(f"Error getting git info for {repo_path}: {e}")
        return None
