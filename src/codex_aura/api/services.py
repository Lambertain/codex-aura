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


def get_service_registry() -> ServiceRegistry:
    """Dependency to get service registry."""
    db = SQLiteStorage()
    return ServiceRegistry(db)


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