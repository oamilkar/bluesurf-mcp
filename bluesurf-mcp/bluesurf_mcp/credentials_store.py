"""Credenciales persistidas para el adaptador MCP.

El username vive en un JSON local (no es secreto). La contraseña vive solo en
el almacén del SO vía ``keyring``. El núcleo ``bluesurf_client`` no persiste nada.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

KEYRING_SERVICE = "bluesurf-mcp"
_CONFIG_FILENAME = "config.json"


def config_dir() -> Path:
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Local"
        return base / "bluesurf-mcp"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "bluesurf-mcp"


def config_path(*, directory: Path | None = None) -> Path:
    return (directory or config_dir()) / _CONFIG_FILENAME


def load(*, directory: Path | None = None) -> tuple[str, str] | None:
    """Devuelve ``(username, password)`` o ``None`` si no hay credenciales."""
    path = config_path(directory=directory)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    username = data.get("username") if isinstance(data, dict) else None
    if not username or not isinstance(username, str):
        return None
    try:
        password = keyring.get_password(KEYRING_SERVICE, username)
    except KeyringError:
        return None
    if not password:
        return None
    return username, password


def save(username: str, password: str, *, directory: Path | None = None) -> None:
    if not username or not password:
        raise ValueError("username y password son obligatorios")
    directory = directory or config_dir()
    path = config_path(directory=directory)

    previous = _read_username(path)
    if previous and previous != username:
        _delete_password(previous)

    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"username": username}, indent=2) + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        path.chmod(0o600)

    keyring.set_password(KEYRING_SERVICE, username, password)


def clear(*, directory: Path | None = None) -> None:
    """Borra config y password. Idempotente si no hay nada guardado."""
    path = config_path(directory=directory)
    username = _read_username(path)
    if username:
        _delete_password(username)
    if path.is_file():
        path.unlink()


def _read_username(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    username = data.get("username") if isinstance(data, dict) else None
    if not username or not isinstance(username, str):
        return None
    return username


def _delete_password(username: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, username)
    except (PasswordDeleteError, KeyringError):
        pass
