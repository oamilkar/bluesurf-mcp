# bluesurf-mcp

Intermediario de **solo lectura** para que Claude u otros agentes IA lean tickets
de **BlueSurf**.

**Unidad publicable:** [`bluesurf-mcp/`](./bluesurf-mcp) — un distro PyPI
(`bluesurf-mcp`) con dos paquetes de import (`bluesurf_client` + `bluesurf_mcp`).
Instalar y correr:

```bash
pip install -e ./bluesurf-mcp
bluesurf-mcp
```

El desarrollo va en `bluesurf-mcp/`. Detalle de tools, variables de entorno y
registro en un cliente MCP: [`bluesurf-mcp/README.md`](./bluesurf-mcp/README.md).

Manual de instalación (Python 3.10+, `pip`, login y Cursor):
[`MANUAL_INSTALACION.md`](./MANUAL_INSTALACION.md).

## Arquitectura

Diseño en capas — toda la lógica vive en el núcleo y los adaptadores son delgados:

```
Agente IA (cliente MCP)
      │  MCP (tools de solo lectura)
      ▼
bluesurf-mcp/bluesurf_mcp      ← servidor MCP local (adaptador)
      │  mis_proyectos, buscar_mis_tickets, obtener_ticket,
      │  listar_adjuntos, descargar_adjuntos
      ▼
bluesurf-mcp/bluesurf_client   ← núcleo reutilizable
   ├─ auth/       interfaz AuthProvider (pluggable)
   ├─ session.py  cookie de sesión + re-auth ante 401
   ├─ client.py   fachada: mis_proyectos, mis_tickets, obtener_ticket,
   │              listar_adjuntos, descargar_adjunto
   └─ models.py   Ticket, Comment, User, Attachment
      │
      ▼
BlueSurf (API existente)
```

**Solo lectura por diseño:** ni el núcleo ni el MCP exponen operaciones de
escritura. El kanban se consulta con un POST de lectura (body de filtro); no hay
mutaciones.

## Desarrollo

Un solo `.venv` compartido en la raíz:

```bash
python -m venv .venv
.venv\Scripts\activate           # Windows PowerShell
pip install -e ./bluesurf-mcp
```

Claves canónicas `BLUESURF_*`; se aceptan `SURF_*` como fallback
(`BLUESURF_USERNAME` / `BLUESURF_PASSWORD` / `BLUESURF_BASE_URL`).

### Scripts de verificación

```bash
python scripts/test_login.py            # prueba el login
python scripts/list_my_tickets.py PROJ # lista mis tickets (agrega --all para cerrados)
```

Ambos leen el `.env` de la raíz (mismas claves que el servidor MCP).

## Usar el cliente desde Python

Tras instalar `bluesurf-mcp`, el import del núcleo es `bluesurf_client`. Las
credenciales o la cookie las provee el consumidor.

```python
from bluesurf_client import BlueSurfClient, CredentialsAuth  # o CookieAuth
```

## Publicar

```bash
cd bluesurf-mcp
python -m build
python -m twine upload --repository testpypi dist/*   # probar en TestPyPI
python -m twine upload dist/*                          # PyPI real
```
