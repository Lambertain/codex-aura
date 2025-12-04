#!/usr/bin/env python3
"""Benchmark script to measure performance on the current project."""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codex_aura.analyzer.python import PythonAnalyzer


def count_lines_of_code(repo_path: Path) -> int:
    """Count total lines of code in Python files."""
    total_lines = 0
    for py_file in repo_path.glob("**/*.py"):
        try:
            with py_file.open('r', encoding='utf-8') as f:
                lines = f.readlines()
                # Count non-empty, non-comment lines
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#'):
                        total_lines += 1
        except (UnicodeDecodeError, OSError):
            continue
    return total_lines


def benchmark_current_repo():
    """Benchmark current repository analysis."""
    repo_path = Path(__file__).parent.parent  # codex-aura root
    print(f"Benchmark: {repo_path.name}")

    # Count files and LOC
    python_files = list(repo_path.glob("**/*.py"))
    loc = count_lines_of_code(repo_path)
    print(f"  ({len(python_files)} files, {loc:,} LOC)")
    print()

    # Time file scanning
    start_time = time.time()
    analyzer = PythonAnalyzer(verbose=False)
    scan_time = time.time() - start_time

    # Time AST parsing
    start_time = time.time()
    graph = analyzer.analyze(repo_path)
    parse_time = time.time() - start_time

    # Build graph time is included in parse_time, but we can estimate
    # For simplicity, we'll show total time and breakdown if available
    total_time = scan_time + parse_time

    print("  Scan files:    {:.2f}s".format(scan_time))
    print("  Parse AST:     {:.2f}s".format(parse_time))
    print("  Build graph:   N/A")  # Would need to modify analyzer to separate this
    print("  Total:         {:.2f}s".format(total_time))
    print()

    if total_time > 0:
        loc_per_sec = loc / total_time
        print("Performance: {:,} LOC/sec".format(int(loc_per_sec)))
    else:
        print("Performance: N/A")


def main():
    """Main function."""
    try:
        benchmark_current_repo()
    except Exception as e:
        print(f"Error during benchmarking: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()