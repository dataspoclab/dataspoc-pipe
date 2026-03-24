"""Modelos de configuração do DataSpoc Pipe."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

DATASPOC_HOME = Path.home() / ".dataspoc-pipe"
PIPELINES_DIR = DATASPOC_HOME / "pipelines"


class SourceConfig(BaseModel):
    tap: str = Field(..., description="Nome do tap Singer (ex: tap-postgres)")
    config: dict | str = Field(..., description="Config do tap (inline dict ou path para arquivo)")
    streams: list[str] | None = Field(None, description="Filtro de streams (None = todas)")


class DestinationConfig(BaseModel):
    bucket: str = Field(..., description="URI do bucket (s3://, gs://, az://, file://)")
    path: str = Field("raw", description="Path base no bucket")
    partition_by: str = Field("_extraction_date", description="Campo de partição")
    compression: str = Field("zstd", description="Compressão: zstd, snappy, gzip, none")


class IncrementalConfig(BaseModel):
    enabled: bool = Field(False, description="Habilitar extração incremental")


class ScheduleConfig(BaseModel):
    cron: str | None = Field(None, description="Expressão cron (ex: '0 * * * *')")


class PipelineConfig(BaseModel):
    name: str = Field(..., description="Pipeline name")
    source: SourceConfig
    destination: DestinationConfig
    incremental: IncrementalConfig = Field(default_factory=IncrementalConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    # Transform is convention-based: if ~/.dataspoc-pipe/transforms/<name>.py exists, it runs.
    # No config needed.


def get_pipeline_path(name: str) -> Path:
    return PIPELINES_DIR / f"{name}.yaml"


def load_pipeline(name: str) -> PipelineConfig:
    """Carrega e valida um pipeline pelo nome."""
    import yaml

    path = get_pipeline_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Pipeline '{name}' não encontrado em {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    data["name"] = name
    return PipelineConfig(**data)


def save_pipeline(config: PipelineConfig) -> Path:
    """Salva a configuração de um pipeline em YAML."""
    import yaml

    path = get_pipeline_path(config.name)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(exclude={"name"}, exclude_none=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return path


def list_pipelines() -> list[str]:
    """Lista nomes dos pipelines configurados."""
    if not PIPELINES_DIR.exists():
        return []
    return [p.stem for p in PIPELINES_DIR.glob("*.yaml")]
