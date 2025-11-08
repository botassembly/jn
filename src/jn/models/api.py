"""API models for the simplified registry architecture.

APIs are generic configurations that can be used as both sources and targets.
They support REST, GraphQL, databases, cloud storage, message queues, and more.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    """Authentication configuration."""

    type: Literal["bearer", "basic", "oauth2", "api_key"] = "bearer"
    token: str | None = None  # Supports ${env:VAR} substitution
    username: str | None = None  # For basic auth
    password: str | None = None  # For basic auth
    api_key: str | None = None  # For API key auth
    header_name: str | None = None  # For API key in header


class Api(BaseModel):
    """API definition (can be source or target).

    Supports multiple API types:
    - REST APIs (default): Use base_url, headers, auth
    - GraphQL: Set type="graphql" with endpoint
    - Databases: Set type="postgres", "mysql", etc.
    - Cloud Storage: Set type="s3", "gcs", etc.
    - Message Queues: Set type="kafka", "rabbitmq", etc.

    Environment variable substitution:
    - Use ${env:VAR_NAME} in any string field
    - Example: "token": "${env:GITHUB_TOKEN}"
    """

    name: str
    type: Literal["rest", "graphql", "postgres", "mysql", "s3", "gcs", "kafka"] = "rest"

    # REST/GraphQL config
    base_url: str | None = None
    endpoint: str | None = None  # For GraphQL
    headers: Dict[str, str] = Field(default_factory=dict)
    auth: AuthConfig | None = None
    source_method: str = "GET"  # Default HTTP method when used as source
    target_method: str = "POST"  # Default HTTP method when used as target

    # Database config (type=postgres, mysql, etc.)
    host: str | None = None
    port: int | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None  # Supports ${env:VAR}

    # Cloud storage config (type=s3, gcs, etc.)
    bucket: str | None = None
    region: str | None = None
    access_key: str | None = None  # Supports ${env:VAR}
    secret_key: str | None = None  # Supports ${env:VAR}

    # Message queue config (type=kafka, rabbitmq, etc.)
    brokers: list[str] = Field(default_factory=list)
    topic: str | None = None
    consumer_group: str | None = None

    # Path templates (for parameterized endpoints)
    paths: Dict[str, str] = Field(default_factory=dict)


__all__ = ["Api", "AuthConfig"]
