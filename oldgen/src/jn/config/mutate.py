"""Mutation helpers for config objects (add/update operations).

Simplified mutations for apis and filters.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from jn.models import Api, AuthConfig, Error, Filter

from .core import persist, require

__all__ = ["add_api", "add_filter"]


def add_api(
    name: str,
    api_type: Literal[
        "rest", "graphql", "postgres", "mysql", "s3", "gcs", "kafka"
    ] = "rest",
    base_url: Optional[str] = None,
    endpoint: Optional[str] = None,
    auth_type: Optional[
        Literal["bearer", "basic", "oauth2", "api_key"]
    ] = None,
    token: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    api_key: Optional[str] = None,
    header_name: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    source_method: str = "GET",
    target_method: str = "POST",
    # Database fields
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    # Cloud storage fields
    bucket: Optional[str] = None,
    region: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
    # Message queue fields
    brokers: Optional[List[str]] = None,
    topic: Optional[str] = None,
    consumer_group: Optional[str] = None,
) -> Api | Error:
    """Add a new API to the cached config and persist it.

    APIs are generic configurations that can be used as both sources and targets.
    Supports REST, GraphQL, databases, cloud storage, and message queues.

    Environment variable substitution:
    Use ${env:VAR_NAME} in any string field, e.g., token="${env:GITHUB_TOKEN}"
    """

    config_obj = require().model_copy(deep=True)

    if config_obj.has_api(name):
        return Error(message=f"API '{name}' already exists")

    # Build auth config if auth fields provided
    auth = None
    if auth_type:
        auth = AuthConfig(
            type=auth_type,
            token=token,
            username=username,
            password=password,
            api_key=api_key,
            header_name=header_name,
        )

    api = Api(
        name=name,
        type=api_type,
        base_url=base_url,
        endpoint=endpoint,
        headers=headers or {},
        auth=auth,
        source_method=source_method,
        target_method=target_method,
        # Database fields
        host=host,
        port=port,
        database=database,
        user=username,  # Reuse username for DB user
        password=password,
        # Cloud storage fields
        bucket=bucket,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
        # Message queue fields
        brokers=brokers or [],
        topic=topic,
        consumer_group=consumer_group,
    )

    config_obj.apis.append(api)
    persist(config_obj)
    return api


def add_filter(
    name: str,
    query: str,
    description: Optional[str] = None,
) -> Filter | Error:
    """Add a new filter to the cached config and persist it.

    Filters are jq transformations that operate on JSON/NDJSON data.
    The term 'filter' follows jq terminology (not 'converter').

    Args:
        name: Unique name for the filter
        query: jq expression (e.g., "select(.amount > 1000)")
        description: Optional human-readable description

    Returns:
        The created Filter or an Error if filter already exists
    """

    config_obj = require().model_copy(deep=True)

    if config_obj.has_filter(name):
        return Error(message=f"Filter '{name}' already exists")

    if not query:
        return Error(message="Filter query is required (--query)")

    filter_obj = Filter(
        name=name,
        query=query,
        description=description,
    )

    config_obj.filters.append(filter_obj)
    persist(config_obj)
    return filter_obj
