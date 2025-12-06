# Sync module for incremental graph updates

from enum import Enum
from dataclasses import dataclass

class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class FileChange:
    path: str
    change_type: ChangeType
    old_path: str | None = None  # для renamed


from .change_detection import ChangeDetector, GitDiff, DiffStats
from .partial_analysis import PartialAnalyzer, PartialAnalysisResult
from .incremental import (
    IncrementalUpdateResult,
    IncrementalGraphUpdater, BatchIncrementalUpdater
)

__all__ = [
    'ChangeDetector', 'GitDiff', 'DiffStats',
    'PartialAnalyzer', 'PartialAnalysisResult',
    'ChangeType', 'FileChange', 'IncrementalUpdateResult',
    'IncrementalGraphUpdater', 'BatchIncrementalUpdater'
]