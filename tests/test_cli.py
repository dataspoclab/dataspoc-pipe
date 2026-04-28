"""Testes do CLI do DataSpoc Pipe."""

from typer.testing import CliRunner

from dataspoc_pipe.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "dataspoc-pipe" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dataspoc-pipe" in result.output.lower() or "Motor" in result.output


def test_init_stub():
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0


def test_add_requires_argument():
    result = runner.invoke(app, ["add"])
    assert result.exit_code != 0


def test_run_requires_valid_pipeline():
    result = runner.invoke(app, ["run", "nonexistent-pipeline"])
    assert result.exit_code != 0


def test_status_stub():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_validate_stub():
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0


def test_manifest_empty(tmp_path):
    result = runner.invoke(app, ["manifest", f"file://{tmp_path}"])
    assert result.exit_code == 0


def test_schedule_install_help():
    result = runner.invoke(app, ["schedule", "install", "--help"])
    assert result.exit_code == 0
    assert "crontab" in result.output.lower() or "agendamento" in result.output.lower()


def test_schedule_remove_help():
    result = runner.invoke(app, ["schedule", "remove", "--help"])
    assert result.exit_code == 0
