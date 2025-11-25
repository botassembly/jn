"""Join command - enrich stream with data from secondary source."""

import json
import subprocess
import sys
from collections import defaultdict
from typing import Iterator, Optional

import click

from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _load_right_side(
    source: str,
    right_key: str,
    pick_fields: Optional[tuple[str, ...]],
    home_dir=None,
) -> dict[str, list[dict]]:
    """Load right source into a lookup table.

    Args:
        source: Data source address (file, URL, profile)
        right_key: Field name to use as lookup key
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

            key_value = record.get(right_key)
            if key_value is None:
                continue

            # Convert key to string for consistent matching
            key_str = str(key_value)

            # Apply field selection if specified
            if pick_fields:
                record = {k: record[k] for k in pick_fields if k in record}

            lookup[key_str].append(record)

        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read()
            click.echo(f"Warning: Right source failed: {err}", err=True)

    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait()

    return dict(lookup)


def _stream_and_enrich(
    lookup: dict[str, list[dict]],
    left_key: str,
    target: str,
    inner_join: bool,
) -> Iterator[dict]:
    """Stream stdin and enrich with lookup data.

    Args:
        lookup: Dict mapping key values to lists of matching records
        left_key: Field name in left records to match on
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

        key_value = record.get(left_key)
        key_str = str(key_value) if key_value is not None else None

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
    "--left-key",
    required=True,
    help="Field in left (stdin) records to match on.",
)
@click.option(
    "--right-key",
    required=True,
    help="Field in right source records to match on.",
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
def join(ctx, right_source, left_key, right_key, target, inner_join, pick_fields):
    """Enrich NDJSON stream with data from a secondary source.

    Reads stdin as the primary (left) stream and enriches each record
    with matching records from the right source, embedded as an array.

    This is a Hash Join: the right source is buffered into memory,
    while the left source streams with constant memory.

    \b
    Examples:
        # Enrich customers with their orders
        jn cat customers.csv | jn join orders.csv \\
          --left-key customer_id \\
          --right-key customer_id \\
          --target orders

        # Find functions with their callers
        jn cat coverage.json | jn join callers.json \\
          --left-key function \\
          --right-key callee \\
          --target callers

        # Inner join - only emit matches
        jn cat left.csv | jn join right.csv \\
          --left-key id --right-key id --target matches --inner

        # Pick specific fields from right
        jn cat left.csv | jn join right.csv \\
          --left-key id --right-key id --target data \\
          --pick name --pick value

    \b
    Output format (left join):
        {"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
        {"id": 2, "name": "Bob", "orders": []}

    Note: The right source is fully buffered in memory. For very large
    right sources, consider filtering before joining.
    """
    try:
        check_uv_available()

        # Phase 1: Load right side into lookup table
        lookup = _load_right_side(
            right_source,
            right_key,
            pick_fields if pick_fields else None,
            home_dir=ctx.home,
        )

        # Phase 2 & 3: Stream left side and enrich
        for record in _stream_and_enrich(lookup, left_key, target, inner_join):
            print(json.dumps(record), flush=True)

    except KeyboardInterrupt:
        sys.exit(130)
