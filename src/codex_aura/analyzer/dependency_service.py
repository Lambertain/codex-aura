"""Service for managing multi-repo dependency scanning and storage."""

import asyncio
from pathlib import Path
from typing import List, Optional

from .dependency_scanner import MultiRepoDependencyScanner
from ..storage.neo4j_client import Neo4jClient
from ..models.graph import Graph


class DependencyScanService:
    """Service for scanning and storing inter-service dependencies."""

    def __init__(self, neo4j_client: Optional[Neo4jClient] = None):
        """
        Initialize the dependency scan service.

        Args:
            neo4j_client: Neo4j client for storing results. If None, creates a new one.
        """
        self.scanner = MultiRepoDependencyScanner()
        self.neo4j_client = neo4j_client or Neo4jClient()

    async def scan_and_store_dependencies(self, repo_paths: List[Path], graph_sha: Optional[str] = None) -> str:
        """
        Scan multiple repositories for dependencies and store in Neo4j.

        Args:
            repo_paths: List of paths to repository root directories.
            graph_sha: Optional SHA for the dependency graph.

        Returns:
            Graph ID in Neo4j.
        """
        # Scan repositories
        dependency_graph = self.scanner.analyze(repo_paths)

        # Set SHA if provided
        if graph_sha:
            dependency_graph.sha = graph_sha

        # Store in Neo4j
        graph_id = await self.neo4j_client.save_dependency_graph(dependency_graph)

        return graph_id

    async def scan_repositories(self, repo_paths: List[Path]) -> Graph:
        """
        Scan repositories without storing results.

        Args:
            repo_paths: List of paths to repository root directories.

        Returns:
            Dependency graph.
        """
        return self.scanner.analyze(repo_paths)

    async def close(self):
        """Close the Neo4j client connection."""
        await self.neo4j_client.close()


# Convenience function for CLI usage
async def scan_dependencies_cli(repo_paths: List[str], neo4j_uri: Optional[str] = None) -> str:
    """
    CLI function to scan dependencies.

    Args:
        repo_paths: List of repository path strings.
        neo4j_uri: Optional Neo4j URI.

    Returns:
        Graph ID.
    """
    paths = [Path(p) for p in repo_paths]

    neo4j_client = Neo4jClient(uri=neo4j_uri) if neo4j_uri else Neo4jClient()
    service = DependencyScanService(neo4j_client)

    try:
        graph_id = await service.scan_and_store_dependencies(paths)
        return graph_id
    finally:
        await service.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python dependency_service.py <repo_path1> [repo_path2] ... [--neo4j-uri URI]")
        sys.exit(1)

    repo_paths = []
    neo4j_uri = None

    for arg in sys.argv[1:]:
        if arg.startswith("--neo4j-uri"):
            neo4j_uri = arg.split("=", 1)[1] if "=" in arg else sys.argv[sys.argv.index(arg) + 1]
        else:
            repo_paths.append(arg)

    if not repo_paths:
        print("No repository paths provided")
        sys.exit(1)

    graph_id = asyncio.run(scan_dependencies_cli(repo_paths, neo4j_uri))
    print(f"Dependency graph stored with ID: {graph_id}")