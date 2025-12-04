"""Data models for Git-related information."""

from typing import Optional

from pydantic import BaseModel


class ChangeFrequency(BaseModel):
    """Represents the frequency of changes for a file.

    Contains information about how often a file has been modified
    within a specified time period, and whether it's considered a hot spot.

    Attributes:
        commits_count: Number of commits that modified the file in the period.
        period_days: Number of days in the analysis period.
        is_hot_spot: Whether the file is considered a hot spot (high change frequency).
    """

    commits_count: int
    period_days: int
    is_hot_spot: bool


class GitInfo(BaseModel):
    """Represents Git repository information.

    Contains information about the current branch, commit SHA, and nearest tag.

    Attributes:
        branch: Current branch name.
        sha: Full SHA of the current commit.
        tag: Nearest tag, or None if no tags exist.
    """

    branch: str
    sha: str
    tag: Optional[str] = None