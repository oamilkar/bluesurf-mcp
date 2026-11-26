"""Autenticación por credenciales (usuario/contraseña).

El consumidor entrega usuario y contraseña; esta clase puede inyectar una
cookie cacheada o hacer el POST de login y dejar la cookie en el cliente httpx.
Con ``persist_session`` el adaptador MCP escribe la cookie en el keyring del SO
(después de un POST exitoso); no aplica al flujo ``BLUESURF_COOKIE`` solo.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.constants import IDENTITY_COOKIE, LOGIN_PATH


class CredentialsAuth(AuthProvider):
    """Inicia sesión con usuario/contraseña contra ``POST /api/login``.

    El endpoint espera JSON ``{"email", "password"}`` (el campo es ``email``
    aunque el valor sea un nombre de usuario). No usa CSRF/anti-forgery.
    """

    def __init__(
        self,
        username: str,
        password: str,
        *,
        initial_session_cookie: str | None = None,
        persist_session: bool = False,
        persist_cookie: Callable[[str, str], None] | None = None,
    ) -> None:
        if not username or not password:
            raise ValueError("username y password son obligatorios")
        self._username = username
        self._password = password
        raw = initial_session_cookie
        self._initial_session_cookie: str | None = (
            raw.strip() if isinstance(raw, str) and raw.strip() else None
        )
        self._persist_session = persist_session
        self._persist_cookie = persist_cookie

    async def apply(self, client: httpx.AsyncClient) -> None:
        await self._apply(client, prefer_cached=True)

    async def refresh(self, client: httpx.AsyncClient) -> None:
        await self._apply(client, prefer_cached=False)

    async def _apply(
        self, client: httpx.AsyncClient, *, prefer_cached: bool
    ) -> None:
        if prefer_cached and self._initial_session_cookie is not None:
            client.cookies.set(IDENTITY_COOKIE, self._initial_session_cookie)
            return

        base = str(client.base_url).rstrip("/")
        try:
            response = await client.post(
                LOGIN_PATH,
                json={"email": self._username, "password": self._password},
                headers={"Origin": base, "Referer": f"{base}/login"},
            )
        except httpx.HTTPError as exc:  # pragma: no cover - error de red
            raise AuthError(f"No se pudo contactar el login de BlueSurf: {exc}") from exc

        if response.status_code in (400, 401, 403):
            raise AuthError(
                f"Login rechazado por BlueSurf (HTTP {response.status_code}): "
                "revisa usuario/contraseña"
            )
        response.raise_for_status()

        # httpx captura el Set-Cookie automáticamente en client.cookies.
        if IDENTITY_COOKIE not in client.cookies:
            raise AuthError(
                "El login respondió 200 pero no llegó la cookie de sesión "
                f"'{IDENTITY_COOKIE}'"
            )

        if self._persist_session and self._persist_cookie is not None:
            value = client.cookies.get(IDENTITY_COOKIE)
            if value:
                self._persist_cookie(self._username, str(value))
