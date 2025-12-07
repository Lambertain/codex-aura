"""Tests for Service Registry functionality."""

import pytest
from uuid import uuid4

from ..src.codex_aura.models.service import Service
from ..src.codex_aura.storage.service_registry import ServiceRegistry
from ..src.codex_aura.storage.sqlite import SQLiteStorage


@pytest.fixture
def db():
    """Create a test database."""
    db = SQLiteStorage(":memory:")
    yield db
    # Cleanup if needed


@pytest.fixture
def service_registry(db):
    """Create a service registry for testing."""
    return ServiceRegistry(db)


def test_register_service(service_registry):
    """Test registering a new service."""
    service_id = uuid4()
    repo_id = uuid4()

    service = Service(
        service_id=service_id,
        name="test-service",
        repo_id=repo_id,
        description="Test service"
    )

    service_registry.register_service(service)

    # Verify service was registered
    retrieved = service_registry.get_service_by_id(str(service_id))
    assert retrieved is not None
    assert retrieved.service_id == service_id
    assert retrieved.name == "test-service"
    assert retrieved.repo_id == repo_id
    assert retrieved.description == "Test service"


def test_get_service_by_repo_id(service_registry):
    """Test getting service by repository ID."""
    service_id = uuid4()
    repo_id = uuid4()

    service = Service(
        service_id=service_id,
        name="repo-service",
        repo_id=repo_id
    )

    service_registry.register_service(service)

    # Get by repo ID
    retrieved = service_registry.get_service_by_repo_id(str(repo_id))
    assert retrieved is not None
    assert retrieved.service_id == service_id
    assert retrieved.name == "repo-service"


def test_list_services(service_registry):
    """Test listing all services."""
    # Register multiple services
    services = []
    for i in range(3):
        service_id = uuid4()
        repo_id = uuid4()
        service = Service(
            service_id=service_id,
            name=f"service-{i}",
            repo_id=repo_id
        )
        service_registry.register_service(service)
        services.append(service)

    # List all services
    listed = service_registry.list_services()
    assert len(listed) >= 3

    # Check that our services are in the list
    service_names = {s.name for s in listed}
    assert "service-0" in service_names
    assert "service-1" in service_names
    assert "service-2" in service_names


def test_delete_service(service_registry):
    """Test deleting a service."""
    service_id = uuid4()
    repo_id = uuid4()

    service = Service(
        service_id=service_id,
        name="delete-me",
        repo_id=repo_id
    )

    service_registry.register_service(service)

    # Verify it exists
    assert service_registry.get_service_by_id(str(service_id)) is not None

    # Delete it
    success = service_registry.delete_service(str(service_id))
    assert success

    # Verify it's gone
    assert service_registry.get_service_by_id(str(service_id)) is None


def test_get_service_name_by_repo_id(service_registry):
    """Test getting service name by repository ID."""
    service_id = uuid4()
    repo_id = uuid4()

    service = Service(
        service_id=service_id,
        name="named-service",
        repo_id=repo_id
    )

    service_registry.register_service(service)

    # Get service name
    name = service_registry.get_service_name_by_repo_id(str(repo_id))
    assert name == "named-service"

    # Test with non-existent repo
    name = service_registry.get_service_name_by_repo_id(str(uuid4()))
    assert name is None


def test_service_uuid_validation():
    """Test UUID validation in Service model."""
    service_id = uuid4()
    repo_id = uuid4()

    # Test with UUID objects
    service = Service(
        service_id=service_id,
        name="test",
        repo_id=repo_id
    )
    assert service.service_id == service_id
    assert service.repo_id == repo_id

    # Test with string UUIDs
    service_str = Service(
        service_id=str(service_id),
        name="test",
        repo_id=str(repo_id)
    )
    assert service_str.service_id == service_id
    assert service_str.repo_id == repo_id