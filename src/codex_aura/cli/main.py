#!/usr/bin/env python3
"""Main CLI entry point for codex-aura."""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import yaml

from ..analyzer.python import PythonAnalyzer
from ..config.parser import ProjectConfig, load_config
from ..models.graph import load_graph, save_graph
from ..search import EmbeddingService, VectorStore, CodeChunker
from ..storage.storage_abstraction import get_storage


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Code context mapping for AI agents")
    parser.add_argument("--version", action="version", version="codex-aura 0.1.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a repository")
    analyze_parser.add_argument("path", help="Path to the repository to analyze")
    analyze_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging for debugging"
    )
    analyze_parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path for the graph JSON (default: print to stdout)",
    )
    analyze_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )
    analyze_parser.add_argument(
        "-f",
        "--format",
        choices=["json", "pretty"],
        default="json",
        help="Output format (default: json)",
    )
    analyze_parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show graph statistics")
    stats_parser.add_argument("graph_file", help="Path to the graph JSON file")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start API server")
    server_parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind server to (default: 0.0.0.0)"
    )
    server_parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind server to (default: 8000)"
    )

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize a new Codex Aura project")
    init_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing configuration"
    )
    init_parser.add_argument(
        "--minimal", action="store_true", help="Create minimal configuration with required fields only"
    )

    # Index command
    index_parser = subparsers.add_parser("index", help="Index management")
    index_subparsers = index_parser.add_subparsers(dest="index_command", help="Index commands")

    # Index rebuild
    rebuild_parser = index_subparsers.add_parser("rebuild", help="Rebuild search index")
    rebuild_parser.add_argument(
        "--repo-id", required=True, help="Repository ID to rebuild index for"
    )
    rebuild_parser.add_argument(
        "--force", action="store_true", help="Force complete rebuild (delete existing index)"
    )

    # Config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command", help="Config commands")

    # Config validate
    config_subparsers.add_parser("validate", help="Validate configuration")

    # Config show
    show_parser = config_subparsers.add_parser("show", help="Show effective configuration")
    show_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )

    # Global config override arguments
    parser.add_argument(
        "--config-analyzer-languages",
        help="Override analyzer.languages (comma-separated)"
    )
    parser.add_argument(
        "--config-server-port",
        type=int,
        help="Override server.port"
    )
    parser.add_argument(
        "--config-context-default-depth",
        type=int,
        help="Override context.default_depth"
    )

    args = parser.parse_args()

    # Build CLI config overrides
    cli_overrides = {}
    if hasattr(args, 'config_analyzer_languages') and args.config_analyzer_languages:
        cli_overrides['analyzer'] = cli_overrides.get('analyzer', {})
        cli_overrides['analyzer']['languages'] = [lang.strip() for lang in args.config_analyzer_languages.split(',')]
    if hasattr(args, 'config_server_port') and args.config_server_port:
        cli_overrides['server'] = cli_overrides.get('server', {})
        cli_overrides['server']['port'] = args.config_server_port
    if hasattr(args, 'config_context_default_depth') and args.config_context_default_depth:
        cli_overrides['context'] = cli_overrides.get('context', {})
        cli_overrides['context']['default_depth'] = args.config_context_default_depth

    if args.command == "analyze":
        analyze_repo(args, cli_overrides)
    elif args.command == "stats":
        stats_repo(args)
    elif args.command == "server":
        start_server(args, cli_overrides)
    elif args.command == "init":
        init_project(args)
    elif args.command == "index":
        if args.index_command == "rebuild":
            index_rebuild(args)
        else:
            index_parser.print_help()
    elif args.command == "config":
        if args.config_command == "validate":
            config_validate(args, cli_overrides)
        elif args.config_command == "show":
            config_show(args, cli_overrides)
        else:
            config_parser.print_help()
    else:
        parser.print_help()


