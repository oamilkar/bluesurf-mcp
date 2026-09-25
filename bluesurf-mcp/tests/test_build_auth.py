from __future__ import annotations

import pytest

from bluesurf_client.auth.cookie import CookieAuth
from bluesurf_client.auth.credentials import CredentialsAuth
from bluesurf_mcp.server import _build_auth


def test_cookie_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLUESURF_COOKIE", "cookie-value")
    monkeypatch.setenv("BLUESURF_USERNAME", "alice")
    monkeypatch.setenv("BLUESURF_PASSWORD", "from-env")
    monkeypatch.setattr(
        "bluesurf_mcp.server.load_stored_credentials",
        lambda: ("alice", "from-store"),
    )
    auth = _build_auth()
    assert isinstance(auth, CookieAuth)


def test_env_credentials_beat_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLUESURF_COOKIE", raising=False)
    monkeypatch.delenv("SURF_COOKIE", raising=False)
    monkeypatch.setenv("BLUESURF_USERNAME", "alice")
    monkeypatch.setenv("BLUESURF_PASSWORD", "from-env")
    monkeypatch.setattr(
        "bluesurf_mcp.server.load_stored_credentials",
        lambda: ("alice", "from-store"),
    )
    auth = _build_auth()
    assert isinstance(auth, CredentialsAuth)
    assert auth._username == "alice"
    assert auth._password == "from-env"


def test_falls_back_to_store(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "BLUESURF_COOKIE",
        "SURF_COOKIE",
        "BLUESURF_USERNAME",
        "SURF_USERNAME",
        "BLUESURF_PASSWORD",
        "SURF_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "bluesurf_mcp.server.load_stored_credentials",
        lambda: ("bob", "stored-secret"),
    )
    auth = _build_auth()
    assert isinstance(auth, CredentialsAuth)
    assert auth._username == "bob"
    assert auth._password == "stored-secret"


def test_error_mentions_login_when_nothing_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "BLUESURF_COOKIE",
        "SURF_COOKIE",
        "BLUESURF_USERNAME",
        "SURF_USERNAME",
        "BLUESURF_PASSWORD",
        "SURF_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "bluesurf_mcp.server.load_stored_credentials",
        lambda: None,
    )
    with pytest.raises(RuntimeError, match="bluesurf-mcp login"):
        _build_auth()
