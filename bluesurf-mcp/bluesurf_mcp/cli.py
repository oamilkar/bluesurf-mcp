"""Punto de entrada del binario ``bluesurf-mcp``.

Sin argumentos arranca el servidor MCP por stdio. ``login`` / ``logout``
gestionan credenciales en el almacén del sistema.
"""

from __future__ import annotations

import asyncio
import getpass
import sys

from bluesurf_client import BlueSurfClient, CredentialsAuth
from bluesurf_client.auth.base import AuthError
from bluesurf_client.constants import DEFAULT_BASE_URL

from bluesurf_mcp.credentials_store import clear, save
from bluesurf_mcp.server import _env, main as run_mcp

_HELP = """uso: bluesurf-mcp [login|logout]

Sin argumentos arranca el servidor MCP por stdio.

  login   Pide usuario y contraseña, valida contra BlueSurf y los guarda
          en el almacén del sistema (la contraseña no queda en mcp.json).
  logout  Borra las credenciales guardadas.
"""


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        run_mcp()
        return
    command = args[0]
    if command in ("-h", "--help", "help"):
        print(_HELP, end="")
        return
    if command == "login":
        raise SystemExit(_cmd_login())
    if command == "logout":
        raise SystemExit(_cmd_logout())
    print(f"comando desconocido: {command}", file=sys.stderr)
    print(_HELP, end="", file=sys.stderr)
    raise SystemExit(2)


def _cmd_login() -> int:
    username = input("Usuario de BlueSurf: ").strip()
    if not username:
        print("ERROR: el usuario no puede estar vacío.", file=sys.stderr)
        return 2
    password = getpass.getpass("Contraseña: ")
    if not password:
        print("ERROR: la contraseña no puede estar vacía.", file=sys.stderr)
        return 2

    base_url = _env("BLUESURF_BASE_URL", "SURF_BASE_URL") or DEFAULT_BASE_URL
    print("Validando contra BlueSurf…")
    try:
        asyncio.run(_verify_credentials(username, password, base_url))
    except AuthError as exc:
        print(f"ERROR: login rechazado: {exc}", file=sys.stderr)
        return 1

    save(username, password)
    print("Credenciales guardadas en el almacén del sistema.")
    print("En mcp.json no hace falta poner usuario ni contraseña.")
    return 0


def _cmd_logout() -> int:
    clear()
    print("Credenciales borradas (si había alguna).")
    return 0


async def _verify_credentials(username: str, password: str, base_url: str) -> None:
    auth = CredentialsAuth(username, password)
    async with BlueSurfClient(base_url=base_url) as client:
        await client.login(auth)


if __name__ == "__main__":
    main()
