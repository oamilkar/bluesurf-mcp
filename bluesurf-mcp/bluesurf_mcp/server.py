"""Servidor MCP local para leer tickets de BlueSurf.

Adaptador delgado sobre ``bluesurf_client``: expone únicamente tools de solo lectura.
No implementa ninguna operación de escritura por diseño.

Config: cookie o credenciales por entorno, o las guardadas con
``bluesurf-mcp login`` (contraseña en el almacén del SO). Las claves
canónicas son ``BLUESURF_*``; se aceptan ``SURF_*`` como fallback.

La cookie de sesión de BlueSurf vive en memoria mientras corre el server.
"""

from __future__ import annotations

import os
from dataclasses import asdict

from mcp.server import MCPServer

from bluesurf_client import BlueSurfClient, CookieAuth, CredentialsAuth
from bluesurf_client.auth.base import AuthProvider
from bluesurf_client.constants import DEFAULT_BASE_URL
from bluesurf_mcp.credentials_store import load as load_stored_credentials

mcp = MCPServer("bluesurf")


def _env(*names: str) -> str | None:
    """Primera variable de entorno no vacía entre ``names``."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def _build_auth() -> AuthProvider:
    """Construye el AuthProvider a partir del entorno (cookie o credenciales)."""
    cookie = _env("BLUESURF_COOKIE", "SURF_COOKIE")
    if cookie:
        return CookieAuth(cookie)

    username = _env("BLUESURF_USERNAME", "SURF_USERNAME")
    password = _env("BLUESURF_PASSWORD", "SURF_PASSWORD")
    if username and password:
        return CredentialsAuth(username, password)

    stored = load_stored_credentials()
    if stored:
        return CredentialsAuth(stored[0], stored[1])

    raise RuntimeError(
        "Falta configuración de autenticación: corre `bluesurf-mcp login`, "
        "o define BLUESURF_COOKIE, o bien BLUESURF_USERNAME y BLUESURF_PASSWORD."
    )


def _base_url() -> str:
    return _env("BLUESURF_BASE_URL", "SURF_BASE_URL") or DEFAULT_BASE_URL


async def _client() -> BlueSurfClient:
    client = BlueSurfClient(base_url=_base_url())
    await client.login(_build_auth())
    return client


@mcp.tool()
async def mis_proyectos() -> list[dict]:
    """Lista los proyectos del usuario (id, smallCode, code, name).

    El ``smallCode`` (p. ej. "PROJ") es lo que se pasa a buscar_mis_tickets.
    """
    client = await _client()
    try:
        proyectos = await client.mis_proyectos()
        return [
            {k: p.get(k) for k in ("id", "smallCode", "code", "name")}
            for p in proyectos
        ]
    finally:
        await client.aclose()


@mcp.tool()
async def buscar_mis_tickets(project: str, include_closed: bool = False) -> list[dict]:
    """Lista los tickets asignados al usuario en un proyecto de BlueSurf.

    Args:
        project: smallCode del proyecto (p. ej. "PROJ"), prefijo de los códigos
            de ticket (PROJ-123). Usa mis_proyectos para descubrirlo.
        include_closed: si True incluye tickets en estados finales; por defecto
            solo los abiertos.
    """
    client = await _client()
    try:
        tickets = await client.mis_tickets(project, include_closed=include_closed)
        return [asdict(t) for t in tickets]
    finally:
        await client.aclose()


@mcp.tool()
async def obtener_ticket(code: str) -> dict:
    """Devuelve el detalle de un ticket de BlueSurf por su código (p. ej. PROJ-123)."""
    client = await _client()
    try:
        ticket = await client.obtener_ticket(code)
        return asdict(ticket)
    finally:
        await client.aclose()


@mcp.tool()
async def listar_adjuntos(code: str) -> list[dict]:
    """Lista los archivos de la sección Files de un ticket, sin descargarlos.

    Args:
        code: código del ticket (p. ej. PROJ-123).
    """
    client = await _client()
    try:
        adjuntos = await client.listar_adjuntos(code)
        return [
            {"id": a.id, "name": a.name, "is_image": a.is_image} for a in adjuntos
        ]
    finally:
        await client.aclose()


@mcp.tool()
async def descargar_adjuntos(
    code: str, destino: str, archivo_id: str | None = None
) -> list[dict]:
    """Descarga los adjuntos de un ticket a una carpeta local.

    Args:
        code: código del ticket (p. ej. PROJ-123).
        destino: directorio donde se guardan los archivos. Se crea si no existe.
        archivo_id: si se indica, descarga solo ese adjunto; si no, descarga todos.
    """
    client = await _client()
    try:
        archivos = await client.descargar_adjuntos(
            code, destino, archivo_id=archivo_id
        )
        return [
            {
                "id": archivo.id,
                "name": archivo.name,
                "path": archivo.path,
                "content_type": archivo.content_type,
                "size": len(archivo.content),
            }
            for archivo in archivos
        ]
    finally:
        await client.aclose()


def main() -> None:
    """Entrypoint para correr el servidor MCP por stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
