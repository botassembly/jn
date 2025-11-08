"""CLI commands: jn new source <driver> - create sources."""

import typer

from jn import ConfigPath, ConfigPathType, config

app = typer.Typer(help="Create a new source")


@app.command()
def exec(
    name: str,
    jn: ConfigPathType = ConfigPath,
    argv: list[str] = typer.Option(
        ...,
        "--argv",
        help="Command arguments",
    ),
    env: list[str] = typer.Option(
        [],
        "--env",
        help="Environment variable (K=V)",
    ),
    cwd: str | None = typer.Option(
        None,
        "--cwd",
        help="Working directory",
    ),
    adapter: str | None = typer.Option(
        None,
        "--adapter",
        help="Adapter for non-JSON output (e.g., 'jc')",
    ),
) -> None:
    """Create a new exec source."""
    config.set_config_path(jn)
    env_dict = config.parse_key_value_pairs(env) if env else None

    result = config.add_source(
        name,
        "exec",
        argv=argv,
        env=env_dict,
        cwd=cwd,
        adapter=adapter,
    )

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")


@app.command()
def shell(
    name: str,
    jn: ConfigPathType = ConfigPath,
    cmd: str = typer.Option(
        ...,
        "--cmd",
        help="Shell command",
    ),
    adapter: str | None = typer.Option(
        None,
        "--adapter",
        help="Adapter for non-JSON output (e.g., 'jc')",
    ),
) -> None:
    """Create a new shell source."""
    config.set_config_path(jn)

    result = config.add_source(name, "shell", cmd=cmd, adapter=adapter)

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")


@app.command()
def curl(
    name: str,
    jn: ConfigPathType = ConfigPath,
    url: str = typer.Option(
        ...,
        "--url",
        help="URL to request",
    ),
    method: str = typer.Option(
        "GET",
        "--method",
        help="HTTP method (GET, POST, PUT, DELETE, etc.)",
    ),
    header: list[str] = typer.Option(
        [],
        "--header",
        help="HTTP header (format: 'Key: Value')",
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        help="Request timeout in seconds",
    ),
    retry: int = typer.Option(
        0,
        "--retry",
        help="Number of retry attempts",
    ),
    retry_delay: int = typer.Option(
        2,
        "--retry-delay",
        help="Initial delay between retries in seconds",
    ),
    no_follow_redirects: bool = typer.Option(
        False,
        "--no-follow-redirects",
        help="Do not follow HTTP redirects",
    ),
    allow_errors: bool = typer.Option(
        False,
        "--allow-errors",
        help="Do not fail on HTTP 4xx/5xx status codes",
    ),
) -> None:
    """Create a new curl source (HTTP GET/POST/etc)."""
    config.set_config_path(jn)

    # Parse headers from "Key: Value" format
    headers_dict = {}
    for h in header:
        if ": " in h:
            key, value = h.split(": ", 1)
            headers_dict[key] = value
        else:
            typer.echo(
                f"Invalid header format: '{h}' (use 'Key: Value')", err=True
            )
            raise typer.Exit(1)

    result = config.add_source(
        name,
        "curl",
        url=url,
        method=method,
        headers=headers_dict if headers_dict else None,
        timeout=timeout,
        retry=retry,
        retry_delay=retry_delay,
        follow_redirects=not no_follow_redirects,
        fail_on_error=not allow_errors,
    )

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")


@app.command()
def file(
    name: str,
    jn: ConfigPathType = ConfigPath,
    path: str = typer.Option(
        ...,
        "--path",
        help="File path to read",
    ),
    allow_outside_config: bool = typer.Option(
        False,
        "--allow-outside-config",
        help="Allow reading files outside config root",
    ),
    adapter: str | None = typer.Option(
        None,
        "--adapter",
        help="Adapter for non-JSON output (e.g., 'csv')",
    ),
    csv_delimiter: str | None = typer.Option(
        None,
        "--csv-delimiter",
        help="CSV delimiter character (default: ',')",
    ),
    csv_quotechar: str | None = typer.Option(
        None,
        "--csv-quotechar",
        help="CSV quote character (default: '\"')",
    ),
    csv_encoding: str | None = typer.Option(
        None,
        "--csv-encoding",
        help="CSV file encoding (default: 'utf-8')",
    ),
    csv_no_header: bool = typer.Option(
        False,
        "--csv-no-header",
        help="CSV has no header row",
    ),
) -> None:
    """Create a new file source."""
    config.set_config_path(jn)

    # Build CSV config if adapter is csv
    csv_config = None
    if adapter == "csv":
        csv_config = {}
        if csv_delimiter is not None:
            csv_config["delimiter"] = csv_delimiter
        if csv_quotechar is not None:
            csv_config["quotechar"] = csv_quotechar
        if csv_encoding is not None:
            csv_config["encoding"] = csv_encoding
        if csv_no_header:
            csv_config["has_header"] = False

    result = config.add_source(
        name,
        "file",
        path=path,
        allow_outside_config=allow_outside_config,
        adapter=adapter,
        csv=csv_config,
    )

    if isinstance(result, config.Error):
        typer.echo(str(result), err=True)
        raise typer.Exit(1)

    typer.echo(f"Created source '{result.name}' with driver '{result.driver}'")
