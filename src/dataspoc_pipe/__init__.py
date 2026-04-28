"""DataSpoc Pipe — Motor de ingestão de dados."""

__version__ = "0.2.0"

__all__ = ["PipeClient", "__version__"]


def __getattr__(name: str):
    if name == "PipeClient":
        from dataspoc_pipe.sdk import PipeClient

        return PipeClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
