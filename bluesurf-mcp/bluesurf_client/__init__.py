"""Núcleo para hablar con BlueSurf.

Este paquete concentra toda la lógica reutilizable: autenticación (pluggable),
manejo de sesión/cookie, lecturas y las dos escrituras (adjuntar un archivo y
publicar un comentario). Los adaptadores (el servidor MCP local y una eventual
CLI) se construyen encima de esto sin duplicar lógica.
"""

from bluesurf_client.auth import AuthError, AuthProvider, CookieAuth, CredentialsAuth
from bluesurf_client.constants import DEFAULT_BASE_URL
from bluesurf_client.client import BlueSurfClient
from bluesurf_client.models import Attachment, Comment, DownloadedFile, Ticket, User

__all__ = [
    "BlueSurfClient",
    "Ticket",
    "Comment",
    "User",
    "Attachment",
    "DownloadedFile",
    "AuthProvider",
    "AuthError",
    "CredentialsAuth",
    "CookieAuth",
    "DEFAULT_BASE_URL",
]
