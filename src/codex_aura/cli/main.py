#!/usr/bin/env python3
"""Main CLI entry point for codex-aura."""

import argparse
import logging
import sys
from pathlib import Path

from ..analyzer.python import PythonAnalyzer
from ..models.graph import save_graph


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Code context mapping for AI agents")
    parser.add_argument("--version", action="version", version="codex-aura 0.1.0")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the repository to analyze (default: current directory)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path for the graph JSON (default: print to stdout)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = getattr(logging, args.log_level)
    if args.verbose:
        log_level = logging.DEBUG
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Analyze repository
    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if not repo_path.is_dir():
        print(f"Error: Path is not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)

    try:
        analyzer = PythonAnalyzer(verbose=args.verbose)
        graph = analyzer.analyze(repo_path)

        if args.output:
            output_path = Path(args.output)
            save_graph(graph, output_path)
            print(f"Graph saved to: {output_path}")
        else:
            print(graph.model_dump_json(indent=2))

    except Exception as e:
        logger = logging.getLogger("codex_aura")
        logger.error(f"Analysis failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
