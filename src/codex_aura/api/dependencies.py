"""API endpoints for dependency scanning."""

from typing import List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..analyzer.dependency_service import DependencyScanService
from ..storage.neo4j_client import Neo4jClient
from ..models.graph import Graph

router = APIRouter(prefix="/api/v1/dependencies", tags=["dependencies"])


class DependencyScanRequest(BaseModel):
    """Request model for dependency scanning."""
    repo_paths: List[str]
    graph_sha: Optional[str] = None


class DependencyScanResponse(BaseModel):
    """Response model for dependency scanning."""
    graph_id: str
    services_found: int
    dependencies_found: int
    status: str = "completed"


class DependencyGraphResponse(BaseModel):
    """Response model for dependency graph retrieval."""
    graph: Graph
    services_count: int
    dependencies_count: int


@router.post("/scan", response_model=DependencyScanResponse)
async def scan_dependencies(
    request: DependencyScanRequest,
    background_tasks: BackgroundTasks
) -> DependencyScanResponse:
    """
    Scan multiple repositories for inter-service dependencies.

    This endpoint analyzes code across repositories to find:
    - HTTP calls between services
    - gRPC client connections
    - Kafka topic usage
    - Import-like references

    Results are stored in Neo4j as (:ServiceA)-[:SERVICE_CALLS]->(:ServiceB) relationships.
    """
    try:
        # Convert string paths to Path objects
        repo_paths = [Path(path) for path in request.repo_paths]

        # Validate paths exist
        for path in repo_paths:
            if not path.exists():
                raise HTTPException(400, f"Repository path does not exist: {path}")
            if not path.is_dir():
                raise HTTPException(400, f"Path is not a directory: {path}")

        # Initialize service
        neo4j_client = Neo4jClient()
        service = DependencyScanService(neo4j_client)

        try:
            # Scan and store dependencies
            graph_id = await service.scan_and_store_dependencies(repo_paths, request.graph_sha)

            # Get basic stats (this is a simplified version - in production you'd query Neo4j)
            dependency_graph = await service.scan_repositories(repo_paths)
            services_count = len(dependency_graph.nodes)
            dependencies_count = len(dependency_graph.edges)

            return DependencyScanResponse(
                graph_id=graph_id,
                services_found=services_count,
                dependencies_found=dependencies_count,
                status="completed"
            )

        finally:
            await service.close()

    except Exception as e:
        raise HTTPException(500, f"Dependency scan failed: {str(e)}")


@router.post("/scan-async")
async def scan_dependencies_async(
    request: DependencyScanRequest,
    background_tasks: BackgroundTasks
):
    """
    Start asynchronous dependency scanning.

    Returns immediately with a job ID. Use /status endpoint to check progress.
    """
    # For now, just run synchronously. In production, this would enqueue to a job queue
    background_tasks.add_task(_run_dependency_scan, request)
    return {"status": "started", "message": "Dependency scan queued"}


async def _run_dependency_scan(request: DependencyScanRequest):
    """Background task to run dependency scanning."""
    try:
        repo_paths = [Path(path) for path in request.repo_paths]
        neo4j_client = Neo4jClient()
        service = DependencyScanService(neo4j_client)

        try:
            await service.scan_and_store_dependencies(repo_paths, request.graph_sha)
            print(f"Dependency scan completed for {len(repo_paths)} repositories")
        finally:
            await service.close()
    except Exception as e:
        print(f"Dependency scan failed: {str(e)}")


@router.get("/graph/{graph_id}", response_model=DependencyGraphResponse)
async def get_dependency_graph(graph_id: str) -> DependencyGraphResponse:
    """
    Get dependency graph by ID.

    Note: This is a simplified implementation. In production, you'd query Neo4j
    to reconstruct the graph from stored data.
    """
    # This would need implementation to query Neo4j and reconstruct the graph
    raise HTTPException(501, "Graph retrieval not yet implemented")


@router.get("/services")
async def list_services():
    """
    List all discovered services.

    Returns service names and their metadata.
    """
    neo4j_client = Neo4jClient()
    try:
        query = """
        MATCH (s:Service)
        RETURN s.name as name, s.path as path, s.repo_id as repo_id
        ORDER BY s.name
        """
        results = await neo4j_client.execute_query(query)
        return {"services": results}
    finally:
        await neo4j_client.close()


@router.get("/dependencies")
async def list_dependencies():
    """
    List all service dependencies.

    Returns relationships between services.
    """
    neo4j_client = Neo4jClient()
    try:
        query = """
        MATCH (source:Service)-[r:SERVICE_CALLS]->(target:Service)
        RETURN source.name as source, target.name as target, r.line as line
        ORDER BY source.name, target.name
        """
        results = await neo4j_client.execute_query(query)
        return {"dependencies": results}
    finally:
        await neo4j_client.close()