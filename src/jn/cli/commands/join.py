"""Join command - enrich stream with data from secondary source."""

import json
import re
import subprocess
import sys
from collections import defaultdict
from typing import Iterator, Optional

import click

from ...context import pass_context
from ...process_utils import popen_with_validation
from ..helpers import build_subprocess_env_for_coverage, check_uv_available


def _eval_where(expr: str, left: dict, right: dict) -> bool:
    """Evaluate a where expression against combined left+right record.

    Supports expressions like:
        .line >= .start_line and .line <= .end_line
        .x > .y
        .type == "function"

    Uses simple Python evaluation with field access.
    """
    # Create combined context - right fields can reference left fields
    combined = {**left, **right}

    # Replace .field with combined['field']
    def replace_field(match):
        field = match.group(1)
        return f"combined.get('{field}')"

    # Pattern matches .fieldname
    py_expr = re.sub(r'\.([a-zA-Z_][a-zA-Z0-9_]*)', replace_field, expr)

    # Replace 'and' and 'or' (jq style) to Python
    py_expr = py_expr.replace(' and ', ' and ')
    py_expr = py_expr.replace(' or ', ' or ')

    try:
        return bool(eval(py_expr, {"combined": combined, "__builtins__": {}}))
    except Exception:
        return False


def _parse_agg_spec(spec: str) -> list[tuple[str, str, Optional[str]]]:
    """Parse aggregation spec like "total: count, hit: sum(.executed)".

    Returns list of (output_name, function, field) tuples.
    """
    result = []
    for part in spec.split(','):
        part = part.strip()
        if ':' in part:
            name, func_expr = part.split(':', 1)
            name = name.strip()
            func_expr = func_expr.strip()
        else:
            # No name, use function as name
            func_expr = part
            name = func_expr.split('(')[0] if '(' in func_expr else func_expr

        # Parse function and optional field
        if '(' in func_expr:
            match = re.match(r'(\w+)\(([^)]*)\)', func_expr)
            if match:
                func = match.group(1)
                field = match.group(2).strip()
                # Remove leading dot from field
                if field.startswith('.'):
                    field = field[1:]
                result.append((name, func, field if field else None))
            else:
                result.append((name, func_expr, None))
        else:
            result.append((name, func_expr, None))

    return result


