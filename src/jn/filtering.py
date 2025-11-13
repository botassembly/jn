"""Filter building utilities for converting query parameters to jq expressions."""

import json
from typing import Dict, List, Tuple
from urllib.parse import unquote


def parse_operator(param_name: str) -> Tuple[str, str]:
    """Parse operator from parameter name.

    Supports:
    - field=value → (field, "==")
    - field>value → (field, ">")
    - field<value → (field, "<")
    - field>=value → (field, ">=")
    - field<=value → (field, "<=")
    - field!=value → (field, "!=")

    Args:
        param_name: Parameter name potentially with operator

    Returns:
        Tuple of (field_name, operator)

    Examples:
        >>> parse_operator("revenue>1000")
        ("revenue", ">")
        >>> parse_operator("category")
        ("category", "==")
    """
    # Check for two-char operators first
    if ">=" in param_name:
        field, _ = param_name.split(">=", 1)
        return field, ">="
    elif "<=" in param_name:
        field, _ = param_name.split("<=", 1)
        return field, "<="
    elif "!=" in param_name:
        field, _ = param_name.split("!=", 1)
        return field, "!="
    # Then single-char operators
    elif ">" in param_name:
        field, _ = param_name.split(">", 1)
        return field, ">"
    elif "<" in param_name:
        field, _ = param_name.split("<", 1)
        return field, "<"
    else:
        # No operator, default to equality
        return param_name, "=="


def parse_filter_params(params: Dict[str, str]) -> List[Tuple[str, str, str]]:
    """Parse filter parameters into (field, operator, value) tuples.

    Args:
        params: Dictionary of parameter name to value

    Returns:
        List of (field, operator, value) tuples

    Examples:
        >>> parse_filter_params({"revenue>": "1000", "category": "Electronics"})
        [("revenue", ">", "1000"), ("category", "==", "Electronics")]
    """
    filters = []
    for param_name, value in params.items():
        field, operator = parse_operator(param_name)
        filters.append((field, operator, value))
    return filters


def infer_value_type(value: str) -> any:
    """Infer the appropriate type for a filter value.

    Args:
        value: String value from query parameter

    Returns:
        Value converted to appropriate type (int, float, bool, or string)

    Examples:
        >>> infer_value_type("123")
        123
        >>> infer_value_type("12.34")
        12.34
        >>> infer_value_type("true")
        True
        >>> infer_value_type("hello")
        "hello"
    """
    # Try boolean
    if value.lower() in ("true", "false"):
        return value.lower() == "true"

    # Try integer
    try:
        return int(value)
    except ValueError:
        pass

    # Try float
    try:
        return float(value)
    except ValueError:
        pass

    # Default to string
    return value


def format_jq_condition(field: str, operator: str, value: any) -> str:
    """Format a single jq condition.

    Args:
        field: Field name
        operator: Comparison operator (==, >, <, etc.)
        value: Value to compare (already typed)

    Returns:
        jq expression string

    Examples:
        >>> format_jq_condition("revenue", ">", 1000)
        ".revenue > 1000"
        >>> format_jq_condition("category", "==", "Electronics")
        '.category == "Electronics"'
    """
    # Format value as JSON (handles strings, numbers, booleans)
    value_str = json.dumps(value)

    return f".{field} {operator} {value_str}"


def build_jq_filter(filters: List[Tuple[str, str, str]]) -> str:
    """Build jq filter expression from filter parameters.

    Rules:
    - Same field, multiple values → OR
    - Different fields → AND

    Args:
        filters: List of (field, operator, value) tuples

    Returns:
        jq filter expression wrapped in select()

    Examples:
        >>> build_jq_filter([("category", "==", "Electronics"), ("category", "==", "Clothing")])
        'select((.category == "Electronics" or .category == "Clothing"))'

        >>> build_jq_filter([("category", "==", "Electronics"), ("revenue", ">", "1000")])
        'select(.category == "Electronics" and .revenue > 1000)'
    """
    if not filters:
        return "."  # Pass-through filter

    # Group by field
    by_field: Dict[str, List[Tuple[str, any]]] = {}
    for field, operator, value in filters:
        # Convert value to appropriate type
        typed_value = infer_value_type(value)
        by_field.setdefault(field, []).append((operator, typed_value))

    # Build clauses
    clauses = []
    for field, conditions in by_field.items():
        if len(conditions) == 1:
            # Single condition
            operator, value = conditions[0]
            clauses.append(format_jq_condition(field, operator, value))
        else:
            # Multiple conditions for same field → OR
            parts = [format_jq_condition(field, op, val) for op, val in conditions]
            clauses.append(f"({' or '.join(parts)})")

    # Combine clauses with AND and wrap in select()
    if len(clauses) == 1:
        condition = clauses[0]
    else:
        condition = " and ".join(clauses)

    return f"select({condition})"


def separate_config_and_filters(
    params: Dict[str, str], config_param_names: List[str]
) -> Tuple[Dict[str, str], List[Tuple[str, str, str]]]:
    """Separate query parameters into config and filter groups.

    Args:
        params: All query parameters
        config_param_names: List of parameter names that are config (from introspection)

    Returns:
        Tuple of (config_dict, filter_list)

    Examples:
        >>> separate_config_and_filters(
        ...     {"method": "POST", "gene": "BRAF", "limit": "100"},
        ...     ["method", "limit"]
        ... )
        ({"method": "POST", "limit": "100"}, [("gene", "==", "BRAF")])
    """
    config = {}
    filter_params = {}

    for param_name, value in params.items():
        # Extract base field name (without operator)
        field, _ = parse_operator(param_name)

        if field in config_param_names:
            # This is a config parameter
            config[field] = value
        else:
            # This is a filter parameter
            filter_params[param_name] = value

    filters = parse_filter_params(filter_params)
    return config, filters
