from __future__ import annotations

import json

import pytest
from keyring.errors import PasswordDeleteError

from bluesurf_mcp import credentials_store as store


class MemoryKeyring:
    def __init__(self) -> None:
        self._data: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self._data.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._data[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        key = (service, username)
        if key not in self._data:
            raise PasswordDeleteError(username)
        del self._data[key]


@pytest.fixture
def keyring_mem(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyring:
    mem = MemoryKeyring()
    monkeypatch.setattr(store.keyring, "get_password", mem.get_password)
    monkeypatch.setattr(store.keyring, "set_password", mem.set_password)
    monkeypatch.setattr(store.keyring, "delete_password", mem.delete_password)
    return mem


def test_save_load_roundtrip(tmp_path, keyring_mem: MemoryKeyring) -> None:
    store.save("alice", "s3cret", directory=tmp_path)
    assert (tmp_path / "config.json").is_file()
    data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert data == {"username": "alice"}
    assert "s3cret" not in (tmp_path / "config.json").read_text(encoding="utf-8")
    assert store.load(directory=tmp_path) == ("alice", "s3cret")
    assert keyring_mem.get_password(store.KEYRING_SERVICE, "alice") == "s3cret"


def test_load_missing_config(tmp_path, keyring_mem: MemoryKeyring) -> None:
    assert store.load(directory=tmp_path) is None


def test_load_config_without_password(tmp_path, keyring_mem: MemoryKeyring) -> None:
    (tmp_path / "config.json").write_text(
        json.dumps({"username": "alice"}), encoding="utf-8"
    )
    assert store.load(directory=tmp_path) is None


def test_save_replaces_previous_username(
    tmp_path, keyring_mem: MemoryKeyring
) -> None:
    store.save("alice", "old", directory=tmp_path)
    store.save("bob", "new", directory=tmp_path)
    assert store.load(directory=tmp_path) == ("bob", "new")
    assert keyring_mem.get_password(store.KEYRING_SERVICE, "alice") is None
    assert keyring_mem.get_password(store.KEYRING_SERVICE, "bob") == "new"


def test_clear_is_idempotent(tmp_path, keyring_mem: MemoryKeyring) -> None:
    store.save("alice", "s3cret", directory=tmp_path)
    store.clear(directory=tmp_path)
    assert store.load(directory=tmp_path) is None
    assert not (tmp_path / "config.json").exists()
    store.clear(directory=tmp_path)
    assert store.load(directory=tmp_path) is None
