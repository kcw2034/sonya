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
