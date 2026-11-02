"""Daily report: consultas, las tres formas de línea y el POST vacío."""

from __future__ import annotations

import json

import httpx
import pytest

from bluesurf_client.auth.base import AuthProvider
from bluesurf_client.client import BlueSurfClient
from bluesurf_client.models import ReporteDiario
from bluesurf_client.session import BlueSurfSession
from bluesurf_mcp import server

_FECHA = "2026-10-13"

_PROYECTOS = [
    {
        "id": "p-rwsg",
        "smallCode": "RWSG2",
        "code": "WSG",
        "name": "WSG Rewrite",
        "status": 1,
        "categories": [{"categoryId": "cat-dev"}],
    },
    {
        "id": "p-off",
        "smallCode": "OFF",
        "code": "OFF",
        "name": "Inactivo",
        "status": 0,
        "categories": [],
    },
]

_CATEGORIAS = [
    {
        "id": "sub-gc",
        "name": "Google Calendar",
        "categoryId": "cat-google",
        "categoryName": "Google",
    },
    {
        "id": "sub-code",
        "name": "Construcción / Codificación",
        "categoryId": "cat-dev",
        "categoryName": "Desarrollo",
    },
    {
        "id": "sub-gen-g",
        "name": "General",
        "categoryId": "cat-ges",
        "categoryName": "Gestión",
    },
    {
        "id": "sub-gen-o",
        "name": "General",
        "categoryId": "cat-otro",
        "categoryName": "Otro",
    },
]

_PREVIO = {
    "id": "eff-1",
    "description": "Daily",
    "executed": 0.25,
    "projectId": "p-rwsg",
    "categoryId": "cat-google",
    "subcategoryId": "sub-gc",
    "reporterId": "user-1",
}

_TICKET = {
    "id": "wi-9",
    "code": "RWSG2-9",
    "projectId": "p-rwsg",
    "name": "Tarea",
}


class _NoopAuth(AuthProvider):
    async def apply(self, client: httpx.AsyncClient) -> None:
        return None

    async def refresh(self, client: httpx.AsyncClient) -> None:
        return None


def _reporte(status: int, efforts: list) -> dict:
    horas = sum(float(item.get("executed") or 0) for item in efforts)
    return {
        "id": "rep-1",
        "date": f"{_FECHA}T00:00:00",
        "status": status,
        "reporterId": "user-1",
        "reporterFullName": "Ana",
        "activitiesCount": len(efforts),
        "executedHours": horas,
        "efforts": efforts,
    }


async def _client_contra(handler) -> BlueSurfClient:
    client = BlueSurfClient(base_url="https://surf.test")
    await client._session._client.aclose()
    client._session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://surf.test",
        headers={"Accept": "application/json"},
    )
    client._session._auth = _NoopAuth()
    return client


async def test_post_json_tolera_un_cuerpo_vacio() -> None:
    session = BlueSurfSession(base_url="https://surf.test")
    await session._client.aclose()
    session._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"")
        ),
        base_url="https://surf.test",
    )
    session._auth = _NoopAuth()
    try:
        assert await session.post_json("/api/Effort/DailyReport", {}) is None
    finally:
        await session.aclose()


async def test_proyectos_reporte_deja_fuera_los_inactivos() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/project"
        assert request.url.params["includeCategories"] == "true"
        return httpx.Response(200, json=_PROYECTOS)

    client = await _client_contra(handler)
    try:
        proyectos = await client.proyectos_reporte()
        assert [proyecto.publico() for proyecto in proyectos] == [
            {
                "id": "p-rwsg",
                "smallCode": "RWSG2",
                "code": "WSG",
                "name": "WSG Rewrite",
                "categoryIds": ["cat-dev"],
            }
        ]
    finally:
        await client.aclose()


