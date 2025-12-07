"""Service Registry management."""

from typing import List, Optional
from uuid import UUID

from ..models.service import Service
from .sqlite import SQLiteStorage


class ServiceRegistry:
    """Manages the Service Registry."""

    def __init__(self, db: SQLiteStorage):
        self.db = db

    def register_service(self, service: Service) -> None:
        """Register or update a service in the registry.

        Args:
            service: Service to register
        """
        self.db.save_service(service)

    def get_service_by_repo_id(self, repo_id: str) -> Optional[Service]:
        """Get service by repository ID.

        Args:
            repo_id: Repository ID

        Returns:
            Service object or None if not found
        """
        return self.db.get_service_by_repo_id(repo_id)

    def get_service_by_id(self, service_id: str) -> Optional[Service]:
        """Get service by service ID.

        Args:
            service_id: Service ID

        Returns:
            Service object or None if not found
        """
        return self.db.get_service_by_id(service_id)

    def list_services(self) -> List[Service]:
        """List all services in the registry.

        Returns:
            List of Service objects
        """
        return self.db.list_services()

    def delete_service(self, service_id: str) -> bool:
        """Delete a service from the registry.

        Args:
            service_id: Service ID to delete

        Returns:
            True if deleted, False if not found
        """
        return self.db.delete_service(service_id)

    def get_service_name_by_repo_id(self, repo_id: str) -> Optional[str]:
        """Get service name by repository ID.

        Args:
            repo_id: Repository ID

        Returns:
            Service name or None if not found
        """
        service = self.get_service_by_repo_id(repo_id)
        return service.name if service else None