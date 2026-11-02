"""Núcleo para hablar con BlueSurf.

Este paquete concentra toda la lógica reutilizable: autenticación (pluggable),
manejo de sesión/cookie, lecturas y las escrituras (adjuntar un archivo,
publicar un comentario y registrar tiempo). Los adaptadores (el servidor MCP
local y una eventual CLI) se construyen encima de esto sin duplicar lógica.
"""

from bluesurf_client.auth import AuthError, AuthProvider, CookieAuth, CredentialsAuth
from bluesurf_client.constants import DEFAULT_BASE_URL
from bluesurf_client.client import BlueSurfClient
from bluesurf_client.models import (
    Attachment,
    CategoriaReporte,
    Comment,
    DownloadedFile,
    EsfuerzoDiario,
    ProyectoReporte,
    ReporteDiario,
    Ticket,
    User,
)

__all__ = [
    "BlueSurfClient",
    "Ticket",
    "Comment",
    "User",
    "Attachment",
    "DownloadedFile",
    "ProyectoReporte",
    "CategoriaReporte",
    "EsfuerzoDiario",
    "ReporteDiario",
    "AuthProvider",
    "AuthError",
    "CredentialsAuth",
    "CookieAuth",
    "DEFAULT_BASE_URL",
]
