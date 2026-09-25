"""Contrato de autenticación (pluggable).

Un ``AuthProvider`` sabe cómo dejar una petición HTTP autenticada contra BlueSurf.
No asume un mecanismo concreto: una implementación puede hacer login con
credenciales y capturar la cookie ``.AspNetCore.Identity.Application``, otra
puede reusar una cookie exportada del navegador. El núcleo solo depende de esta
interfaz.

Notas sobre la sesión de BlueSurf:
- La sesión viaja por cookie de ASP.NET Core Identity, no por header ``Authorization``.
- Los flags ``samesite=lax`` y ``httponly`` solo afectan al navegador; un cliente
  backend (httpx) puede almacenar y reenviar la cookie sin problema.
"""

from __future__ import annotations

import abc

import httpx


class AuthError(RuntimeError):
    """La autenticación falló o la sesión no pudo renovarse."""


class AuthProvider(abc.ABC):
    """Interfaz que provee/renueva una sesión autenticada contra BlueSurf.

    Las implementaciones concretas se agregan después (login programático,
    cookie del navegador, etc.). El contrato es intencionalmente mínimo.
    """

    @abc.abstractmethod
    async def apply(self, client: httpx.AsyncClient) -> None:
        """Deja ``client`` autenticado.

        Típicamente instala la cookie de sesión en ``client.cookies``. Se llama
        una vez al construir el cliente y de nuevo tras ``refresh``. Debe lanzar
        :class:`AuthError` si no puede autenticar.
        """

    async def refresh(self, client: httpx.AsyncClient) -> None:
        """Renueva la sesión tras un 401.

        Por defecto reintenta ``apply``. Las implementaciones que necesiten
        re-login explícito (p. ej. volver a POSTear credenciales) lo sobrescriben.
        """
        await self.apply(client)
