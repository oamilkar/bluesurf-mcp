from __future__ import annotations

import pytest

from bluesurf_client.auth.base import AuthError
from bluesurf_mcp import cli


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main(["--help"])
    out = capsys.readouterr().out
    assert "login" in out
    assert "logout" in out


def test_unknown_command_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["nope"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "comando desconocido" in err


def test_login_saves_after_successful_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, str] = {}

    async def ok(username: str, password: str, base_url: str) -> None:
        return None

    monkeypatch.setattr(cli, "_verify_credentials", ok)
    monkeypatch.setattr(
        cli, "save", lambda u, p: saved.update(username=u, password=p)
    )
    monkeypatch.setattr("builtins.input", lambda _: "alice")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "pw")
    assert cli._cmd_login() == 0
    assert saved == {"username": "alice", "password": "pw"}


def test_login_does_not_save_when_surf_rejects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[tuple[str, str]] = []

    async def bad(username: str, password: str, base_url: str) -> None:
        raise AuthError("rechazado")

    monkeypatch.setattr(cli, "_verify_credentials", bad)
    monkeypatch.setattr(cli, "save", lambda u, p: saved.append((u, p)))
    monkeypatch.setattr("builtins.input", lambda _: "alice")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "pw")
    assert cli._cmd_login() == 1
    assert saved == []


def test_logout_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"n": 0}

    def fake_clear() -> None:
        called["n"] += 1

    monkeypatch.setattr(cli, "clear", fake_clear)
    assert cli._cmd_logout() == 0
    assert called["n"] == 1
