"""Constantes del núcleo."""

# URL base por defecto de BlueSurf. Sobrescribible al construir el cliente/auth.
DEFAULT_BASE_URL = "https://surf.bluepeople.com"

# Cookie de sesión que emite ASP.NET Core Identity al iniciar sesión.
IDENTITY_COOKIE = ".AspNetCore.Identity.Application"

# Ruta del endpoint de login (POST JSON {"email", "password"}).
LOGIN_PATH = "/api/login"
