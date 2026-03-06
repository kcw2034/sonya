"""Lightweight input validation against a JSON Schema subset."""

from __future__ import annotations

from typing import Any

_JSON_TYPE_CHECK: dict[str, type | tuple[type, ...]] = {
    'string': str,
    'integer': int,
    'number': (int, float),
    'boolean': bool,
    'array': list,
    'object': dict,
}


def validate_input(
    data: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """Validate *data* against a JSON Schema-like *schema*.

    Returns a list of error messages (empty if valid).
    Checks required fields and basic type conformance.
    """
    errors: list[str] = []
    properties = schema.get('properties', {})

    # Check required fields
    for field_name in schema.get('required', []):
        if field_name not in data:
            errors.append(
                f"Missing required field: '{field_name}'"
            )

    # Check types
    for field_name, value in data.items():
        if field_name not in properties:
            continue
        prop_schema = properties[field_name]
        expected_type = prop_schema.get('type')
        if expected_type is None:
            continue
        nullable = prop_schema.get('nullable', False)
        if nullable and value is None:
            continue
        py_type = _JSON_TYPE_CHECK.get(expected_type)
        if py_type and not isinstance(value, py_type):
            errors.append(
                f"Field '{field_name}' expected type "
                f"'{expected_type}', "
                f"got '{type(value).__name__}'"
            )

    return errors
