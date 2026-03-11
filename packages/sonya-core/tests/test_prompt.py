"""Tests for Prompt and Example data types."""

from sonya.core.models.prompt import Example


def test_example_creation():
    ex = Example(user='Hello', assistant='Hi there')
    assert ex.user == 'Hello'
    assert ex.assistant == 'Hi there'


def test_example_is_frozen():
    ex = Example(user='a', assistant='b')
    try:
        ex.user = 'c'
        assert False, 'Should have raised'
    except AttributeError:
        pass


def test_example_equality():
    a = Example(user='x', assistant='y')
    b = Example(user='x', assistant='y')
    assert a == b
