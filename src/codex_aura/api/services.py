"""API endpoints for Service Registry management."""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from ..models.service import Service
from ..storage.service_registry import ServiceRegistry
from ..storage.sqlite import SQLiteStorage

# Assuming these imports exist
# from ..auth import get_current_user
# from ..database import get_db

router = APIRouter(prefix="/api/v1/services", tags=["services"])


class ServiceCreateRequest(BaseModel):
    """Request model for creating a service."""
    service_id: UUID
    name: str
    repo_id: UUID
    description: Optional[str] = None


class ServiceUpdateRequest(BaseModel):
    """Request model for updating a service."""
    name: Optional[str] = None
    description: Optional[str] = None


class ServiceGraphNode(BaseModel):
    """Node model for service graph response."""
    service_id: str
    name: str


class ServiceGraphEdge(BaseModel):
    """Edge model for service graph response."""
    source: str
    target: str
    type: str


class ServiceGraphResponse(BaseModel):
    """Response model for service graph endpoint."""
    nodes: List[ServiceGraphNode]
    edges: List[ServiceGraphEdge]


def get_service_registry() -> ServiceRegistry:
    """Dependency to get service registry."""
    db = SQLiteStorage()
    return ServiceRegistry(db)


def get_neo4j_client():
    """Dependency to get Neo4j client."""
    # Import locally to avoid circular imports
    from ..storage.neo4j_client import Neo4jClient
    return Neo4jClient()


@router.post("/", response_model=Service)
async def create_service(
    request: ServiceCreateRequest,
    service_registry: ServiceRegistry = Depends(get_service_registry)
    # current_user: User = Depends(get_current_user)
):
    """Create a new service in the registry."""
    service = Service(
        service_id=request.service_id,
        name=request.name,
        repo_id=request.repo_id,
        description=request.description
    )

    service_registry.register_service(service)
    return service


@router.get("/", response_model=List[Service])
async def list_services(
    service_registry: ServiceRegistry = Depends(get_service_registry)
    # current_user: User = Depends(get_current_user)
):
    """List all services in the registry."""
    return service_registry.list_services()


@router.get("/{service_id}", response_model=Service)
async def get_service(
    service_id: str,
    service_registry: ServiceRegistry = Depends(get_service_registry)
    # current_user: User = Depends(get_current_user)
):
    """Get a service by ID."""
    service = service_registry.get_service_by_id(service_id)
    if not service:
        raise HTTPException(404, "Service not found")
    return service


@router.put("/{service_id}", response_model=Service)
async def update_service(
    service_id: str,
    request: ServiceUpdateRequest,
    service_registry: ServiceRegistry = Depends(get_service_registry)
    # current_user: User = Depends(get_current_user)
):
    """Update a service."""
    service = service_registry.get_service_by_id(service_id)
    if not service:
        raise HTTPException(404, "Service not found")

    # Update fields
    if request.name is not None:
        service.name = request.name
    if request.description is not None:
        service.description = request.description

    service_registry.register_service(service)
    return service


@router.delete("/{service_id}")
async def delete_service(
    service_id: str,
    service_registry: ServiceRegistry = Depends(get_service_registry)
    # current_user: User = Depends(get_current_user)
):
    """Delete a service from the registry."""
    success = service_registry.delete_service(service_id)
    if not success:
        raise HTTPException(404, "Service not found")
    return {"status": "deleted"}


@router.get("/repo/{repo_id}", response_model=Service)
async def get_service_by_repo(
    repo_id: str,
    service_registry: ServiceRegistry = Depends(get_service_registry)
    # current_user: User = Depends(get_current_user)
):
    """Get service by repository ID."""
    service = service_registry.get_service_by_repo_id(repo_id)
    if not service:
        raise HTTPException(404, "Service not found for this repository")
    return service


@router.get("/graph", response_model=ServiceGraphResponse)
async def get_service_graph(
    service_registry: ServiceRegistry = Depends(get_service_registry),
    neo4j_client: Neo4jClient = Depends(get_neo4j_client)
    # current_user: User = Depends(get_current_user)
):
    """Get cross-repo service dependency graph.

    Returns all services as nodes and their inter-service call relationships as edges.
    Optimized for dashboard visualization with < 200ms response time.
    """
    # Get all services
    services = service_registry.list_services()

    # Create nodes from services
    nodes = [
        ServiceGraphNode(
            service_id=str(service.service_id),
            name=service.name
        )
        for service in services
    ]

    # Query Neo4j for SERVICE_CALLS edges between services
    query = """
    MATCH (source:Service)-[r:SERVICE_CALLS]->(target:Service)
    RETURN source.name as source_name, target.name as target_name, type(r) as edge_type
    """

    try:
        results = await neo4j_client.execute_query(query)

        # Create edges from Neo4j results
        edges = []
        for record in results:
            # Find source and target service IDs by name
            source_service = next(
                (s for s in services if s.name == record["source_name"]), None
            )
            target_service = next(
                (s for s in services if s.name == record["target_name"]), None
            )

            if source_service and target_service:
                edges.append(ServiceGraphEdge(
                    source=str(source_service.service_id),
                    target=str(target_service.service_id),
                    type=record["edge_type"]
                ))

    except Exception as e:
        # If Neo4j is not available or has no data, return empty edges
        # This allows the endpoint to work even without Neo4j connection
        edges = []

    return ServiceGraphResponse(nodes=nodes, edges=edges)