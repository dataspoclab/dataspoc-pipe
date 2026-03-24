#!/usr/bin/env python3
"""Mock tap Singer para testes — emite dados simples."""

import json
import sys

# SCHEMA
schema = {
    "type": "SCHEMA",
    "stream": "users",
    "schema": {
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "email": {"type": ["string", "null"]},
            "active": {"type": "boolean"},
        }
    },
    "key_properties": ["id"],
}
print(json.dumps(schema))

# RECORDS
users = [
    {"id": 1, "name": "Ana", "email": "ana@test.com", "active": True},
    {"id": 2, "name": "Bruno", "email": None, "active": True},
    {"id": 3, "name": "Carlos", "email": "carlos@test.com", "active": False},
]

for user in users:
    record = {"type": "RECORD", "stream": "users", "record": user}
    print(json.dumps(record))

# STATE
state = {"type": "STATE", "value": {"bookmarks": {"users": {"id": 3}}}}
print(json.dumps(state))
