"""Núcleo de solo lectura para hablar con BlueSurf.

Este paquete concentra toda la lógica reutilizable: autenticación (pluggable),
manejo de sesión/cookie, endpoints de lectura y modelos tipados. Los adaptadores
(el servidor MCP local y una eventual CLI) se construyen encima de esto sin
duplicar lógica.

Diseño de solo lectura: aquí no se expone ninguna operación de escritura.
"""

from bluesurf_client.auth import AuthError, AuthProvider, CookieAuth, CredentialsAuth
from bluesurf_client.constants import DEFAULT_BASE_URL
from bluesurf_client.client import BlueSurfClient
from bluesurf_client.models import Comment, Ticket, User

__all__ = [
    "BlueSurfClient",
    "Ticket",
    "Comment",
    "User",
    "AuthProvider",
    "AuthError",
    "CredentialsAuth",
    "CookieAuth",
    "DEFAULT_BASE_URL",
]
