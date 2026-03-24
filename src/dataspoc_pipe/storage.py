"""Abstração de storage — fsspec multi-cloud."""

from __future__ import annotations

import uuid

import fsspec


def get_fs(uri: str) -> tuple[fsspec.AbstractFileSystem, str]:
    """Resolve filesystem e path a partir de URI.

    Retorna (filesystem, path) onde path é o caminho sem o scheme.
    """
    if uri.startswith("file://"):
        path = uri[7:]
        fs = fsspec.filesystem("file")
        return fs, path

    # fsspec resolve automaticamente s3://, gs://, az://
    fs, _, paths = fsspec.get_fs_token_paths(uri)
    path = paths[0] if paths else ""
    return fs, path


def write_bytes(uri: str, data: bytes) -> None:
    """Escreve bytes em um URI."""
    fs, path = get_fs(uri)
    fs.mkdirs(fs._parent(path), exist_ok=True)
    with fs.open(path, "wb") as f:
        f.write(data)


def read_bytes(uri: str) -> bytes:
    """Lê bytes de um URI."""
    fs, path = get_fs(uri)
    with fs.open(path, "rb") as f:
        return f.read()


def exists(uri: str) -> bool:
    """Verifica se um URI existe."""
    fs, path = get_fs(uri)
    return fs.exists(path)


def list_files(uri: str) -> list[str]:
    """Lista arquivos em um URI prefix."""
    fs, path = get_fs(uri)
    try:
        return fs.ls(path, detail=False)
    except FileNotFoundError:
        return []


def atomic_write(uri: str, data: bytes) -> None:
    """Escrita atômica: escreve em temp, depois move para destino."""
    fs, path = get_fs(uri)
    parent = fs._parent(path)
    fs.mkdirs(parent, exist_ok=True)

    tmp_path = f"{parent}/_tmp_{uuid.uuid4().hex}"
    try:
        with fs.open(tmp_path, "wb") as f:
            f.write(data)
        # Para filesystems locais, rename é atômico.
        # Para cloud, copy+delete é o melhor que temos.
        if fs.protocol == "file":
            import os
            os.rename(tmp_path, path)
        else:
            fs.copy(tmp_path, path)
            fs.rm(tmp_path)
    except Exception:
        # Limpa temp se algo falhar
        try:
            fs.rm(tmp_path)
        except Exception:
            pass
        raise


def delete(uri: str) -> None:
    """Deleta um arquivo."""
    fs, path = get_fs(uri)
    fs.rm(path)
