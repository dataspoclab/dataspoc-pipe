"""Parser do protocolo Singer — lê stdout de taps."""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class SingerMessage:
    type: str
    stream: str | None = None
    record: dict | None = None
    schema: dict | None = None
    key_properties: list[str] | None = None
    value: dict | None = None  # STATE value


def parse_message(line: str) -> SingerMessage:
    """Parseia uma linha JSON do stdout do Singer."""
    data = json.loads(line)
    msg_type = data["type"]

    if msg_type == "RECORD":
        return SingerMessage(type="RECORD", stream=data["stream"], record=data["record"])
    elif msg_type == "SCHEMA":
        return SingerMessage(
            type="SCHEMA",
            stream=data["stream"],
            schema=data["schema"],
            key_properties=data.get("key_properties"),
        )
    elif msg_type == "STATE":
        return SingerMessage(type="STATE", value=data["value"])
    else:
        return SingerMessage(type=msg_type)


def json_schema_to_pyarrow(schema: dict) -> "pa.Schema":
    """Converte JSON Schema (Singer) para PyArrow Schema."""
    import pyarrow as pa

    fields = []
    properties = schema.get("properties", {})

    for name, prop in properties.items():
        pa_type = _json_type_to_arrow(prop)
        nullable = _is_nullable(prop)
        fields.append(pa.field(name, pa_type, nullable=nullable))

    return pa.schema(fields)


def _is_nullable(prop: dict) -> bool:
    """Verifica se o tipo JSON Schema é nullable."""
    type_val = prop.get("type", "string")
    if isinstance(type_val, list):
        return "null" in type_val
    return False


def _json_type_to_arrow(prop: dict) -> "pa.DataType":
    """Converte tipo JSON Schema para tipo PyArrow."""
    import pyarrow as pa

    type_val = prop.get("type", "string")

    # Lidar com arrays de tipo (ex: ["string", "null"])
    if isinstance(type_val, list):
        types = [t for t in type_val if t != "null"]
        type_val = types[0] if types else "string"

    fmt = prop.get("format", "")

    if type_val == "integer":
        return pa.int64()
    elif type_val == "number":
        return pa.float64()
    elif type_val == "boolean":
        return pa.bool_()
    elif type_val == "string":
        if fmt == "date-time":
            return pa.timestamp("s")
        elif fmt == "date":
            return pa.date32()
        return pa.string()
    elif type_val == "array":
        items = prop.get("items", {"type": "string"})
        return pa.list_(_json_type_to_arrow(items))
    elif type_val == "object":
        return pa.string()  # Serializar objetos como JSON string
    else:
        return pa.string()