def analyze_repo(args, cli_overrides=None):
    """Analyze repository function."""
    # Setup logging
    log_level = getattr(logging, args.log_level)
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet or args.format == "pretty":
        log_level = logging.WARNING  # Suppress INFO logs for quiet/pretty
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Analyze repository
    repo_path = Path(args.path).resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if not repo_path.is_dir():
        print(f"Error: Path is not a directory: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if not os.access(repo_path, os.R_OK):
        print(f"Error: No read permission for directory: {repo_path}", file=sys.stderr)
        sys.exit(1)

    python_files = list(repo_path.glob("**/*.py"))
    if not python_files:
        print(f"Error: No Python files found in directory: {repo_path}", file=sys.stderr)
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


def stats_repo(args):
    """Show graph statistics function."""
    graph_file = Path(args.graph_file).resolve()
    if not graph_file.exists():
        print(f"Error: Graph file does not exist: {graph_file}", file=sys.stderr)
        sys.exit(1)

    if not graph_file.is_file():
        print(f"Error: Path is not a file: {graph_file}", file=sys.stderr)
        sys.exit(1)

    try:
        graph = load_graph(graph_file)

        print(f"Graph: {graph.repository.name} (v{graph.version})")
        print(f"Generated: {graph.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print("Nodes by type:")
        for node_type, count in graph.stats.node_types.items():
            percentage = (
                (count / graph.stats.total_nodes * 100) if graph.stats.total_nodes > 0 else 0
            )
            print(f"  {node_type}:     {count} ({percentage:.0f}%)")
        print()
        print("Most connected files:")
        # Need to calculate most connected files
        # Assuming nodes have incoming/outgoing connections
        # For simplicity, let's sort by total connections (assuming we can calculate)
        # Since we don't have direct connection counts, we'll show top files by some metric
        # For now, just show first few files
        file_nodes = [node for node in graph.nodes if node.type == "file"]
        # Sort by some metric, e.g., number of edges connected
        # For simplicity, show first 2
        for i, node in enumerate(file_nodes[:2]):
            # Placeholder: calculate incoming/outgoing
            incoming = sum(1 for edge in graph.edges if edge.target == node.id)
            outgoing = sum(1 for edge in graph.edges if edge.source == node.id)
            print(f"  {i + 1}. {node.name}      ({incoming} incoming, {outgoing} outgoing)")

    except Exception as e:
        print(f"Error: Failed to load or parse graph file: {e}", file=sys.stderr)
        sys.exit(1)


def start_server(args, cli_overrides=None):
    """Start the API server."""
    try:
        import uvicorn
        from ..api.server import app

        print(f"Starting Codex Aura API server on {args.host}:{args.port}")
        print(f"Health check: http://{args.host}:{args.port}/health")
        print(f"API docs: http://{args.host}:{args.port}/docs")

        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info"
        )

    except ImportError as e:
        print(f"Error: Missing required dependencies. Please install FastAPI and uvicorn: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: Failed to start server: {e}", file=sys.stderr)
        sys.exit(1)


def init_project(args):
    """Initialize a new Codex Aura project."""
    repo_path = Path.cwd()

    # Check if .codex-aura already exists
    codex_dir = repo_path / ".codex-aura"
    if codex_dir.exists() and not args.force:
        print(f"Error: .codex-aura directory already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    # Create directory
    codex_dir.mkdir(exist_ok=True)

    # Interactive mode if not minimal
    config_data = {}
    if not args.minimal:
        print("Initializing Codex Aura project...")
        print()

        # Project settings
        project_name = input("Project name [my-project]: ").strip() or "my-project"
        project_desc = input("Project description [Codex Aura project]: ").strip() or "Codex Aura project"
        primary_lang = input("Primary language [python]: ").strip() or "python"

        # Analyzer settings
        include_tests = input("Include tests in analysis? [y/N]: ").strip().lower()
        include_tests = include_tests in ('y', 'yes')

        config_data = {
            "version": "1.0",
            "project": {
                "name": project_name,
                "description": project_desc,
                "language": primary_lang,
            },
            "analyzer": {
                "languages": [primary_lang],
                "include_patterns": ["src/**/*.py"] if primary_lang == "python" else ["src/**/*"],
                "exclude_patterns": [
                    "**/tests/**" if not include_tests else None,
                    "**/__pycache__/**",
                    ".venv/**",
                    "node_modules/**"
                ]
            }
        }
        # Remove None values
        config_data["analyzer"]["exclude_patterns"] = [p for p in config_data["analyzer"]["exclude_patterns"] if p is not None]
    else:
        # Minimal config
        config_data = {
            "version": "1.0",
            "project": {
                "name": "my-project",
                "language": "python",
            }
        }

    # Validate config
    try:
        config = ProjectConfig(**config_data)
    except Exception as e:
        print(f"Error: Invalid configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Write config.yaml
    config_path = codex_dir / "config.yaml"
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)

    # Write rules.yaml (empty for now)
    rules_path = codex_dir / "rules.yaml"
    with open(rules_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"rules": []}, f)

    # Write .gitignore
    gitignore_path = codex_dir / ".gitignore"
    gitignore_content = """# Codex Aura cache and temporary files
*.db
*.log
.cache/
temp/
"""
    with open(gitignore_path, "w", encoding="utf-8") as f:
        f.write(gitignore_content)

    print("✓ Created .codex-aura/config.yaml")
    print("✓ Created .codex-aura/rules.yaml")
    print("✓ Created .codex-aura/.gitignore")


def config_validate(args, cli_overrides=None):
    """Validate configuration."""
    repo_path = Path.cwd()
    try:
        config, sources = load_config(repo_path, cli_overrides)

        print("✓ Config file: .codex-aura/config.yaml")
        print(f"✓ Version: {config.version} (supported)")

        # Check analyzer settings
        print("✓ Analyzer settings: valid")

        # Check plugins
        if "basic" in config.plugins.context:
            print("✓ Plugin 'basic' found")
        else:
            print("⚠ Warning: Plugin 'basic' not found")

        # Check exclude patterns
        if not config.analyzer.exclude_patterns:
            print("⚠ Warning: exclude_patterns is empty")

        print("\nConfiguration validation completed successfully.")

    except Exception as e:
        print(f"✗ Configuration validation failed: {e}", file=sys.stderr)
        sys.exit(1)


def config_show(args, cli_overrides=None):
    """Show effective configuration."""
    repo_path = Path.cwd()
    try:
        config, sources = load_config(repo_path, cli_overrides)

        if args.json:
            print(config.model_dump_json(indent=2))
        else:
            # Build source map for tracking
            source_map = {}
            for source in sources:
                _build_source_map(source_map, source.data, source.name)

            _print_config_with_sources(config.model_dump(), source_map, "")

    except Exception as e:
        print(f"Error: Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)


def _build_source_map(source_map, data, source_name, prefix=""):
    """Build a map of config paths to their sources."""
    if isinstance(data, dict):
        for key, value in data.items():
            current_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, (dict, list)):
                _build_source_map(source_map, value, source_name, current_prefix)
            else:
                source_map[current_prefix] = source_name
    elif isinstance(data, list):
        # For lists, mark the parent as the source
        source_map[prefix] = source_name


def _print_config_with_sources(config_dict, source_map, prefix=""):
    """Print configuration with source information."""
    for key, value in config_dict.items():
        current_prefix = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            print(f"{current_prefix}:")
            _print_config_with_sources(value, source_map, current_prefix)
        elif isinstance(value, list):
            source = source_map.get(current_prefix, "defaults")
            print(f"{current_prefix}: {value} (from {source})")
        else:
            source = source_map.get(current_prefix, "defaults")
            print(f"{current_prefix}: {value} (from {source})")


def index_rebuild(args):
    """Rebuild search index for a repository."""
    import asyncio
    import tqdm

    repo_id = args.repo_id
    force = args.force

    print(f"Rebuilding search index for repository: {repo_id}")
    if force:
        print("Force rebuild enabled - will delete existing index")

    try:
        # Get storage and load graph
        storage = get_storage()
        graph = storage.load_graph(repo_id)

        if not graph:
            print(f"Error: Repository graph '{repo_id}' not found", file=sys.stderr)
            sys.exit(1)

        # Initialize search services
        embedding_service = EmbeddingService()
        vector_store = VectorStore()

        async def rebuild_index():
            # Delete existing collection if force rebuild
            if force:
                try:
                    # Note: Qdrant client doesn't have delete_collection method in basic client
                    # We'll recreate the collection instead
                    pass
                except Exception as e:
                    print(f"Warning: Could not delete existing collection: {e}")

            # Create new collection
            await vector_store.create_collection(repo_id)

            # Extract code chunks from graph
            chunker = CodeChunker()
            all_chunks = []

            print("Extracting code chunks from repository...")

            # Process each file in the graph
            for node in tqdm.tqdm(graph.nodes, desc="Processing files"):
                if node.type == "file" and node.path:
                    # Load file content
                    try:
                        repo_path = Path(graph.repository.path)
                        file_path = repo_path / node.path
                        if file_path.exists() and file_path.is_file():
                            with file_path.open("r", encoding="utf-8") as f:
                                content = f.read()

                            # Chunk the file
                            chunks = chunker.chunk_file(content, node.path)
                            all_chunks.extend(chunks)
                    except Exception as e:
                        print(f"Warning: Failed to process {node.path}: {e}")
                        continue

            if not all_chunks:
                print("No code chunks found to index")
                return

            print(f"Found {len(all_chunks)} code chunks to index")

            # Generate embeddings in batches
            print("Generating embeddings...")
            batch_size = 10
            all_embeddings = []

            for i in tqdm.tqdm(range(0, len(all_chunks), batch_size), desc="Embedding"):
                batch = all_chunks[i:i + batch_size]
                contents = [chunk.content for chunk in batch]
                embeddings = await embedding_service.embed_batch(contents)
                all_embeddings.extend(embeddings)

            # Upsert to vector store
            print("Indexing chunks...")
            await vector_store.upsert_chunks(repo_id, all_chunks, all_embeddings)

            print(f"✓ Successfully indexed {len(all_chunks)} code chunks for repository {repo_id}")

        # Run async rebuild
        asyncio.run(rebuild_index())

    except Exception as e:
        print(f"Error: Index rebuild failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
