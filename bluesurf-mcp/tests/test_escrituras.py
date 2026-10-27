"""Adjuntar un archivo y publicar un comentario: multipart y reintento 401."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.client import BlueSurfClient
from bluesurf_client.models import Attachment, Comment
from bluesurf_client.session import BlueSurfSession
from bluesurf_mcp import server

_TICKET = {
    "id": "wi-1",
    "code": "PROJ-1",
    "files": [{"id": "doc-1", "workItemId": "wi-1", "isImage": False}],
    "comments": [{"id": "c-old", "comment": "viejo", "createdByFullName": "Ana"}],
}

_TRAS_ARCHIVO = {
    **_TICKET,
    "files": [
        *_TICKET["files"],
        {
            "id": "doc-2",
            "workItemId": "wi-1",
            "isImage": False,
            "name": "nota.txt",
        },
    ],
}

_TRAS_COMENTARIO = {
    **_TICKET,
    "comments": [
        *_TICKET["comments"],
        {
            "id": "c-new",
            "comment": "<p>hola &lt; b</p>",
            "createdByFullName": "Ana",
            "createdAt": "2026-10-27T00:00:00",
        },
    ],
}


class _CountingAuth(AuthProvider):
    def __init__(self) -> None:
        self.refreshes = 0

    async def apply(self, client: httpx.AsyncClient) -> None:
        return None

    async def refresh(self, client: httpx.AsyncClient) -> None:
        self.refreshes += 1


def _client_nuevo() -> tuple[BlueSurfClient, _CountingAuth]:
    return BlueSurfClient(base_url="https://surf.test"), _CountingAuth()


async def _abrir(client: BlueSurfClient, auth: _CountingAuth, handler) -> None:
    await client._session._client.aclose()
    client._session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://surf.test",
        headers={"Accept": "application/json"},
    )
    client._session._auth = auth


async def test_adjuntar_archivo_sube_el_nombre_y_devuelve_el_nuevo(
    tmp_path: Path,
) -> None:
    origen = tmp_path / "subdir" / "nota.txt"
    origen.parent.mkdir()
    origen.write_bytes(b"hola <binario>")
    vistos: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistos.append(request)
        if request.method == "GET" and request.url.path == "/api/workItem/PROJ-1":
            return httpx.Response(200, json=_TICKET)
        if (
            request.method == "POST"
            and request.url.path == "/api/workItem/wi-1/file"
        ):
            cuerpo = request.content
            assert b'name="file"' in cuerpo
            assert b'filename="nota.txt"' in cuerpo
            assert b"hola <binario>" in cuerpo
            assert b"subdir" not in cuerpo
            tipo = request.headers["content-type"]
            assert tipo.startswith("multipart/form-data")
            return httpx.Response(200, json=_TRAS_ARCHIVO)
        return httpx.Response(404, json={"path": request.url.path})

    client, auth = _client_nuevo()
    await _abrir(client, auth, handler)
    try:
        adjunto = await client.adjuntar_archivo("PROJ-1", origen)
    finally:
        await client.aclose()

    assert adjunto.id == "doc-2"
    assert adjunto.name == "nota.txt"
    assert adjunto.is_image is False
    assert [r.method for r in vistos] == ["GET", "POST"]


async def test_agregar_comentario_envuelve_el_texto_en_un_parrafo() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/workItem/PROJ-1":
            return httpx.Response(200, json=_TICKET)
        if (
            request.method == "POST"
            and request.url.path == "/api/WorkItem/wi-1/comment"
        ):
            cuerpo = request.content
            assert b'name="comment"' in cuerpo
            assert b'filename=' not in cuerpo
            assert (
                b'{"comment":"<p>hola &lt; b</p>"}' in cuerpo
            )
            return httpx.Response(200, json=_TRAS_COMENTARIO)
        return httpx.Response(404, json={"path": request.url.path})

    client, auth = _client_nuevo()
    await _abrir(client, auth, handler)
    try:
        comentario = await client.agregar_comentario("PROJ-1", "  hola < b  ")
    finally:
        await client.aclose()

    assert comentario.id == "c-new"
    assert comentario.author == "Ana"
    assert comentario.body == "<p>hola &lt; b</p>"
    assert comentario.created_at == "2026-10-27T00:00:00"


async def test_post_multipart_reintenta_una_vez_ante_401(tmp_path: Path) -> None:
    origen = tmp_path / "nota.txt"
    origen.write_bytes(b"hola")
    posts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/workItem/PROJ-1":
            return httpx.Response(200, json=_TICKET)
        if request.method == "POST" and request.url.path == "/api/workItem/wi-1/file":
            posts["n"] += 1
            assert b"hola" in request.content
            if posts["n"] == 1:
                return httpx.Response(401)
            return httpx.Response(200, json=_TRAS_ARCHIVO)
        return httpx.Response(404)

    client, auth = _client_nuevo()
    await _abrir(client, auth, handler)
    try:
        adjunto = await client.adjuntar_archivo("PROJ-1", origen)
    finally:
        await client.aclose()

    assert posts["n"] == 2
    assert auth.refreshes == 1
    assert adjunto.id == "doc-2"


async def test_post_multipart_no_reintenta_mas_de_una_vez() -> None:
    session = BlueSurfSession(base_url="https://surf.test")
    auth = _CountingAuth()
    await session._client.aclose()
    session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
        base_url="https://surf.test",
    )
    session._auth = auth
    try:
        with pytest.raises(AuthError):
            await session.post_multipart(
                "/api/workItem/wi-1/file",
                files=lambda: {"file": ("nota.txt", b"hola", "text/plain")},
            )
    finally:
        await session.aclose()
    assert auth.refreshes == 1


async def test_tool_adjuntar_archivo_devuelve_el_archivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cliente:
        async def adjuntar_archivo(self, code: str, ruta: Path | str) -> Attachment:
            assert code == "PROJ-1"
            assert str(ruta) == "C:/tmp/nota.txt"
            return Attachment(
                id="doc-2",
                work_item_id="wi-1",
                name="nota.txt",
                is_image=False,
            )

        async def aclose(self) -> None:
            return None

    async def _falso() -> _Cliente:
        return _Cliente()

    monkeypatch.setattr(server, "_client", _falso)
    assert await server.adjuntar_archivo("PROJ-1", "C:/tmp/nota.txt") == {
        "id": "doc-2",
        "name": "nota.txt",
        "is_image": False,
    }


async def test_tool_agregar_comentario_devuelve_el_comentario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cliente:
        async def agregar_comentario(self, code: str, texto: str) -> Comment:
            assert code == "PROJ-1"
            assert texto == "hola"
            return Comment(
                id="c-new",
                author="Ana",
                body="<p>hola</p>",
                created_at="2026-10-27T00:00:00",
            )

        async def aclose(self) -> None:
            return None

    async def _falso() -> _Cliente:
        return _Cliente()

    monkeypatch.setattr(server, "_client", _falso)
    assert await server.agregar_comentario("PROJ-1", "hola") == {
        "id": "c-new",
        "author": "Ana",
        "body": "<p>hola</p>",
        "created_at": "2026-10-27T00:00:00",
    }
