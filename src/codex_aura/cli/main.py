#!/usr/bin/env python3
"""Main CLI entry point for codex-aura."""

import argparse
import logging
import sys
import time
from pathlib import Path

from ..analyzer.python import PythonAnalyzer
from ..models.graph import save_graph


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Code context mapping for AI agents")
    parser.add_argument("--version", action="version", version="codex-aura 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a repository")
    analyze_parser.add_argument(
        "path",
        help="Path to the repository to analyze"
    )
    analyze_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging for debugging"
    )
    analyze_parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path for the graph JSON (default: print to stdout)"
    )
    analyze_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    analyze_parser.add_argument(
        "-f", "--format",
        choices=["json", "pretty"],
        default="json",
        help="Output format (default: json)"
    )
    analyze_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Minimal output"
    )

    args = parser.parse_args()

    if args.command == "analyze":
        analyze_repo(args)
    else:
        parser.print_help()


def analyze_repo(args):
    """Analyze repository function."""
    # Setup logging
    log_level = getattr(logging, args.log_level)
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet or args.format == "pretty":
        log_level = logging.WARNING  # Suppress INFO logs for quiet/pretty
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
        start_time = time.time()
        analyzer = PythonAnalyzer(verbose=args.verbose)
        graph = analyzer.analyze(repo_path)
        elapsed_time = time.time() - start_time

        if args.quiet:
            # Minimal output
            if args.output:
                output_path = Path(args.output)
                save_graph(graph, output_path)
        elif args.format == "pretty":
            # Pretty formatted output
            print(f"✓ Analyzed: {graph.repository.name}")
            print()
            print("  📊 Statistics:")
            print(f"     Files:     {graph.stats.node_types.get('file', 0)}")
            print(f"     Classes:   {graph.stats.node_types.get('class', 0)}")
            print(f"     Functions: {graph.stats.node_types.get('function', 0)}")
            print(f"     Imports:   {graph.stats.total_edges}")
            print()
            if args.output:
                output_path = Path(args.output)
                save_graph(graph, output_path)
                file_size = output_path.stat().st_size / 1024  # KB
                print(f"  📁 Output: {output_path} ({file_size:.1f} KB)")
            else:
                print("  📁 Output: stdout")
            print(f"  ⏱  Time: {elapsed_time:.1f}s")
        else:  # json format
            if args.output:
                output_path = Path(args.output)
                save_graph(graph, output_path)
                if not args.quiet:
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
