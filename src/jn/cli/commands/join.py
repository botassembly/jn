"""Join command - enrich stream with data from secondary source."""

import json
import subprocess
import sys
from collections import defaultdict
from typing import Iterator, Optional

import click

from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import (
    build_subprocess_env_for_coverage,
    check_uv_available,
)


def _make_key(record: dict, fields: list[str]) -> str | None:
    """Create a composite key from multiple fields.

    Args:
        record: The record to extract key from
        fields: List of field names to use for the key

    Returns:
        A string key (tuple repr for composite), or None if any field missing.
    """
    values = []
    for field in fields:
        value = record.get(field)
        if value is None:
            return None
        values.append(str(value))

    # Single field: just the value string
    # Multiple fields: tuple-like representation
    if len(values) == 1:
        return values[0]
    return tuple(values).__repr__()


def _load_right_side(
    source: str,
    right_fields: list[str],
    pick_fields: Optional[tuple[str, ...]],
    home_dir=None,
) -> dict[str, list[dict]]:
    """Load right source into a lookup table.

    Args:
        source: Data source address (file, URL, profile)
        right_fields: Field names to use as lookup key
        pick_fields: Optional tuple of field names to include
        home_dir: JN home directory (overrides $JN_HOME)

    Returns:
        Dict mapping key values to lists of matching records.
    """
    lookup: dict[str, list[dict]] = defaultdict(list)

    proc = popen_with_validation(
        [sys.executable, "-m", "jn.cli.main", "cat", source],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=build_subprocess_env_for_coverage(home_dir=home_dir),
    )

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                click.echo(
                    f"Warning: Skipping invalid JSON in right source: {line[:50]}...",
                    err=True,
                )
                continue

            key_str = _make_key(record, right_fields)
            if key_str is None:
                continue

            # Apply field selection if specified
            if pick_fields:
                record = {k: record[k] for k in pick_fields if k in record}

            lookup[key_str].append(record)

        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read()
            raise click.ClickException(
                f"Right source '{source}' failed: {err}"
            )

    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait()

    return dict(lookup)


def _stream_and_enrich(
    lookup: dict[str, list[dict]],
    left_fields: list[str],
    target: str,
    inner_join: bool,
) -> Iterator[dict]:
    """Stream stdin and enrich with lookup data.

    Args:
        lookup: Dict mapping key values to lists of matching records
        left_fields: Field names in left records to match on
        target: Field name for embedded array of matches
        inner_join: If True, only emit records with matches

    Yields:
        Enriched records with matches embedded in target field.
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            click.echo(
                f"Warning: Skipping invalid JSON in left source: {line[:50]}...",
                err=True,
            )
            continue

        key_str = _make_key(record, left_fields)
        matches = lookup.get(key_str, []) if key_str else []

        # Inner join: skip records with no matches
        if inner_join and not matches:
            continue

        # Embed matches into target field
        record[target] = matches
        yield record


@click.command()
@click.argument("right_source")
@click.option(
    "--on",
    "on_fields",
    help="Field(s) to join on (same name on both sides). Comma-separated for composite key.",
)
@click.option(
    "--left-on",
    "left_on",
    help="Field(s) in left (stdin) records. Comma-separated for composite key.",
)
@click.option(
    "--right-on",
    "right_on",
    help="Field(s) in right source records. Comma-separated for composite key.",
)
@click.option(
    "--target",
    required=True,
    help="Field name for embedded array of matches.",
)
@click.option(
    "--inner",
    "inner_join",
    is_flag=True,
    default=False,
    help="Only emit records with matches (inner join).",
)
@click.option(
    "--pick",
    "pick_fields",
    multiple=True,
    help="Fields to include from right records (can repeat).",
)
@pass_context
def join(
    ctx,
    right_source,
    on_fields,
    left_on,
    right_on,
    target,
    inner_join,
    pick_fields,
):
    """Enrich NDJSON stream with data from a secondary source.

    Reads stdin as the primary (left) stream and enriches each record
    with matching records from the right source, embedded as an array.

    This is a Hash Join: the right source is buffered into memory,
    while the left source streams with constant memory.

    \b
    Examples:
        # Simple join (same field name)
        jn cat customers.csv | jn join orders.csv \\
          --on customer_id --target orders

        # Different field names
        jn cat users.csv | jn join purchases.csv \\
          --left-on id --right-on user_id --target purchases

        # Composite key join (multiple fields)
        jn cat symbols.ndjson | jn join coverage.ndjson \\
          --on file,function --target coverage

        # Inner join - only emit matches
        jn cat left.csv | jn join right.csv \\
          --on id --target matches --inner

        # Pick specific fields from right
        jn cat left.csv | jn join right.csv \\
          --on id --target data --pick name --pick value

    \b
    Output format (left join):
        {"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
        {"id": 2, "name": "Bob", "orders": []}

    Note: The right source is fully buffered in memory. For very large
    right sources, consider filtering before joining.
    """
    try:
        check_uv_available()

        # Resolve field names
        if on_fields:
            # --on specifies same field(s) for both sides
            left_fields = [f.strip() for f in on_fields.split(",")]
            right_fields = left_fields
        elif left_on and right_on:
            # Different field names on each side
            left_fields = [f.strip() for f in left_on.split(",")]
            right_fields = [f.strip() for f in right_on.split(",")]
        else:
            raise click.ClickException(
                "Must specify either --on or both --left-on and --right-on"
            )

        # Validate composite key lengths match
        if len(left_fields) != len(right_fields):
            raise click.ClickException(
                f"Key field count mismatch: left has {len(left_fields)}, "
                f"right has {len(right_fields)}"
            )

        # Phase 1: Load right side into lookup table
        lookup = _load_right_side(
            right_source,
            right_fields,
            pick_fields if pick_fields else None,
            home_dir=ctx.home,
        )

        # Phase 2 & 3: Stream left side and enrich
        for record in _stream_and_enrich(
            lookup, left_fields, target, inner_join
        ):
            print(json.dumps(record), flush=True)

    except KeyboardInterrupt:
        sys.exit(130)
