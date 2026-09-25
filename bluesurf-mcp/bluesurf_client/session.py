"""Cliente de sesión HTTP con manejo de cookie y re-auth ante 401.

Envuelve ``httpx.AsyncClient``. La construcción no tiene efectos: la
autenticación es explícita vía :meth:`login`, que recibe el ``AuthProvider``
(inyección por método). Solo expone verbos de lectura (GET): el intermediario es
de solo lectura por diseño, así que no hay POST/PUT/PATCH/DELETE aquí.
"""

from __future__ import annotations

from typing import Any

import httpx

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.constants import DEFAULT_BASE_URL


class BlueSurfSession:
    """Sesión de solo lectura contra la API de BlueSurf."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        self._auth: AuthProvider | None = None

    @property
    def authenticated(self) -> bool:
        return self._auth is not None

    async def login(self, auth: AuthProvider) -> None:
        """Autentica la sesión. Guarda el ``auth`` para renovar ante un 401."""
        await auth.apply(self._client)
        self._auth = auth

    def cookie(self, name: str) -> str | None:
        """Devuelve el valor de una cookie de la sesión (o ``None``)."""
        return self._client.cookies.get(name)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_json(self, path: str, **kwargs: Any) -> Any:
        """GET que devuelve JSON, re-autenticando una vez si BlueSurf responde 401."""
        return await self._request_json("GET", path, **kwargs)

    async def query_json(self, path: str, json: Any, **kwargs: Any) -> Any:
        """POST de solo lectura: consulta que requiere body de filtro (p. ej. el
        kanban). No muta estado; es una lectura parametrizada."""
        return await self._request_json("POST", path, json=json, **kwargs)

    async def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._auth is None:
            raise AuthError("La sesión no está autenticada: llama a login() primero")

        response = await self._client.request(method, path, **kwargs)

        if response.status_code == 401:
            # La cookie pudo expirar: renovamos una sola vez y reintentamos.
            await self._auth.refresh(self._client)
            response = await self._client.request(method, path, **kwargs)

        if response.status_code == 401:
            raise AuthError("BlueSurf sigue devolviendo 401 tras renovar la sesión")

        response.raise_for_status()
        return response.json()