async def test_listar_categorias_filtra_por_el_proyecto() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/user/current/subcategory":
            return httpx.Response(200, json=_CATEGORIAS)
        if request.url.path == "/api/project":
            return httpx.Response(200, json=_PROYECTOS)
        raise AssertionError(request.url.path)

    client = await _client_contra(handler)
    try:
        categorias = await client.listar_categorias("rwsg2")
        assert [categoria.publico() for categoria in categorias] == [
            {
                "id": "sub-code",
                "name": "Construcción / Codificación",
                "categoryId": "cat-dev",
                "categoryName": "Desarrollo",
            }
        ]
    finally:
        await client.aclose()


async def test_registra_las_tres_formas_en_un_solo_post() -> None:
    posts: list[dict] = []
    lecturas = {"n": 0}
    guardado = _reporte(
        2,
        [_PREVIO, {"id": "eff-nueva"}, {"id": "eff-proy"}, {"id": "eff-wi"}],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST" and path == "/api/Effort/DailyReport":
            posts.append(json.loads(request.content))
            return httpx.Response(200, content=b"")
        if path == f"/api/effort/myDailyReport/{_FECHA}":
            n = lecturas["n"]
            lecturas["n"] = n + 1
            body = _reporte(0, [_PREVIO]) if n == 0 else guardado
            return httpx.Response(200, json=body)
        if path == "/api/user/current/subcategory":
            return httpx.Response(200, json=_CATEGORIAS)
        if path == "/api/project":
            return httpx.Response(200, json=_PROYECTOS)
        if path == "/api/workItem/RWSG2-9":
            return httpx.Response(200, json=_TICKET)
        raise AssertionError(f"{request.method} {path}")

    client = await _client_contra(handler)
    try:
        guardado_dia = await client.registrar_tiempo(
            _FECHA,
            [
                {
                    "horas": 20 / 60,
                    "categoria": "Google: Google Calendar",
                    "descripcion": "Cursor skills",
                },
                {
                    "horas": 1,
                    "categoria": "Construcción / Codificación",
                    "descripcion": "Daily Meeting",
                    "proyecto": "RWSG2",
                },
                {
                    "horas": 2,
                    "categoria": "Desarrollo: Construcción / Codificación",
                    "proyecto": "RWSG2",
                    "ticket": "RWSG2-9",
                    "pendiente": 3,
                },
            ],
            confirmar=True,
        )
    finally:
        await client.aclose()

    assert len(posts) == 1
    cuerpo = posts[0]
    assert cuerpo["status"] == 2
    assert cuerpo["efforts"][0] == _PREVIO
    assert cuerpo["efforts"][1:] == [
        {
            "projectId": None,
            "taskId": None,
            "workItemId": None,
            "description": "Cursor skills",
            "executed": 0.333,
            "pending": None,
            "categoryId": "cat-google",
            "subcategoryId": "sub-gc",
            "deleted": False,
        },
        {
            "projectId": "p-rwsg",
            "taskId": None,
            "workItemId": None,
            "description": "Daily Meeting",
            "executed": 1,
            "pending": None,
            "categoryId": "cat-dev",
            "subcategoryId": "sub-code",
            "deleted": False,
        },
        {
            "projectId": "p-rwsg",
            "taskId": None,
            "workItemId": "wi-9",
            "description": None,
            "executed": 2,
            "pending": 3,
            "categoryId": "cat-dev",
            "subcategoryId": "sub-code",
            "deleted": False,
        },
    ]
    assert guardado_dia.cerrado is True
    assert guardado_dia.publico()["efforts"][3]["id"] == "eff-wi"


async def test_no_escribe_si_no_hay_lineas_o_una_es_invalida() -> None:
    posts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts["n"] += 1
        raise AssertionError("no debería consultar BlueSurf")

    client = await _client_contra(handler)
    try:
        with pytest.raises(ValueError, match="al menos una línea"):
            await client.registrar_tiempo(_FECHA, [])
        with pytest.raises(ValueError, match="Línea 2: La descripción es obligatoria"):
            await client.registrar_tiempo(
                _FECHA,
                [
                    {
                        "horas": 1,
                        "categoria": "Google Calendar",
                        "descripcion": "válida",
                    },
                    {"horas": 1, "categoria": "Google Calendar"},
                ],
            )
    finally:
        await client.aclose()
    assert posts["n"] == 0


async def test_no_escribe_si_el_dia_esta_cerrado() -> None:
    posts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts["n"] += 1
        assert request.url.path == f"/api/effort/myDailyReport/{_FECHA}"
        return httpx.Response(200, json=_reporte(2, [_PREVIO]))

    client = await _client_contra(handler)
    try:
        with pytest.raises(ValueError, match="ya está cerrado"):
            await client.registrar_tiempo(
                _FECHA,
                [{"horas": 1, "categoria": "Google Calendar", "descripcion": "tarde"}],
            )
    finally:
        await client.aclose()
    assert posts["n"] == 0


async def test_categoria_ambigua_falla_y_el_nombre_calificado_resuelve() -> None:
    posts: list[dict] = []
    lecturas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            posts.append(json.loads(request.content))
            return httpx.Response(200, content=b"")
        if path == f"/api/effort/myDailyReport/{_FECHA}":
            n = lecturas["n"]
            lecturas["n"] = n + 1
            efforts = (
                [_PREVIO]
                if n < 2
                else [_PREVIO, {"id": "eff-gen", "subcategoryId": "sub-gen-g"}]
            )
            return httpx.Response(200, json=_reporte(0, efforts))
        if path == "/api/user/current/subcategory":
            return httpx.Response(200, json=_CATEGORIAS)
        raise AssertionError(path)

    client = await _client_contra(handler)
    try:
        with pytest.raises(ValueError, match="Línea 1: .*ambigua"):
            await client.registrar_tiempo(
                _FECHA,
                [{"horas": 1, "categoria": "General", "descripcion": "junta"}],
            )
        assert posts == []
        guardado = await client.registrar_tiempo(
            _FECHA,
            [{"horas": 1, "categoria": "Gestión: General", "descripcion": "junta"}],
        )
    finally:
        await client.aclose()
    assert posts[0]["efforts"][1]["subcategoryId"] == "sub-gen-g"
    assert guardado.publico()["efforts"][1]["id"] == "eff-gen"


async def test_tool_reexpone_el_cliente_sin_el_documento_crudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reporte = ReporteDiario(
        id="rep-1",
        fecha=_FECHA,
        status=0,
        cerrado=False,
        executed_hours=1,
        efforts=[],
        raw={"secreto": True},
    )

    class _Cliente:
        async def proyectos_reporte(self):
            from bluesurf_client.models import ProyectoReporte

            return [
                ProyectoReporte(
                    id="p-rwsg",
                    small_code="RWSG2",
                    code="WSG",
                    name="WSG",
                    category_ids=["cat-dev"],
                )
            ]

        async def listar_categorias(self, proyecto=None):
            from bluesurf_client.models import CategoriaReporte

            assert proyecto == "RWSG2"
            return [
                CategoriaReporte(
                    id="sub-code",
                    name="Construcción / Codificación",
                    category_id="cat-dev",
                    category_name="Desarrollo",
                )
            ]

        async def mi_reporte_diario(self, fecha: str) -> ReporteDiario:
            assert fecha == _FECHA
            return reporte

        async def registrar_tiempo(self, fecha, lineas, confirmar=False):
            assert confirmar is False
            assert lineas[0]["ticket"] == "RWSG2-9"
            return reporte

        async def aclose(self) -> None:
            return None

    async def _falso():
        return _Cliente()

    monkeypatch.setattr(server, "_client", _falso)
    assert await server.proyectos_reporte() == [
        {
            "id": "p-rwsg",
            "smallCode": "RWSG2",
            "code": "WSG",
            "name": "WSG",
            "categoryIds": ["cat-dev"],
        }
    ]
    assert (await server.listar_categorias("RWSG2"))[0]["id"] == "sub-code"
    leido = await server.mi_reporte_diario(_FECHA)
    assert "raw" not in leido
    assert leido["fecha"] == _FECHA
    escrito = await server.registrar_tiempo(
        _FECHA, [{"horas": 1, "categoria": "Google Calendar", "ticket": "RWSG2-9"}]
    )
    assert "raw" not in escrito
    assert escrito["id"] == "rep-1"
