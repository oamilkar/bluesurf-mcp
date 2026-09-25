"""Autenticación pluggable contra BlueSurf.

El consumidor decide el mecanismo y entrega credenciales o cookie:
- :class:`CredentialsAuth` — usuario/contraseña (hace login).
- :class:`CookieAuth` — cookie de sesión ya válida.

La librería no persiste credenciales ni sesión: la cookie vive solo en memoria
durante el ciclo de vida de la instancia del cliente.
"""

from bluesurf_client.auth.base import AuthError, AuthProvider
from bluesurf_client.auth.cookie import CookieAuth
from bluesurf_client.auth.credentials import CredentialsAuth

__all__ = ["AuthProvider", "AuthError", "CredentialsAuth", "CookieAuth"]
