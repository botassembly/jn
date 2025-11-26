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
    check_jq_available,
    check_uv_available,
)


def _apply_jq_transform(record: dict, jq_expr: str) -> dict | None:
    """Apply a jq expression to transform a record.

    Args:
        record: The input record to transform
        jq_expr: A jq expression to apply

    Returns:
        Transformed record, or None if transformation fails.
    """
    proc = subprocess.run(  # noqa: S603
        ["jq", "-c", jq_expr],  # noqa: S607
        input=json.dumps(record),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    output = proc.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def _load_right_side(
    source: str,
    right_key: str,
    pick_fields: Optional[tuple[str, ...]],
    home_dir=None,
    transform: Optional[str] = None,
) -> dict[str, list[dict]]:
    """Load right source into a lookup table.

    Args:
        source: Data source address (file, URL, profile)
        right_key: Field name to use as lookup key
        pick_fields: Optional tuple of field names to include
        home_dir: JN home directory (overrides $JN_HOME)
        transform: Optional jq expression to transform records before keying

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

            # Apply transform if specified
            keying_record = record
            if transform:
                keying_record = _apply_jq_transform(record, transform)
                if keying_record is None:
                    continue

            key_value = keying_record.get(right_key)
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
    left_key: str,
    target: str,
    inner_join: bool,
    transform: Optional[str] = None,
) -> Iterator[dict]:
    """Stream stdin and enrich with lookup data.

    Args:
        lookup: Dict mapping key values to lists of matching records
        left_key: Field name in left records to match on
        target: Field name for embedded array of matches
        inner_join: If True, only emit records with matches
        transform: Optional jq expression to transform records before keying

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

        # Apply transform if specified
        keying_record = record
        if transform:
            keying_record = _apply_jq_transform(record, transform)
            if keying_record is None:
                continue

        key_value = keying_record.get(left_key)
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
@click.option(
    "--left-transform",
    "left_transform",
    help="jq expression to transform left records before extracting key.",
)
@click.option(
    "--right-transform",
    "right_transform",
    help="jq expression to transform right records before extracting key.",
)
@pass_context
def join(
    ctx,
    right_source,
    left_key,
    right_key,
    target,
    inner_join,
    pick_fields,
    left_transform,
    right_transform,
):
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

        # Composite key join (normalize paths before joining)
        jn cat symbols.ndjson | jn join coverage.ndjson \\
          --left-transform '. + {_key: (.file + ":" + .function)}' \\
          --right-transform '. + {_key: ((.file | split("/") | .[-1]) + ":" + .function)}' \\
          --left-key _key --right-key _key --target coverage

    \b
    Output format (left join):
        {"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
        {"id": 2, "name": "Bob", "orders": []}

    Note: The right source is fully buffered in memory. For very large
    right sources, consider filtering before joining.
    """
    try:
        check_uv_available()
        if left_transform or right_transform:
            check_jq_available()

        # Phase 1: Load right side into lookup table
        lookup = _load_right_side(
            right_source,
            right_key,
            pick_fields if pick_fields else None,
            home_dir=ctx.home,
            transform=right_transform,
        )

        # Phase 2 & 3: Stream left side and enrich
        for record in _stream_and_enrich(
            lookup, left_key, target, inner_join, transform=left_transform
        ):
            print(json.dumps(record), flush=True)

    except KeyboardInterrupt:
        sys.exit(130)
