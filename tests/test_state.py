"""Testes de state/bookmarks incrementais."""

from dataspoc_pipe.state import get_state_uri, load_state, save_state
from dataspoc_pipe.storage import exists


def test_state_uri():
    uri = get_state_uri("s3://my-bucket", "my-pipeline")
    assert uri == "s3://my-bucket/.dataspoc/state/my-pipeline/state.json"


def test_load_state_nonexistent(tmp_path):
    state = load_state(f"file://{tmp_path}", "no-pipeline")
    assert state is None


def test_save_and_load_state(tmp_path):
    bucket = f"file://{tmp_path}"
    state = {"bookmarks": {"users": {"id": 42}}}

    save_state(bucket, "test-pipe", state)
    loaded = load_state(bucket, "test-pipe")

    assert loaded == state
    assert loaded["bookmarks"]["users"]["id"] == 42


def test_state_is_persisted_in_bucket(tmp_path):
    bucket = f"file://{tmp_path}"
    save_state(bucket, "test", {"bookmarks": {}})

    uri = get_state_uri(bucket, "test")
    assert exists(uri)


def test_save_state_overwrites(tmp_path):
    bucket = f"file://{tmp_path}"

    save_state(bucket, "test", {"bookmarks": {"users": {"id": 1}}})
    save_state(bucket, "test", {"bookmarks": {"users": {"id": 99}}})

    loaded = load_state(bucket, "test")
    assert loaded["bookmarks"]["users"]["id"] == 99
