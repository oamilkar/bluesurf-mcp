"""Autenticación por cookie provista por el consumidor.

El consumidor entrega una cookie de sesión ya válida (p. ej. extraída de una
sesión de navegador autenticada). Esta clase la instala en el cliente httpx. No
persiste nada y no puede renovar la sesión por sí sola: si expira, es
responsabilidad del consumidor entregar una cookie fresca.
"""

from __future__ import annotations

import httpx

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.constants import IDENTITY_COOKIE


class CookieAuth(AuthProvider):
    """Usa una cookie de sesión provista por el consumidor.

    Por defecto asume la cookie ``.AspNetCore.Identity.Application``; se puede
    indicar otro nombre si hiciera falta.
    """

    def __init__(self, cookie_value: str, *, cookie_name: str = IDENTITY_COOKIE) -> None:
        if not cookie_value:
            raise ValueError("cookie_value es obligatorio")
        self._cookie_value = cookie_value
        self._cookie_name = cookie_name

    async def apply(self, client: httpx.AsyncClient) -> None:
        domain = client.base_url.host
        client.cookies.set(
            self._cookie_name, self._cookie_value, domain=domain, path="/"
        )

    async def refresh(self, client: httpx.AsyncClient) -> None:
        raise AuthError(
            "La cookie provista expiró o fue rechazada. CookieAuth no puede "
            "renovar la sesión: entrega una cookie fresca (o usa CredentialsAuth)."
        )
