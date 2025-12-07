"""Data models for representing services in the Service Registry."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator


class Service(BaseModel):
    """Represents a service in the Service Registry.

    A service is a logical unit that can contain one or more repositories.
    Services are used to group related code and track inter-service dependencies.

    Attributes:
        service_id: Unique identifier for the service (UUID).
        name: Human-readable name of the service.
        repo_id: ID of the primary repository for this service (UUID).
        description: Optional description of the service and its purpose.
    """

    service_id: UUID
    name: str
    repo_id: UUID
    description: Optional[str] = None

    @field_validator("service_id", "repo_id")
    @classmethod
    def validate_uuid(cls, v):
        """Validate that UUID fields are proper UUID objects."""
        if isinstance(v, str):
            return UUID(v)
        return v

    class Config:
        """Pydantic configuration."""
        json_encoders = {
            UUID: str
        }