"""Descarga de adjuntos: URLs de imagen/archivo, reintento 401 y nombres seguros."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.client import BlueSurfClient
from bluesurf_client.models import Attachment, DownloadedFile
from bluesurf_client.session import BlueSurfSession
from bluesurf_mcp import server

_TICKET = {
    "id": "wi-1",
    "code": "PROJ-1",
    "files": [
        {"id": "img-1", "workItemId": "wi-1", "isImage": True},
        {"id": "doc-1", "workItemId": "wi-1", "isImage": False},
    ],
}


class _CountingAuth(AuthProvider):
    def __init__(self) -> None:
        self.refreshes = 0

    async def apply(self, client: httpx.AsyncClient) -> None:
        return None

    async def refresh(self, client: httpx.AsyncClient) -> None:
        self.refreshes += 1


def _routes(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/api/workItem/PROJ-1":
        return httpx.Response(200, json=_TICKET)
    if path == "/api/workItem/wi-1/fileName/img-1":
        return httpx.Response(200, json="foto.png")
    if path == "/api/workItem/wi-1/fileName/doc-1":
        return httpx.Response(
            200,
            content=b"../secreto.txt",
            headers={"content-type": "text/plain"},
        )
    if path == "/api/workItem/wi-1/image/img-1":
        assert request.headers["accept"] == "*/*"
        return httpx.Response(
            200, content=b"PNG", headers={"content-type": "image/png"}
        )
    if path == "/api/workItem/wi-1/file/doc-1":
        assert request.headers["accept"] == "*/*"
        return httpx.Response(
            200, content=b"PDF", headers={"content-type": "application/pdf"}
        )
    return httpx.Response(404, json={"path": path})


async def _client_contra(handler) -> BlueSurfClient:
    client = BlueSurfClient(base_url="https://surf.test")
    await client._session._client.aclose()
    client._session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://surf.test",
        headers={"Accept": "application/json"},
    )
    client._session._auth = _CountingAuth()
    return client


async def test_listar_resuelve_nombres_y_descarga_por_tipo(tmp_path: Path) -> None:
    client = await _client_contra(_routes)
    try:
        adjuntos = await client.listar_adjuntos("PROJ-1")
        assert [(a.id, a.name, a.is_image) for a in adjuntos] == [
            ("img-1", "foto.png", True),
            ("doc-1", "../secreto.txt", False),
        ]

        guardados = await client.descargar_adjuntos("PROJ-1", tmp_path)
    finally:
        await client.aclose()

    por_id = {archivo.id: archivo for archivo in guardados}
    imagen = por_id["img-1"]
    documento = por_id["doc-1"]

    assert imagen.content == b"PNG"
    assert imagen.content_type == "image/png"
    assert Path(imagen.path or "").name == "foto.png"
    assert Path(imagen.path or "").read_bytes() == b"PNG"

    assert documento.name == "secreto.txt"
    assert documento.content == b"PDF"
    destino = Path(documento.path or "")
    assert destino.name == "secreto.txt"
    assert destino.parent == tmp_path.resolve()
    assert destino.read_bytes() == b"PDF"
    assert destino.resolve() == (tmp_path / "secreto.txt").resolve()


async def test_get_bytes_reintenta_una_vez_ante_401() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        assert request.headers["accept"] == "*/*"
        if calls["n"] == 1:
            return httpx.Response(401)
        return httpx.Response(
            200, content=b"ok", headers={"content-type": "application/pdf"}
        )

    auth = _CountingAuth()
    session = BlueSurfSession(base_url="https://surf.test")
    await session._client.aclose()
    session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://surf.test",
    )
    session._auth = auth
    try:
        body = await session.get_bytes("/api/workItem/wi-1/file/doc-1")
    finally:
        await session.aclose()

    assert body.content == b"ok"
    assert body.content_type == "application/pdf"
    assert auth.refreshes == 1
    assert calls["n"] == 2


async def test_get_bytes_no_reintenta_mas_de_una_vez() -> None:
    auth = _CountingAuth()
    session = BlueSurfSession(base_url="https://surf.test")
    await session._client.aclose()
    session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(401)),
        base_url="https://surf.test",
    )
    session._auth = auth
    try:
        with pytest.raises(AuthError):
            await session.get_bytes("/api/workItem/wi-1/file/doc-1")
    finally:
        await session.aclose()
    assert auth.refreshes == 1


async def test_tool_descargar_adjuntos_devuelve_la_ruta(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Cliente:
        async def descargar_adjuntos(
            self,
            code: str,
            destino: Path | str | None = None,
            *,
            archivo_id: str | None = None,
        ) -> list[DownloadedFile]:
            assert code == "PROJ-1"
            assert archivo_id is None
            carpeta = Path(destino or tmp_path)
            carpeta.mkdir(parents=True, exist_ok=True)
            ruta = carpeta / "nota.txt"
            ruta.write_bytes(b"hola")
            return [
                DownloadedFile(
                    id="f1",
                    name="nota.txt",
                    content_type="text/plain",
                    content=b"hola",
                    path=str(ruta),
                )
            ]

        async def aclose(self) -> None:
            return None

    async def _falso() -> _Cliente:
        return _Cliente()

    monkeypatch.setattr(server, "_client", _falso)
    result = await server.descargar_adjuntos("PROJ-1", str(tmp_path))

    assert result == [
        {
            "id": "f1",
            "name": "nota.txt",
            "path": str(tmp_path / "nota.txt"),
            "content_type": "text/plain",
            "size": 4,
        }
    ]
    assert (tmp_path / "nota.txt").read_bytes() == b"hola"


async def test_tool_listar_adjuntos_no_incluye_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Cliente:
        async def listar_adjuntos(self, code: str) -> list[Attachment]:
            assert code == "PROJ-1"
            return [
                Attachment(
                    id="f1",
                    work_item_id="wi-1",
                    name="nota.txt",
                    is_image=False,
                )
            ]

        async def aclose(self) -> None:
            return None

    async def _falso() -> _Cliente:
        return _Cliente()

    monkeypatch.setattr(server, "_client", _falso)
    assert await server.listar_adjuntos("PROJ-1") == [
        {"id": "f1", "name": "nota.txt", "is_image": False}
    ]
