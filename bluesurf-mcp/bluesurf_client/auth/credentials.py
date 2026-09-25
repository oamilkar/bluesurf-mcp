"""Autenticación por credenciales (usuario/contraseña).

El consumidor entrega usuario y contraseña; esta clase hace el POST de login y
deja la cookie de sesión en el cliente httpx (en memoria). **No** persiste nada
en disco: ni credenciales ni cookie. Las credenciales se mantienen en memoria
solo para poder re-loguear si la sesión expira (401) durante la vida de la
instancia.
"""

from __future__ import annotations

import httpx

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.constants import IDENTITY_COOKIE, LOGIN_PATH


class CredentialsAuth(AuthProvider):
    """Inicia sesión con usuario/contraseña contra ``POST /api/login``.

    El endpoint espera JSON ``{"email", "password"}`` (el campo es ``email``
    aunque el valor sea un nombre de usuario). No usa CSRF/anti-forgery.
    """

    def __init__(self, username: str, password: str) -> None:
        if not username or not password:
            raise ValueError("username y password son obligatorios")
        # Solo en memoria; nunca se escriben a disco.
        self._username = username
        self._password = password

    async def apply(self, client: httpx.AsyncClient) -> None:
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

    async def refresh(self, client: httpx.AsyncClient) -> None:
        # La cookie expiró: volvemos a loguear con las credenciales en memoria.
        await self.apply(client)
