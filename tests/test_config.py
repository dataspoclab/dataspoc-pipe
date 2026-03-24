"""Testes de configuração e comandos init/add."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from dataspoc_pipe.cli import app
from dataspoc_pipe.config import (
    DestinationConfig,
    PipelineConfig,
    SourceConfig,
    load_pipeline,
    save_pipeline,
)

runner = CliRunner()


@pytest.fixture
def tmp_home(tmp_path):
    """Redireciona DATASPOC_HOME para diretório temporário."""
    home = tmp_path / ".dataspoc-pipe"
    with patch("dataspoc_pipe.config.DATASPOC_HOME", home), \
         patch("dataspoc_pipe.config.PIPELINES_DIR", home / "pipelines"), \
         patch("dataspoc_pipe.cli.DATASPOC_HOME", home), \
         patch("dataspoc_pipe.cli.PIPELINES_DIR", home / "pipelines"):
        yield home


def test_init_creates_structure(tmp_home):
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert tmp_home.exists()
    assert (tmp_home / "pipelines").exists()
    assert (tmp_home / "config.yaml").exists()


def test_init_idempotent(tmp_home):
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert "already exists" in result.output


def test_pipeline_config_validation():
    config = PipelineConfig(
        name="test",
        source=SourceConfig(tap="tap-csv", config={"path": "/data"}),
        destination=DestinationConfig(bucket="file:///tmp/lake"),
    )
    assert config.name == "test"
    assert config.destination.compression == "zstd"
    assert config.incremental.enabled is False


def test_pipeline_config_requires_source():
    with pytest.raises(ValidationError):
        PipelineConfig(
            name="test",
            destination=DestinationConfig(bucket="file:///tmp"),
        )


def test_save_and_load_pipeline(tmp_home):
    config = PipelineConfig(
        name="my-pipeline",
        source=SourceConfig(tap="tap-csv", config={"path": "/data"}),
        destination=DestinationConfig(bucket="file:///tmp/lake", path="raw"),
    )
    save_pipeline(config)

    loaded = load_pipeline("my-pipeline")
    assert loaded.name == "my-pipeline"
    assert loaded.source.tap == "tap-csv"
    assert loaded.destination.bucket == "file:///tmp/lake"


def test_load_nonexistent_pipeline(tmp_home):
    with pytest.raises(FileNotFoundError):
        load_pipeline("inexistente")


def test_add_wizard(tmp_home):
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        ["add", "test-pipe"],
        input="tap-csv\n{}\nfile:///tmp/lake\nraw\nzstd\nn\n\n",
    )
    assert result.exit_code == 0
    assert "Pipeline saved" in result.output
    assert (tmp_home / "pipelines" / "test-pipe.yaml").exists()


def test_add_duplicate_pipeline(tmp_home):
    runner.invoke(app, ["init"])
    runner.invoke(app, ["add", "dup"], input="tap-csv\n{}\nfile:///tmp\nraw\nzstd\nn\n\n")
    result = runner.invoke(app, ["add", "dup"], input="tap-csv\n{}\nfile:///tmp\nraw\nzstd\nn\n\n")
    assert result.exit_code == 1
