"""Gestão de state/bookmarks para extração incremental."""

from __future__ import annotations

import json

from dataspoc_pipe.storage import atomic_write, exists, read_bytes


def get_state_uri(bucket: str, pipeline_name: str) -> str:
    """Retorna URI do state file no bucket."""
    return f"{bucket.rstrip('/')}/.dataspoc/state/{pipeline_name}/state.json"


def load_state(bucket: str, pipeline_name: str) -> dict | None:
    """Carrega state do bucket. Retorna None se não existe."""
    uri = get_state_uri(bucket, pipeline_name)
    if not exists(uri):
        return None
    data = read_bytes(uri)
    return json.loads(data)


def save_state(bucket: str, pipeline_name: str, state: dict) -> None:
    """Salva state atomicamente no bucket."""
    uri = get_state_uri(bucket, pipeline_name)
    data = json.dumps(state, indent=2).encode()
    atomic_write(uri, data)
