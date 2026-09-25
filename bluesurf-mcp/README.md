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

## Guardar credenciales (`login` / `logout`)

La contraseña no tiene que ir en `mcp.json`. Una vez, en una terminal:

```bash
bluesurf-mcp login
```

Pide usuario y contraseña, valida contra BlueSurf y guarda la contraseña en el
almacén del sistema (Credential Manager en Windows, Keychain en macOS, Secret
Service en Linux). El username queda en un JSON local, sin la contraseña.

```bash
bluesurf-mcp logout
```

borra lo guardado.

## Configuración (variables de entorno)

El entorno **gana** sobre lo guardado con `login`. Útil para CI o para
sobrescribir sin tocar el almacén.

Claves canónicas `BLUESURF_*`; se aceptan `SURF_*` como fallback.

- `BLUESURF_BASE_URL` — URL base (opcional; default `https://surf.bluepeople.com`).
- `BLUESURF_COOKIE` — cookie de sesión ya válida → usa `CookieAuth`.
- `BLUESURF_USERNAME` + `BLUESURF_PASSWORD` — credenciales → usa `CredentialsAuth`.

Precedencia: cookie en env → usuario/contraseña en env → `bluesurf-mcp login`.

El núcleo (`bluesurf_client`) no persiste secretos.

## Correr el servidor

```bash
bluesurf-mcp
```

Se comunica por **stdio** (el transporte estándar para MCP local). Sin
argumentos no pide contraseña: usa env o las credenciales de `login`.

## Registrar el MCP en un cliente

### Claude Code / Cursor (`.mcp.json` o config de usuario)

Tras `bluesurf-mcp login`:

```json
{
  "mcpServers": {
    "bluesurf": {
      "command": "bluesurf-mcp"
    }
  }
}
```

Si `bluesurf-mcp` no está en el `PATH`, usa la ruta absoluta al ejecutable del
venv o `python -m bluesurf_mcp`.

Las variables `BLUESURF_*` en `env` siguen siendo válidas como override; no hace
falta poner la contraseña ahí.

## Tools expuestas (solo lectura)

- `mis_proyectos` — proyectos del usuario (id, smallCode, code, name).
- `buscar_mis_tickets(project, include_closed=False)` — tickets asignados al usuario.
- `obtener_ticket(code)` — detalle de un ticket por su código (p. ej. `PROJ-123`).

## Usar el cliente desde Python

El paquete de import del núcleo es `bluesurf_client`:

```python
from bluesurf_client import BlueSurfClient, CredentialsAuth  # o CookieAuth
```
