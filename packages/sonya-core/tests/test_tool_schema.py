"""Tests for tool._schema — JSON Schema generation from type hints."""

from __future__ import annotations

from dataclasses import dataclass

from sonya.core.parsers.schema_parser import function_to_schema


@dataclass
class Point:
    x: float
    y: float


def test_simple_primitives() -> None:
    def fn(a: int, b: str) -> str:
        ...

    schema = function_to_schema(fn)
    assert schema['type'] == 'object'
    assert schema['properties']['a'] == {'type': 'integer'}
    assert schema['properties']['b'] == {'type': 'string'}
    assert set(schema['required']) == {'a', 'b'}


def test_optional_parameter() -> None:
    def fn(a: int, b: str = 'hello') -> str:
        ...

    schema = function_to_schema(fn)
    assert schema['required'] == ['a']


def test_nullable_type() -> None:
    def fn(a: int | None) -> None:
        ...

    schema = function_to_schema(fn)
    assert schema['properties']['a']['type'] == 'integer'
    assert schema['properties']['a']['nullable'] is True


def test_list_type() -> None:
    def fn(items: list[str]) -> None:
        ...

    schema = function_to_schema(fn)
    assert schema['properties']['items']['type'] == 'array'
    assert schema['properties']['items']['items'] == {'type': 'string'}


def test_dict_type() -> None:
    def fn(data: dict[str, int]) -> None:
        ...

    schema = function_to_schema(fn)
    prop = schema['properties']['data']
    assert prop['type'] == 'object'
    assert prop['additionalProperties'] == {'type': 'integer'}


def test_dataclass_type() -> None:
    def fn(point: Point) -> None:
        ...

    schema = function_to_schema(fn)
    prop = schema['properties']['point']
    assert prop['type'] == 'object'
    assert prop['properties']['x'] == {'type': 'number'}
    assert prop['properties']['y'] == {'type': 'number'}
    assert set(prop['required']) == {'x', 'y'}


def test_no_params() -> None:
    def fn() -> None:
        ...

    schema = function_to_schema(fn)
    assert schema['type'] == 'object'
    assert schema['properties'] == {}
    assert 'required' not in schema


def test_skips_self_and_cls() -> None:
    class Foo:
        def method(self, a: int) -> None:
            ...

        @classmethod
        def clsmethod(cls, b: str) -> None:
            ...

    schema = function_to_schema(Foo.method)
    assert 'self' not in schema['properties']
    assert 'a' in schema['properties']

    schema = function_to_schema(Foo.clsmethod)
    assert 'cls' not in schema['properties']
    assert 'b' in schema['properties']


def test_bool_and_float() -> None:
    def fn(flag: bool, value: float) -> None:
        ...

    schema = function_to_schema(fn)
    assert schema['properties']['flag'] == {'type': 'boolean'}
    assert schema['properties']['value'] == {'type': 'number'}


def test_safe_get_hints_no_eval_on_unresolvable() -> None:
    """Unresolvable string annotations must fall back to str, not eval."""
    from sonya.core.parsers.schema_parser import _safe_get_hints

    # Simulate a function whose annotation references a name that
    # does not exist in any reachable namespace.
    def fn(x: int) -> None:  # type: ignore[misc]
        ...

    # Patch a raw string annotation that cannot be resolved.
    fn.__annotations__ = {'x': 'NonExistentType12345'}
    # __globals__ should NOT contain NonExistentType12345
    assert 'NonExistentType12345' not in fn.__globals__  # type: ignore[attr-defined]

    hints = _safe_get_hints(fn)
    # Must not raise; must map the unresolvable hint to str safely.
    assert hints['x'] is str


def test_safe_get_hints_resolvable_forward_ref() -> None:
    """A string annotation that IS resolvable should be resolved correctly."""
    from sonya.core.parsers.schema_parser import _safe_get_hints

    def fn(a: int) -> None:
        ...

    # 'int' is always resolvable via builtins
    fn.__annotations__ = {'a': 'int'}
    hints = _safe_get_hints(fn)
    assert hints['a'] is int


def test_schema_parser_contains_no_eval_call() -> None:
    """Ensure the schema_parser source no longer contains an eval() call."""
    import importlib.util
    import inspect

    spec = importlib.util.find_spec('sonya.core.parsers.schema_parser')
    assert spec is not None
    assert spec.origin is not None
    source = open(spec.origin).read()
    # The word 'eval(' must not appear anywhere in the module.
    assert 'eval(' not in source, (
        'schema_parser.py still contains eval() — security risk'
    )
