"""Reusable testing framework for plugins.

Provides schema-based validation and smart field matching for plugin tests.
"""

import sys
import json
from typing import Any, Callable, Iterator, Optional
from io import StringIO


def validate_with_schema(record: dict, schema: dict) -> tuple[bool, Optional[str]]:
    """Validate record against JSON schema.

    Args:
        record: Record to validate
        schema: JSON schema definition

    Returns:
        (is_valid, error_message)
    """
    try:
        import jsonschema
        jsonschema.validate(record, schema)
        return True, None
    except ImportError:
        # If jsonschema not available, do basic type checking
        return validate_basic_types(record, schema)
    except jsonschema.ValidationError as e:
        return False, str(e)


def validate_basic_types(record: dict, schema: dict) -> tuple[bool, Optional[str]]:
    """Basic type validation when jsonschema not available.

    Args:
        record: Record to validate
        schema: JSON schema definition

    Returns:
        (is_valid, error_message)
    """
    if schema.get('type') != 'object':
        return True, None

    properties = schema.get('properties', {})
    required = schema.get('required', [])

    # Check required fields
    for field in required:
        if field not in record:
            return False, f"Missing required field: {field}"

    # Check types
    type_map = {
        'string': str,
        'integer': int,
        'number': (int, float),
        'boolean': bool,
        'array': list,
        'object': dict
    }

    for field, prop in properties.items():
        if field not in record:
            continue

        expected_type = prop.get('type')
        if expected_type and expected_type in type_map:
            python_type = type_map[expected_type]
            if not isinstance(record[field], python_type):
                return False, f"Field {field}: expected {expected_type}, got {type(record[field]).__name__}"

    return True, None


def match_field_value(actual: Any, expected: Any, check_type: str = 'exact') -> bool:
    """Match field value based on check type.

    Args:
        actual: Actual value from plugin
        expected: Expected value from test case
        check_type: Type of check ('exact', 'type', 'pattern', 'range')

    Returns:
        True if match
    """
    if check_type == 'exact':
        return actual == expected

    elif check_type == 'type':
        return type(actual) == type(expected)

    elif check_type == 'pattern':
        import re
        return bool(re.match(str(expected), str(actual)))

    elif check_type == 'range':
        if isinstance(expected, dict):
            min_val = expected.get('min')
            max_val = expected.get('max')
            if min_val is not None and actual < min_val:
                return False
            if max_val is not None and actual > max_val:
                return False
            return True
        return True

    return False


def run_plugin_tests(
    run_func: Callable,
    examples_func: Callable,
    schema_func: Optional[Callable] = None,
    verbose: bool = False
) -> bool:
    """Run tests for a plugin using examples and schema validation.

    Args:
        run_func: Plugin's run() function
        examples_func: Plugin's examples() function
        schema_func: Plugin's schema() function (optional)
        verbose: Print detailed output

    Returns:
        True if all tests pass
    """
    test_cases = examples_func()
    schema = schema_func() if schema_func else None

    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        desc = test_case.get('description', f'Test {i}')
        test_input = test_case.get('input', '')
        expected = test_case.get('expected', [])
        config = test_case.get('config', {})
        checks = test_case.get('checks', {})

        # Mock stdin
        old_stdin = sys.stdin
        sys.stdin = StringIO(test_input)

        try:
            # Run plugin
            results = list(run_func(config))

            # Check result count
            if len(results) != len(expected):
                if verbose:
                    print(f"✗ Test {i}: {desc}", file=sys.stderr)
                    print(f"  Expected {len(expected)} records, got {len(results)}", file=sys.stderr)
                failed += 1
                continue

            # Validate each record against schema
            if schema:
                for j, record in enumerate(results):
                    valid, error = validate_with_schema(record, schema)
                    if not valid:
                        if verbose:
                            print(f"✗ Test {i}: {desc}", file=sys.stderr)
                            print(f"  Record {j} schema validation failed: {error}", file=sys.stderr)
                        failed += 1
                        continue

            # Check specific fields
            test_passed = True

            # Exact field checks
            for field in checks.get('exact', []):
                for j, (result, exp) in enumerate(zip(results, expected)):
                    if field not in result:
                        if verbose:
                            print(f"✗ Test {i}: {desc}", file=sys.stderr)
                            print(f"  Record {j} missing field: {field}", file=sys.stderr)
                        test_passed = False
                        break
                    if result[field] != exp.get(field):
                        if verbose:
                            print(f"✗ Test {i}: {desc}", file=sys.stderr)
                            print(f"  Record {j} field {field}: expected {exp.get(field)}, got {result[field]}", file=sys.stderr)
                        test_passed = False
                        break

            # Type checks
            for field in checks.get('types', []):
                for j, (result, exp) in enumerate(zip(results, expected)):
                    if field in result and field in exp:
                        if type(result[field]) != type(exp[field]):
                            if verbose:
                                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                                print(f"  Record {j} field {field}: type mismatch", file=sys.stderr)
                            test_passed = False
                            break

            # Pattern checks
            for field, pattern in checks.get('patterns', {}).items():
                import re
                for j, result in enumerate(results):
                    if field in result:
                        if not re.match(pattern, str(result[field])):
                            if verbose:
                                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                                print(f"  Record {j} field {field}: doesn't match pattern {pattern}", file=sys.stderr)
                            test_passed = False
                            break

            # Range checks
            for field, range_spec in checks.get('ranges', {}).items():
                for j, result in enumerate(results):
                    if field in result:
                        val = result[field]
                        if 'min' in range_spec and val < range_spec['min']:
                            if verbose:
                                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                                print(f"  Record {j} field {field}: {val} < min {range_spec['min']}", file=sys.stderr)
                            test_passed = False
                            break
                        if 'max' in range_spec and val > range_spec['max']:
                            if verbose:
                                print(f"✗ Test {i}: {desc}", file=sys.stderr)
                                print(f"  Record {j} field {field}: {val} > max {range_spec['max']}", file=sys.stderr)
                            test_passed = False
                            break

            if test_passed:
                if verbose:
                    print(f"✓ Test {i}: {desc}", file=sys.stderr)
                passed += 1
            else:
                failed += 1

        except Exception as e:
            if verbose:
                print(f"✗ Test {i}: {desc} - {e}", file=sys.stderr)
            failed += 1

        finally:
            sys.stdin = old_stdin

    # Summary
    if verbose or failed > 0:
        print(f"\n{passed} passed, {failed} failed", file=sys.stderr)

    return failed == 0
