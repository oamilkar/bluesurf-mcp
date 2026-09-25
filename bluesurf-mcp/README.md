# bluesurf-mcp

Servidor MCP local de **solo lectura** para que Claude u otros agentes IA lean
tickets de **BlueSurf**. Un solo paquete PyPI incluye el núcleo
(`bluesurf_client`) y el adaptador MCP (`bluesurf_mcp`).

**Solo lectura por diseño:** no hay operaciones de escritura.

## Instalación

```bash
pip install bluesurf-mcp
```

En este monorepo, modo editable:

```bash
pip install -e ./bluesurf-mcp
```

## Configuración (variables de entorno)

El consumidor entrega credenciales o cookie; la librería no persiste nada.

Claves canónicas `BLUESURF_*`; se aceptan `SURF_*` como fallback.

- `BLUESURF_BASE_URL` — URL base (opcional; default `https://surf.bluepeople.com`).
- `BLUESURF_COOKIE` — cookie de sesión ya válida → usa `CookieAuth`.
- `BLUESURF_USERNAME` + `BLUESURF_PASSWORD` — credenciales → usa `CredentialsAuth`.

## Correr el servidor

```bash
bluesurf-mcp
```

Se comunica por **stdio** (el transporte estándar para MCP local).

## Registrar el MCP en un cliente

### Claude Code (`.mcp.json` o config de usuario)

```json
{
  "mcpServers": {
    "bluesurf": {
      "command": "bluesurf-mcp",
      "env": {
        "BLUESURF_USERNAME": "usuario",
        "BLUESURF_PASSWORD": "contraseña"
      }
    }
  }
}
```

Si `bluesurf-mcp` no está en el `PATH`, usa la ruta absoluta al ejecutable del
venv o `python -m bluesurf_mcp.server`.

## Tools expuestas (solo lectura)

- `mis_proyectos` — proyectos del usuario (id, smallCode, code, name).
- `buscar_mis_tickets(project, include_closed=False)` — tickets asignados al usuario.
- `obtener_ticket(code)` — detalle de un ticket por su código (p. ej. `PROJ-123`).

## Usar el cliente desde Python

El paquete de import del núcleo es `bluesurf_client`:

```python
from bluesurf_client import BlueSurfClient, CredentialsAuth  # o CookieAuth
```
