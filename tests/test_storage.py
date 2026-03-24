"""Testes do storage layer."""

import os

import pytest

from dataspoc_pipe.storage import (
    atomic_write,
    delete,
    exists,
    read_bytes,
    write_bytes,
)


def test_write_and_read(tmp_path):
    uri = f"file://{tmp_path}/test.txt"
    write_bytes(uri, b"hello world")
    assert read_bytes(uri) == b"hello world"


def test_exists(tmp_path):
    uri = f"file://{tmp_path}/test.txt"
    assert not exists(uri)
    write_bytes(uri, b"data")
    assert exists(uri)


def test_atomic_write(tmp_path):
    uri = f"file://{tmp_path}/atomic.txt"
    atomic_write(uri, b"atomic data")
    assert read_bytes(uri) == b"atomic data"
    # Sem arquivo temporário remanescente
    files = os.listdir(tmp_path)
    assert len(files) == 1
    assert files[0] == "atomic.txt"


def test_delete(tmp_path):
    uri = f"file://{tmp_path}/to_delete.txt"
    write_bytes(uri, b"bye")
    assert exists(uri)
    delete(uri)
    assert not exists(uri)


def test_write_creates_dirs(tmp_path):
    uri = f"file://{tmp_path}/deep/nested/dir/file.txt"
    write_bytes(uri, b"deep")
    assert read_bytes(uri) == b"deep"


def test_atomic_write_creates_dirs(tmp_path):
    uri = f"file://{tmp_path}/deep/nested/atomic.txt"
    atomic_write(uri, b"deep atomic")
    assert read_bytes(uri) == b"deep atomic"
