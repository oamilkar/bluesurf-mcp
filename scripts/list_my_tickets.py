"""Lista los tickets asignados al usuario, para verificar el flujo end-to-end.

Uso:
    python scripts/list_my_tickets.py [SMALLCODE] [--all]

- SMALLCODE: proyecto a consultar (p. ej. PROJ). Si se omite, usa el primer
  proyecto del usuario.
- --all: incluye también los tickets en estados finales (cerrados).

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
from bluesurf_client.constants import DEFAULT_BASE_URL

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

    args = [a for a in sys.argv[1:]]
    include_closed = "--all" in args
    positional = [a for a in args if not a.startswith("--")]
    project_arg = positional[0] if positional else None

    async with BlueSurfClient(base_url=base_url) as client:
        try:
            await client.login(CredentialsAuth(username, password))
        except AuthError as exc:
            print(f"❌ Login falló: {exc}", file=sys.stderr)
            return 1

        me = await client.current_user()
        print(f"Usuario: {me.full_name} (@{me.blue_tag}) — id {me.id}")

        proyectos = await client.mis_proyectos()
        print(f"\nProyectos ({len(proyectos)}):")
        for p in proyectos:
            print(f"  - {p.get('smallCode'):<8} {p.get('name')}  [{p.get('code')}]")

        project = project_arg or (proyectos[0].get("smallCode") if proyectos else None)
        if not project:
            print("No hay proyecto para consultar.", file=sys.stderr)
            return 1

        estado = "todos" if include_closed else "abiertos"
        print(f"\nTickets asignados a mí en '{project}' ({estado}):")
        tickets = await client.mis_tickets(project, include_closed=include_closed)
        if not tickets:
            print("  (ninguno)")
        for t in tickets:
            print(f"  [{t.code}] {t.status_name} — {t.name}")
        print(f"\nTotal: {len(tickets)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
