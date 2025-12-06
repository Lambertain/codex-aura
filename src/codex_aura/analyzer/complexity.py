"""Cyclomatic complexity analysis using radon library."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from radon.complexity import cc_visit, cc_rank
    from radon.visitors import ComplexityVisitor
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

logger = logging.getLogger("codex_aura")


class ComplexityResult:
    """Result of complexity analysis for a single function/method."""

    def __init__(
        self,
        name: str,
        complexity: int,
        rank: str,
        lineno: int,
        endline: int,
        is_method: bool = False,
        classname: Optional[str] = None,
    ):
        self.name = name
        self.complexity = complexity
        self.rank = rank  # A, B, C, D, E, F
        self.lineno = lineno
        self.endline = endline
        self.is_method = is_method
        self.classname = classname

    @property
    def full_name(self) -> str:
        """Get fully qualified name including class if method."""
        if self.classname:
            return f"{self.classname}::{self.name}"
        return self.name

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "full_name": self.full_name,
            "complexity": self.complexity,
            "rank": self.rank,
            "lineno": self.lineno,
            "endline": self.endline,
            "is_method": self.is_method,
            "classname": self.classname,
        }


class FileComplexityResult:
    """Complexity analysis results for an entire file."""

    def __init__(
        self,
        path: str,
        functions: List[ComplexityResult],
        average_complexity: float,
        total_complexity: int,
    ):
        self.path = path
        self.functions = functions
        self.average_complexity = average_complexity
        self.total_complexity = total_complexity

    @property
    def max_complexity(self) -> int:
        """Get the maximum complexity in this file."""
        if not self.functions:
            return 0
        return max(f.complexity for f in self.functions)

    @property
    def hotspots(self) -> List[ComplexityResult]:
        """Get functions with complexity rank C or worse (complexity >= 11)."""
        return [f for f in self.functions if f.complexity >= 11]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "functions": [f.to_dict() for f in self.functions],
            "average_complexity": round(self.average_complexity, 2),
            "total_complexity": self.total_complexity,
            "max_complexity": self.max_complexity,
            "hotspot_count": len(self.hotspots),
        }


def analyze_file_complexity(file_path: Path) -> Optional[FileComplexityResult]:
    """Analyze cyclomatic complexity of a Python file using radon.

    Args:
        file_path: Path to the Python file to analyze.

    Returns:
        FileComplexityResult with complexity metrics, or None if analysis fails.
    """
    if not RADON_AVAILABLE:
        logger.warning("radon library not available. Install with: pip install radon")
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Use radon's cc_visit to get complexity for all functions
        blocks = cc_visit(source)

        if not blocks:
            # No functions/methods found
            return FileComplexityResult(
                path=str(file_path),
                functions=[],
                average_complexity=0.0,
                total_complexity=0,
            )

        functions = []
        total_complexity = 0

        for block in blocks:
            # block can be Function or Class containing methods
            if hasattr(block, "methods"):
                # It's a class - process methods
                for method in block.methods:
                    result = ComplexityResult(
                        name=method.name,
                        complexity=method.complexity,
                        rank=cc_rank(method.complexity),
                        lineno=method.lineno,
                        endline=method.endlineno,
                        is_method=True,
                        classname=block.name,
                    )
                    functions.append(result)
                    total_complexity += method.complexity
            else:
                # It's a standalone function
                result = ComplexityResult(
                    name=block.name,
                    complexity=block.complexity,
                    rank=cc_rank(block.complexity),
                    lineno=block.lineno,
                    endline=block.endlineno,
                    is_method=False,
                )
                functions.append(result)
                total_complexity += block.complexity

        avg_complexity = total_complexity / len(functions) if functions else 0.0

        return FileComplexityResult(
            path=str(file_path),
            functions=functions,
            average_complexity=avg_complexity,
            total_complexity=total_complexity,
        )

    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error analyzing complexity for {file_path}: {e}")
        return None


def analyze_directory_complexity(
    directory: Path,
    ignore_patterns: Optional[List[str]] = None
) -> Dict[str, FileComplexityResult]:
    """Analyze complexity of all Python files in a directory.

    Args:
        directory: Root directory to analyze.
        ignore_patterns: Optional list of glob patterns to ignore.

    Returns:
        Dictionary mapping file paths to their complexity results.
    """
    if not RADON_AVAILABLE:
        logger.warning("radon library not available. Install with: pip install radon")
        return {}

    results = {}

    # Find all Python files
    for py_file in directory.rglob("*.py"):
        # Skip common ignore patterns
        rel_path = py_file.relative_to(directory)
        path_str = str(rel_path)

        # Default ignores
        if any(part.startswith(".") for part in rel_path.parts):
            continue
        if any(part in ("__pycache__", "venv", "node_modules", ".git") for part in rel_path.parts):
            continue

        result = analyze_file_complexity(py_file)
        if result:
            results[path_str] = result

    return results


def get_complexity_summary(results: Dict[str, FileComplexityResult]) -> dict:
    """Generate a summary of complexity across all analyzed files.

    Args:
        results: Dictionary of file paths to complexity results.

    Returns:
        Summary dictionary with aggregate metrics.
    """
    if not results:
        return {
            "total_files": 0,
            "total_functions": 0,
            "average_complexity": 0.0,
            "max_complexity": 0,
            "hotspots": [],
            "rank_distribution": {},
        }

    all_functions = []
    for file_result in results.values():
        all_functions.extend(file_result.functions)

    if not all_functions:
        return {
            "total_files": len(results),
            "total_functions": 0,
            "average_complexity": 0.0,
            "max_complexity": 0,
            "hotspots": [],
            "rank_distribution": {},
        }

    # Calculate metrics
    total_complexity = sum(f.complexity for f in all_functions)
    avg_complexity = total_complexity / len(all_functions)
    max_complexity = max(f.complexity for f in all_functions)

    # Find hotspots (rank C or worse)
    hotspots = sorted(
        [f for f in all_functions if f.complexity >= 11],
        key=lambda x: x.complexity,
        reverse=True,
    )[:10]  # Top 10 hotspots

    # Calculate rank distribution
    rank_distribution = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0, "F": 0}
    for func in all_functions:
        rank_distribution[func.rank] = rank_distribution.get(func.rank, 0) + 1

    return {
        "total_files": len(results),
        "total_functions": len(all_functions),
        "average_complexity": round(avg_complexity, 2),
        "max_complexity": max_complexity,
        "hotspots": [
            {
                "name": f.full_name,
                "complexity": f.complexity,
                "rank": f.rank,
                "file": next(
                    (path for path, r in results.items() if f in r.functions),
                    "unknown",
                ),
            }
            for f in hotspots
        ],
        "rank_distribution": rank_distribution,
    }


def get_complexity_rank_description(rank: str) -> str:
    """Get human-readable description of complexity rank.

    Args:
        rank: Complexity rank (A-F).

    Returns:
        Description of what the rank means.
    """
    descriptions = {
        "A": "Low - simple block (1-5)",
        "B": "Low - well structured (6-10)",
        "C": "Moderate - slightly complex (11-20)",
        "D": "More than moderate - more complex (21-30)",
        "E": "High - complex, alarming (31-40)",
        "F": "Very high - error-prone, unstable (41+)",
    }
    return descriptions.get(rank, "Unknown rank")
