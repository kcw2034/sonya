"""Generate JSON Schema from function type hints (stdlib only)."""

import dataclasses
import inspect
import types
from typing import Any, Union, get_type_hints

_TYPE_MAP: dict[type, str] = {
    str: 'string',
    int: 'integer',
    float: 'number',
    bool: 'boolean',
}


def _is_union(annotation: Any) -> bool:
    """Check if annotation is a Union type (typing.Union or T | None)."""
    origin = getattr(annotation, '__origin__', None)
    if origin is Union:
        return True
    if isinstance(annotation, types.UnionType):
        return True
    return False


def _get_union_args(annotation: Any) -> tuple[Any, ...]:
    """Get the type arguments from a Union."""
    return annotation.__args__


def _resolve_type(annotation: Any) -> dict[str, Any]:
    """Convert a single Python type annotation to a JSON Schema fragment.

    Supports primitives, list[T], dict[str, T], Optional (T | None),
    and dataclasses (expanded as nested object schemas).
    """
    # Union / T | None (both typing.Union and types.UnionType)
    if _is_union(annotation):
        args = [
            a for a in _get_union_args(annotation)
            if a is not type(None)
        ]
        if len(args) == 1:
            schema = _resolve_type(args[0])
            schema['nullable'] = True
            return schema
        return {'anyOf': [_resolve_type(a) for a in args]}

    origin = getattr(annotation, '__origin__', None)

    # list[T]
    if origin is list:
        type_args = getattr(annotation, '__args__', None)
        item_type = type_args[0] if type_args else Any
        return {'type': 'array', 'items': _resolve_type(item_type)}

    # dict[str, T]
    if origin is dict:
        type_args = getattr(annotation, '__args__', None)
        val_type = type_args[1] if type_args else Any
        return {
            'type': 'object',
            'additionalProperties': _resolve_type(val_type),
        }

    # Dataclass -> nested object
    if dataclasses.is_dataclass(annotation) and isinstance(
        annotation, type
    ):
        return _dataclass_to_schema(annotation)

    # Primitives
    if annotation in _TYPE_MAP:
        return {'type': _TYPE_MAP[annotation]}

    # Fallback
    return {'type': 'string'}


def _dataclass_to_schema(cls: type) -> dict[str, Any]:
    """Convert a dataclass to a JSON Schema object."""
    hints = get_type_hints(cls)
    fields = dataclasses.fields(cls)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for f in fields:
        properties[f.name] = _resolve_type(hints[f.name])
        if (
            f.default is dataclasses.MISSING
            and f.default_factory is dataclasses.MISSING
        ):
            required.append(f.name)

    schema: dict[str, Any] = {
        'type': 'object',
        'properties': properties,
    }
    if required:
        schema['required'] = required
    return schema


def _safe_get_hints(fn: Any) -> dict[str, Any]:
    """Get type hints without eval, falling back safely on error.

    Resolution order:
    1. ``typing.get_type_hints(fn)`` — standard resolution.
    2. Retry with the function's ``__globals__`` passed explicitly,
       which helps when forward-reference strings live outside the
       default lookup namespace.
    3. Final fallback: return raw ``__annotations__``, mapping any
       unresolvable string annotations to ``str`` rather than calling
       ``eval`` (which would be a security risk).
    """
    try:
        return get_type_hints(fn)
    except (NameError, AttributeError, TypeError):
        pass

    globalns = getattr(fn, '__globals__', {})
    try:
        return get_type_hints(fn, globalns=globalns)
    except (NameError, AttributeError, TypeError):
        pass

    # Safe fallback: do NOT eval string annotations.
    raw = getattr(fn, '__annotations__', {})
    resolved: dict[str, Any] = {}
    for name, hint in raw.items():
        resolved[name] = hint if not isinstance(hint, str) else str
    return resolved


def _is_tool_context(annotation: Any) -> bool:
    """Return True if *annotation* is the ToolContext class.

    Uses a string-based check to avoid a circular import between
    schema_parser and tool_context.
    """
    cls = annotation if isinstance(annotation, type) else None
    if cls is None:
        return False
    return (
        cls.__name__ == 'ToolContext'
        and cls.__module__.startswith('sonya.core')
    )


def function_to_schema(fn: Any) -> dict[str, Any]:
    """Generate a JSON Schema ``parameters`` object from *fn*'s type hints.

    Skips ``self``, ``cls``, ``return``, and any parameter typed as
    :class:`~sonya.core.utils.tool_context.ToolContext` (context
    parameters are injected at runtime and must not be exposed to the LLM).
    Parameters without a default value are marked as required.
    """
    sig = inspect.signature(fn)
    hints = _safe_get_hints(fn)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ('self', 'cls'):
            continue
        annotation = hints.get(name, str)
        if _is_tool_context(annotation):
            continue  # injected at runtime; never exposed to LLM
        properties[name] = _resolve_type(annotation)

        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema: dict[str, Any] = {
        'type': 'object',
        'properties': properties,
    }
    if required:
        schema['required'] = required
    return schema
