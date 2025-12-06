import subprocess
import asyncio
from dataclasses import dataclass
from pathlib import Path

from . import ChangeType, FileChange


@dataclass
class GitDiff:
    old_sha: str
    new_sha: str
    changes: list[FileChange]
    stats: 'DiffStats'


@dataclass
class DiffStats:
    files_changed: int
    insertions: int
    deletions: int


class ChangeDetector:
    """Detect file changes between git commits."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    async def detect_changes(
        self,
        old_sha: str,
        new_sha: str
    ) -> GitDiff:
        """
        Get list of changed files between two commits.

        Uses `git diff --name-status` for file-level changes.
        """
        # Run git diff
        cmd = [
            "git", "diff", "--name-status",
            "--no-renames",  # Handle renames separately
            old_sha, new_sha
        ]

        result = await self._run_git(cmd)
        changes = self._parse_diff_output(result)

        # Get stats
        stats_cmd = ["git", "diff", "--stat", old_sha, new_sha]
        stats_result = await self._run_git(stats_cmd)
        stats = self._parse_stats(stats_result)

        return GitDiff(
            old_sha=old_sha,
            new_sha=new_sha,
            changes=changes,
            stats=stats
        )

    async def detect_renames(
        self,
        old_sha: str,
        new_sha: str,
        similarity_threshold: int = 50
    ) -> list[FileChange]:
        """Detect renamed files using git's rename detection."""
        cmd = [
            "git", "diff", "--name-status",
            f"-M{similarity_threshold}%",  # Rename detection threshold
            "--diff-filter=R",  # Only renames
            old_sha, new_sha
        ]

        result = await self._run_git(cmd)
        renames = []

        for line in result.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].startswith("R"):
                renames.append(FileChange(
                    path=parts[2],  # new path
                    old_path=parts[1],  # old path
                    change_type=ChangeType.RENAMED
                ))

        return renames

    async def get_file_at_commit(
        self,
        file_path: str,
        sha: str
    ) -> str | None:
        """Get file content at a specific commit."""
        cmd = ["git", "show", f"{sha}:{file_path}"]
        try:
            return await self._run_git(cmd)
        except subprocess.CalledProcessError:
            return None  # File didn't exist at this commit

    async def get_changed_lines(
        self,
        file_path: str,
        old_sha: str,
        new_sha: str
    ) -> tuple[list[int], list[int]]:
        """
        Get specific line numbers that changed.
        Returns (added_lines, removed_lines).
        """
        cmd = [
            "git", "diff",
            "--unified=0",  # No context lines
            old_sha, new_sha,
            "--", file_path
        ]

        result = await self._run_git(cmd)
        return self._parse_line_changes(result)

    async def _run_git(self, cmd: list[str]) -> str:
        """Run git command asynchronously."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, stderr.decode()
            )

        return stdout.decode()

    def _parse_diff_output(self, output: str) -> list[FileChange]:
        """Parse git diff --name-status output."""
        changes = []

        for line in output.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            status = parts[0]
            path = parts[1] if len(parts) > 1 else ""

            change_type = {
                "A": ChangeType.ADDED,
                "M": ChangeType.MODIFIED,
                "D": ChangeType.DELETED,
            }.get(status[0], ChangeType.MODIFIED)

            changes.append(FileChange(path=path, change_type=change_type))

        return changes

    def _parse_stats(self, output: str) -> DiffStats:
        """Parse git diff --stat output."""
        lines = output.strip().split("\n")
        if not lines:
            return DiffStats(0, 0, 0)

        # Last line contains summary
        summary = lines[-1]
        # "3 files changed, 10 insertions(+), 5 deletions(-)"

        import re
        files = re.search(r"(\d+) files? changed", summary)
        insertions = re.search(r"(\d+) insertions?", summary)
        deletions = re.search(r"(\d+) deletions?", summary)

        return DiffStats(
            files_changed=int(files.group(1)) if files else 0,
            insertions=int(insertions.group(1)) if insertions else 0,
            deletions=int(deletions.group(1)) if deletions else 0
        )

    def _parse_line_changes(self, diff_output: str) -> tuple[list[int], list[int]]:
        """Parse unified diff to get changed line numbers."""
        added_lines = []
        removed_lines = []

        import re
        # Match @@ -start,count +start,count @@
        hunk_pattern = re.compile(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

        current_old_line = 0
        current_new_line = 0

        for line in diff_output.split("\n"):
            hunk_match = hunk_pattern.match(line)
            if hunk_match:
                current_old_line = int(hunk_match.group(1))
                current_new_line = int(hunk_match.group(3))
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(current_new_line)
                current_new_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(current_old_line)
                current_old_line += 1
            elif not line.startswith("\\"):
                current_old_line += 1
                current_new_line += 1

        return added_lines, removed_lines