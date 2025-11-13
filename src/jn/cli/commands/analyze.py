"""Analyze command - inspect NDJSON stream for schema, stats, facets, samples."""

import json
import random
import sys
from collections import Counter, deque
from typing import Any, Dict, List, Optional

import click

from ...context import pass_context


class SchemaTracker:
    """Track schema information for a single field."""

    def __init__(self):
        self.types_seen = Counter()
        self.null_count = 0
        self.total_count = 0
        self.unique_values = set()
        self.numeric_values = []  # For min/max tracking

    def observe(self, value: Any) -> None:
        """Observe a value for this field."""
        self.total_count += 1

        if value is None:
            self.null_count += 1
            self.types_seen["null"] += 1
            return

        # Determine type
        value_type = self._infer_type(value)
        self.types_seen[value_type] += 1

        # Track cardinality (limit to prevent memory issues)
        if len(self.unique_values) < 10000:
            # Use string representation for hashability
            self.unique_values.add(str(value))

        # Track numeric values for stats
        if value_type in ("integer", "number"):
            self.numeric_values.append(float(value))

    def _infer_type(self, value: Any) -> str:
        """Infer JSON type from Python value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, (list, tuple)):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"

    def summarize(self) -> Dict[str, Any]:
        """Generate schema summary for this field."""
        # Determine primary type (most common)
        if not self.types_seen:
            return {"type": "unknown", "nullable": True, "unique": 0}

        primary_type = self.types_seen.most_common(1)[0][0]
        if primary_type == "null" and len(self.types_seen) > 1:
            # If null is most common but other types exist, use second most common
            primary_type = self.types_seen.most_common(2)[1][0]

        result = {
            "type": primary_type,
            "nullable": self.null_count > 0,
            "unique": len(self.unique_values),
        }

        # Add numeric stats if applicable
        if primary_type in ("integer", "number") and self.numeric_values:
            result["min"] = min(self.numeric_values)
            result["max"] = max(self.numeric_values)

        return result


class FacetTracker:
    """Track facet information (categorical value distributions)."""

    def __init__(self, limit: int = 100):
        self.limit = limit
        self.value_counts = Counter()
        self.overflow = False

    def observe(self, value: Any) -> None:
        """Observe a value."""
        if value is None:
            return

        # Convert to string for counting
        str_value = str(value)

        # Only track if under limit
        if not self.overflow:
            self.value_counts[str_value] += 1

            # Check if we've exceeded the limit
            if len(self.value_counts) > self.limit:
                self.overflow = True
                self.value_counts.clear()

    def should_facet(self) -> bool:
        """Determine if this field is suitable for faceting."""
        return not self.overflow and len(self.value_counts) > 0

    def get_facets(self) -> Dict[str, int]:
        """Get facet distribution."""
        if not self.should_facet():
            return {}
        return dict(self.value_counts.most_common())


class StatsTracker:
    """Track statistical information for numeric fields using online algorithms."""

    def __init__(self):
        self.count = 0
        self.null_count = 0
        self.sum = 0.0
        self.sum_squared = 0.0
        self.min_val = None
        self.max_val = None

    def observe(self, value: Any) -> None:
        """Observe a value."""
        if value is None:
            self.null_count += 1
            return

        # Try to convert to numeric
        try:
            num_val = float(value)
        except (TypeError, ValueError):
            return

        self.count += 1
        self.sum += num_val
        self.sum_squared += num_val * num_val

        if self.min_val is None or num_val < self.min_val:
            self.min_val = num_val

        if self.max_val is None or num_val > self.max_val:
            self.max_val = num_val

    def summarize(self) -> Optional[Dict[str, float]]:
        """Generate statistical summary."""
        if self.count == 0:
            return None

        mean = self.sum / self.count
        variance = (self.sum_squared / self.count) - (mean * mean)
        variance = max(0, variance)  # Handle floating point errors

        result = {
            "count": self.count,
            "nulls": self.null_count,
            "min": self.min_val,
            "max": self.max_val,
            "sum": self.sum,
            "mean": mean,
            "variance": variance,
            "stddev": variance**0.5,
        }

        return result


class StreamingAnalyzer:
    """Streaming analyzer for NDJSON data."""

    def __init__(self, sample_size: int = 10, facet_limit: int = 100):
        self.sample_size = sample_size
        self.facet_limit = facet_limit

        self.row_count = 0
        self.schema_trackers: Dict[str, SchemaTracker] = {}
        self.facet_trackers: Dict[str, FacetTracker] = {}
        self.stats_trackers: Dict[str, StatsTracker] = {}

        self.first_samples: List[Dict] = []
        self.last_samples: deque = deque(maxlen=sample_size)
        self.random_samples: List[Dict] = []

    def process(self, record: Dict[str, Any]) -> None:
        """Process a single record."""
        self.row_count += 1

        # Process each field
        for key, value in record.items():
            # Skip metadata fields
            if key.startswith("_"):
                continue

            # Initialize trackers for new fields
            if key not in self.schema_trackers:
                self.schema_trackers[key] = SchemaTracker()
                self.facet_trackers[key] = FacetTracker(self.facet_limit)
                self.stats_trackers[key] = StatsTracker()

            # Update trackers
            self.schema_trackers[key].observe(value)
            self.facet_trackers[key].observe(value)
            self.stats_trackers[key].observe(value)

        # Collect samples
        if len(self.first_samples) < self.sample_size:
            self.first_samples.append(record)

        self.last_samples.append(record)

        # Reservoir sampling for random samples
        if len(self.random_samples) < self.sample_size:
            self.random_samples.append(record)
        else:
            # Randomly replace with decreasing probability
            i = random.randint(0, self.row_count - 1)
            if i < self.sample_size:
                self.random_samples[i] = record

    def finalize(self) -> Dict[str, Any]:
        """Generate final analysis report."""
        # Build schema
        schema = {
            field: tracker.summarize()
            for field, tracker in self.schema_trackers.items()
        }

        # Build facets (only for low-cardinality fields)
        facets = {}
        for field, tracker in self.facet_trackers.items():
            if tracker.should_facet():
                field_facets = tracker.get_facets()
                if field_facets:
                    facets[field] = field_facets

        # Build stats (only for numeric fields with data)
        stats = {}
        for field, tracker in self.stats_trackers.items():
            summary = tracker.summarize()
            if summary:
                stats[field] = summary

        return {
            "rows": self.row_count,
            "columns": len(self.schema_trackers),
            "schema": schema,
            "facets": facets,
            "stats": stats,
            "samples": {
                "first": self.first_samples,
                "last": list(self.last_samples),
                "random": self.random_samples,
            },
        }


@click.command()
@click.option(
    "--sample-size",
    default=10,
    type=int,
    help="Number of sample records to collect",
)
@click.option(
    "--facet-limit",
    default=100,
    type=int,
    help="Maximum unique values for faceting",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"]),
    default="json",
    help="Output format",
)
@pass_context
def analyze(ctx, sample_size, facet_limit, output_format):
    """Analyze NDJSON stream from stdin.

    Computes schema, statistics, facets, and samples in a single streaming pass.

    Examples:
        jn cat data.csv --limit 10000 | jn analyze
        jn cat @api/endpoint | jn filter '.status == "active"' | jn analyze
        jn cat data.json | jn analyze --sample-size 20
    """
    try:
        analyzer = StreamingAnalyzer(sample_size, facet_limit)

        # Process stdin line by line
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    click.echo(
                        f"Warning: Skipping non-object record: {line[:100]}",
                        err=True,
                    )
                    continue

                analyzer.process(record)
            except json.JSONDecodeError as e:
                click.echo(
                    f"Warning: Skipping invalid JSON: {line[:100]} ({e})",
                    err=True,
                )
                continue

        # Generate report
        result = analyzer.finalize()

        # Output
        if output_format == "json":
            click.echo(json.dumps(result, indent=2))
        else:
            # Text format
            click.echo(f"Rows: {result['rows']}")
            click.echo(f"Columns: {result['columns']}")
            click.echo()

            click.echo("Schema:")
            for field, info in result["schema"].items():
                nullable = " (nullable)" if info.get("nullable") else ""
                unique = info.get("unique", 0)
                click.echo(f"  {field}: {info['type']}{nullable} ({unique} unique)")

            if result["facets"]:
                click.echo()
                click.echo("Facets:")
                for field, counts in result["facets"].items():
                    click.echo(f"  {field}:")
                    for value, count in list(counts.items())[:10]:
                        click.echo(f"    {value}: {count}")

            if result["stats"]:
                click.echo()
                click.echo("Statistics:")
                for field, stats in result["stats"].items():
                    click.echo(f"  {field}:")
                    click.echo(f"    Count: {stats['count']} (nulls: {stats['nulls']})")
                    click.echo(f"    Min: {stats['min']:.2f}")
                    click.echo(f"    Max: {stats['max']:.2f}")
                    click.echo(f"    Mean: {stats['mean']:.2f}")
                    click.echo(f"    StdDev: {stats['stddev']:.2f}")

    except KeyboardInterrupt:
        click.echo("Interrupted", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
