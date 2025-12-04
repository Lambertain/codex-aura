"""Impact analysis result wrapper for Codex Aura SDK."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AffectedFile:
    """Represents an affected file in impact analysis."""

    path: str
    impact_type: str  # "direct" or "transitive"
    edges: Optional[List[str]] = None  # For direct impact
    distance: Optional[int] = None  # For transitive impact


@dataclass
class ImpactAnalysis:
    """Impact analysis result wrapper."""

    changed_files: List[str]
    affected_files: List[AffectedFile]
    affected_tests: List[str]

    @property
    def all_affected_files(self) -> List[str]:
        """Get all affected file paths."""
        return [f.path for f in self.affected_files]

    @property
    def direct_affected_files(self) -> List[str]:
        """Get directly affected file paths."""
        return [f.path for f in self.affected_files if f.impact_type == "direct"]

    @property
    def transitive_affected_files(self) -> List[str]:
        """Get transitively affected file paths."""
        return [f.path for f in self.affected_files if f.impact_type == "transitive"]

    def get_files_by_impact_type(self, impact_type: str) -> List[str]:
        """Get files filtered by impact type."""
        return [f.path for f in self.affected_files if f.impact_type == impact_type]

    def get_max_transitive_distance(self) -> int:
        """Get maximum transitive distance."""
        transitive_files = [f for f in self.affected_files if f.impact_type == "transitive" and f.distance is not None]
        if not transitive_files:
            return 0
        return max(f.distance for f in transitive_files)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "changed_files": self.changed_files,
            "affected_files": [
                {
                    "path": f.path,
                    "impact_type": f.impact_type,
                    "edges": f.edges,
                    "distance": f.distance
                }
                for f in self.affected_files
            ],
            "affected_tests": self.affected_tests,
            "summary": {
                "total_affected_files": len(self.affected_files),
                "direct_affected_files": len(self.direct_affected_files),
                "transitive_affected_files": len(self.transitive_affected_files),
                "affected_tests": len(self.affected_tests),
                "max_transitive_distance": self.get_max_transitive_distance()
            }
        }

    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> "ImpactAnalysis":
        """Create ImpactAnalysis from API response data."""
        affected_files = [
            AffectedFile(
                path=file_data["path"],
                impact_type=file_data["impact_type"],
                edges=file_data.get("edges"),
                distance=file_data.get("distance")
            )
            for file_data in response_data["affected_files"]
        ]

        return cls(
            changed_files=response_data["changed_files"],
            affected_files=affected_files,
            affected_tests=response_data["affected_tests"]
        )