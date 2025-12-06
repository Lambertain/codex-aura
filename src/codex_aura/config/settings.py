"""Application settings."""

import os
from typing import Optional

from pydantic import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Stripe settings
    stripe_secret_key: Optional[str] = os.getenv("STRIPE_SECRET_KEY")

    # Database settings
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")

    # OpenAI settings
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")

    # Qdrant settings
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()