def _aggregate(matches: list[dict], agg_spec: str) -> dict:
    """Aggregate matches according to spec.

    Supports: count, sum(field), avg(field), min(field), max(field)
    """
    parsed = _parse_agg_spec(agg_spec)
    result = {}

    for name, func, field in parsed:
        if func == 'count':
            result[name] = len(matches)
        elif func == 'sum':
            values = [m.get(field, 0) for m in matches]
            # Convert booleans to int
            values = [int(v) if isinstance(v, bool) else v for v in values]
            result[name] = sum(v for v in values if isinstance(v, (int, float)))
        elif func == 'avg':
            values = [m.get(field) for m in matches]
            values = [v for v in values if isinstance(v, (int, float))]
            result[name] = sum(values) / len(values) if values else 0
        elif func == 'min':
            values = [m.get(field) for m in matches]
            values = [v for v in values if v is not None]
            result[name] = min(values) if values else None
        elif func == 'max':
            values = [m.get(field) for m in matches]
            values = [v for v in values if v is not None]
            result[name] = max(values) if values else None

    return result


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
    target: Optional[str],
    inner_join: bool,
    where_expr: Optional[str] = None,
    agg_spec: Optional[str] = None,
) -> Iterator[dict]:
    """Stream stdin and enrich with lookup data.

    Args:
        lookup: Dict mapping key values to lists of matching records
        left_key: Field name in left records to match on
        target: Field name for embedded array of matches (None if aggregating)
        inner_join: If True, only emit records with matches
        where_expr: Optional expression to filter matches
        agg_spec: Optional aggregation spec (if set, aggregate instead of embed)

    Yields:
        Enriched records with matches embedded or aggregated.
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

        # Apply where filter if specified
        if where_expr and matches:
            matches = [m for m in matches if _eval_where(where_expr, record, m)]

        # Inner join: skip records with no matches
        if inner_join and not matches:
            continue

        # Aggregate or embed
        if agg_spec:
            # Add aggregation results to record
            record.update(_aggregate(matches, agg_spec))
        else:
            # Embed matches into target field
            record[target] = matches

        yield record


@click.command()
@click.argument("right_source")
@click.option(
    "--on",
    "join_field",
    help="Field to join on (natural join, same field name in both sources).",
)
@click.option(
    "--left-key",
    help="Field in left (stdin) records to match on.",
)
@click.option(
    "--right-key",
    help="Field in right source records to match on.",
)
@click.option(
    "--target",
    help="Field name for embedded array of matches (not needed with --agg).",
)
@click.option(
    "--where",
    "where_expr",
    help="Expression to filter matches (e.g., '.line >= .start_line').",
)
@click.option(
    "--agg",
    "agg_spec",
    help="Aggregation spec (e.g., 'total: count, hit: sum(.executed)').",
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
    ctx, right_source, join_field, left_key, right_key, target, where_expr,
    agg_spec, inner_join, pick_fields
):
    """Enrich NDJSON stream with data from a secondary source.

    Reads stdin as the primary (left) stream and enriches each record
    with matching records from the right source, embedded as an array
    or aggregated inline.

    This is a Hash Join: the right source is buffered into memory,
    while the left source streams with constant memory.

    \b
    Examples:
        # Natural join - same field name in both sources
        jn cat customers.csv | jn join orders.csv --on customer_id --target orders

        # Join with range condition (coverage analysis)
        jn cat functions.json | jn join coverage.lcov \\
          --on file \\
          --where ".line >= .start_line and .line <= .end_line" \\
          --target lines

        # Aggregate instead of embedding
        jn cat functions.json | jn join coverage.lcov \\
          --on file \\
          --where ".line >= .start_line and .line <= .end_line" \\
          --agg "total: count, hit: sum(.executed)"

        # Different field names
        jn cat customers.csv | jn join orders.csv \\
          --left-key customer_id --right-key cust_id --target orders

        # Inner join - only emit matches
        jn cat left.csv | jn join right.csv --on id --target matches --inner

        # Pick specific fields from right
        jn cat left.csv | jn join right.csv --on id --target data \\
          --pick name --pick value

    \b
    Aggregation functions:
        count           - Number of matches
        sum(.field)     - Sum of field values
        avg(.field)     - Average of field values
        min(.field)     - Minimum value
        max(.field)     - Maximum value

    \b
    Output format (left join):
        {"id": 1, "name": "Alice", "orders": [{"order_id": "O1"}, {"order_id": "O2"}]}
        {"id": 2, "name": "Bob", "orders": []}

    Output format (with --agg):
        {"id": 1, "name": "Alice", "total": 2, "hit": 1}

    Note: The right source is fully buffered in memory. For very large
    right sources, consider filtering before joining.
    """
    try:
        check_uv_available()

        # Resolve join keys: --on is shortcut for same field name
        if join_field:
            effective_left_key = join_field
            effective_right_key = join_field
        elif left_key and right_key:
            effective_left_key = left_key
            effective_right_key = right_key
        else:
            raise click.ClickException(
                "Must specify --on or both --left-key and --right-key"
            )

        # Validate target vs agg
        if not agg_spec and not target:
            raise click.ClickException(
                "Must specify --target (for embedding) or --agg (for aggregation)"
            )

        # Phase 1: Load right side into lookup table
        lookup = _load_right_side(
            right_source,
            effective_right_key,
            pick_fields if pick_fields else None,
            home_dir=ctx.home,
        )

        # Phase 2 & 3: Stream left side and enrich
        for record in _stream_and_enrich(
            lookup,
            effective_left_key,
            target,
            inner_join,
            where_expr=where_expr,
            agg_spec=agg_spec,
        ):
            print(json.dumps(record), flush=True)

    except KeyboardInterrupt:
        sys.exit(130)
