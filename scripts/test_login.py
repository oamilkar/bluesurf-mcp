"""Prueba manual de login contra BlueSurf.

Lee credenciales del .env de la raíz del proyecto y verifica que
``CredentialsAuth`` obtiene la cookie de sesión. No imprime la contraseña y solo
muestra un fragmento enmascarado de la cookie.

Uso:
    python scripts/test_login.py

Variables (en .env de la raíz o en el entorno):
    BLUESURF_USERNAME / BLUESURF_PASSWORD / BLUESURF_BASE_URL (opcional);
    se aceptan SURF_* como fallback.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# bluesurf_client se importa desde el .venv (instalado en modo editable).
from bluesurf_client import BlueSurfClient, CredentialsAuth
from bluesurf_client.auth.base import AuthError
from bluesurf_client.constants import DEFAULT_BASE_URL, IDENTITY_COOKIE

# La consola de Windows suele ser cp1252; forzamos UTF-8 para acentos/emojis.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure:
        reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]


def _env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _mask(value: str) -> str:
    return f"{value[:12]}…{value[-6:]} ({len(value)} chars)" if value else "<vacía>"


async def main() -> int:
    load_dotenv(ROOT / ".env")

    username = _env("BLUESURF_USERNAME", "SURF_USERNAME")
    password = _env("BLUESURF_PASSWORD", "SURF_PASSWORD")
    base_url = _env("BLUESURF_BASE_URL", "SURF_BASE_URL") or DEFAULT_BASE_URL

    if not username or not password:
        print(
            "ERROR: define BLUESURF_USERNAME y BLUESURF_PASSWORD en .env "
            "(o SURF_USERNAME / SURF_PASSWORD)",
            file=sys.stderr,
        )
        return 2

    print(f"Base URL : {base_url}")
    print(f"Usuario  : {username}")
    print("Iniciando sesión…")

    auth = CredentialsAuth(username, password)
    async with BlueSurfClient(base_url=base_url) as client:
        try:
            await client.login(auth)
        except AuthError as exc:
            print(f"❌ Login falló: {exc}", file=sys.stderr)
            return 1

        cookie = client.session_cookie(IDENTITY_COOKIE)

    print("✅ Login exitoso.")
    print(f"   Cookie '{IDENTITY_COOKIE}': {_mask(cookie or '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
