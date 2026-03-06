from __future__ import annotations

from pydantic import BaseModel


def _strip_titles(value: object) -> None:
    if isinstance(value, dict):
        value.pop("title", None)
        for item in value.values():
            _strip_titles(item)
        return

    if isinstance(value, list):
        for item in value:
            _strip_titles(item)


def _schema_to_json_schema(schema: type[BaseModel]) -> dict:
    raw = schema.model_json_schema()
    _strip_titles(raw)
    return raw
