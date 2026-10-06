"""Cliente de solo lectura de BlueSurf (la fachada de alto nivel).

Expone las lecturas centradas en el objetivo: los tickets (work items) asignados
al usuario. En BlueSurf no hay un endpoint "asignados a mí"; se resuelve consultando
el kanban de un proyecto con el filtro ``assignedTo`` puesto en el id del usuario
actual.

Ciclo de vida:
- Construcción sin efectos: ``BlueSurfClient(base_url=...)``.
- Autenticación explícita: ``await client.login(auth)`` (inyección por método).
- Limpieza: ``await client.aclose()``, o usa ``async with`` que la hace sola.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bluesurf_client.auth.base import AuthProvider
from bluesurf_client.constants import DEFAULT_BASE_URL, IDENTITY_COOKIE
from bluesurf_client.models import Attachment, DownloadedFile, Ticket, User
from bluesurf_client.session import BlueSurfSession

_PATH_CURRENT_USER = "/api/instance/currentUser"
_PATH_MY_PROJECTS = "/api/user/current/project"
_PATH_KANBAN = "/api/project/{project}/kanban"
_PATH_WORKITEM = "/api/workItem/{code}"
_PATH_FILE_NAME = "/api/workItem/{work_item_id}/fileName/{file_id}"
_PATH_FILE = "/api/workItem/{work_item_id}/file/{file_id}"
_PATH_IMAGE = "/api/workItem/{work_item_id}/image/{file_id}"

# Body base del kanban (todos los filtros vacíos). Se rellena ``assignedTo`` con
# el id del usuario actual para que BlueSurf filtre del lado servidor.
_KANBAN_FILTER_TEMPLATE: dict[str, Any] = {
    "statuses": [],
    "tags": [],
    "sprints": [],
    "priorities": [],
    "assignedTo": [],
    "reportedBy": [],
    "colors": [],
    "defectsOrigins": [],
    "tagCondition": "and",
    "search": "",
    "quantityPerStatus": [],
}


class BlueSurfClient:
    """Fachada de solo lectura sobre la API de BlueSurf."""

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL) -> None:
        self._session = BlueSurfSession(base_url=base_url)
        self._current_user: User | None = None

    async def __aenter__(self) -> "BlueSurfClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._session.aclose()

    async def login(self, auth: AuthProvider) -> "BlueSurfClient":
        """Autentica la sesión. Devuelve ``self`` para encadenar."""
        await self._session.login(auth)
        return self

    @property
    def authenticated(self) -> bool:
        return self._session.authenticated

    def session_cookie(self, name: str = IDENTITY_COOKIE) -> str | None:
        """Valor de la cookie de sesión (por defecto la de ASP.NET Identity)."""
        return self._session.cookie(name)

    async def aclose(self) -> None:
        await self._session.aclose()

    async def current_user(self) -> User:
        """El usuario autenticado. Se cachea en la instancia tras la 1ª llamada."""
        if self._current_user is None:
            data = await self._session.get_json(_PATH_CURRENT_USER)
            self._current_user = User.from_current_user(data)
        return self._current_user

    async def mis_proyectos(self) -> list[dict]:
        """Proyectos del usuario (crudo). Útil para descubrir el ``smallCode``."""
        data = await self._session.get_json(_PATH_MY_PROJECTS)
        return data if isinstance(data, list) else []

    async def mis_tickets(
        self, project: str, *, include_closed: bool = False
    ) -> list[Ticket]:
        """Tickets asignados al usuario en un proyecto.

        Args:
            project: ``smallCode`` del proyecto (p. ej. ``"PROJ"``), que es el
                prefijo del código de los tickets (``PROJ-123``).
            include_closed: si ``False`` (default) omite los tickets en estados
                finales (cerrados/done); si ``True`` los incluye.

        Nota: el kanban pagina por columna. Con el filtro por asignado el volumen
        es bajo, pero si tuvieras muchísimos tickets abiertos en una sola columna
        podrían no venir todos en una sola respuesta.
        """
        me = await self.current_user()

        body = dict(_KANBAN_FILTER_TEMPLATE)
        body["assignedTo"] = [me.id]

        data = await self._session.query_json(
            _PATH_KANBAN.format(project=project),
            json=body,
            params={"skipWorkItems": "false"},
        )

        tickets: list[Ticket] = []
        for raw in _iter_work_items(data):
            ticket = Ticket.from_json(raw)
            # Safety: garantizamos que sean míos aunque el filtro del servidor
            # cambiara de semántica.
            if ticket.assignee is None or ticket.assignee.id != me.id:
                continue
            if not include_closed and ticket.status_is_final:
                continue
            tickets.append(ticket)
        return tickets

    async def obtener_ticket(self, code: str) -> Ticket:
        """Detalle de un ticket por su código (p. ej. ``"PROJ-123"``)."""
        data = await self._session.get_json(_PATH_WORKITEM.format(code=code))
        return Ticket.from_json(data)

    async def listar_adjuntos(self, code: str) -> list[Attachment]:
        """Archivos de la sección Files de un ticket, con el nombre resuelto.

        El detalle trae ``files[]`` sin nombre usable. Cada nombre se pide con
        ``GET /api/workItem/{id}/fileName/{fileId}``.
        """
        ticket = await self.obtener_ticket(code)
        adjuntos: list[Attachment] = []
        for raw in ticket.raw.get("files") or []:
            if not isinstance(raw, dict):
                continue
            adjunto = Attachment.from_json(raw)
            if not adjunto.work_item_id:
                adjunto.work_item_id = ticket.id
            adjunto.name = await self._nombre_adjunto(adjunto.work_item_id, adjunto.id)
            adjuntos.append(adjunto)
        return adjuntos

    async def descargar_adjunto(
        self,
        code: str,
        archivo_id: str,
        *,
        destino: Path | str | None = None,
    ) -> DownloadedFile:
        """Descarga un adjunto del ticket.

        Las imágenes salen de ``/image/`` y el resto de ``/file/``. Si
        ``destino`` está presente, escribe el archivo ahí y rellena ``path``.
        """
        guardados = await self.descargar_adjuntos(
            code, destino, archivo_id=archivo_id
        )
        return guardados[0]

    async def descargar_adjuntos(
        self,
        code: str,
        destino: Path | str | None = None,
        *,
        archivo_id: str | None = None,
    ) -> list[DownloadedFile]:
        """Descarga los adjuntos del ticket en una sola sesión.

        Con ``archivo_id`` baja solo ese archivo. Sin él, baja todos. ``destino``
        es la carpeta donde se escriben; si es ``None`` solo devuelve los bytes.
        """
        adjuntos = await self.listar_adjuntos(code)
        if archivo_id is not None:
            adjuntos = [a for a in adjuntos if a.id == archivo_id]
            if not adjuntos:
                raise LookupError(
                    f"El ticket {code} no tiene un adjunto con id {archivo_id}"
                )

        carpeta = Path(destino) if destino is not None else None
        if carpeta is not None:
            carpeta.mkdir(parents=True, exist_ok=True)

        descargados: list[DownloadedFile] = []
        for adjunto in adjuntos:
            descargados.append(await self._bajar_adjunto(adjunto, carpeta))
        return descargados

    async def _nombre_adjunto(self, work_item_id: str, file_id: str) -> str | None:
        body = await self._session.get_bytes(
            _PATH_FILE_NAME.format(work_item_id=work_item_id, file_id=file_id)
        )
        name = _parse_file_name(body.content, body.content_type)
        return name or None

    async def _bajar_adjunto(
        self, adjunto: Attachment, destino: Path | None
    ) -> DownloadedFile:
        plantilla = _PATH_IMAGE if adjunto.is_image else _PATH_FILE
        body = await self._session.get_bytes(
            plantilla.format(work_item_id=adjunto.work_item_id, file_id=adjunto.id)
        )
        nombre = _nombre_seguro(adjunto.name, adjunto.id)
        ruta: Path | None = None
        if destino is not None:
            ruta = _ruta_destino(destino, nombre, adjunto.id)
            ruta.write_bytes(body.content)
        return DownloadedFile(
            id=adjunto.id,
            name=ruta.name if ruta is not None else nombre,
            content_type=body.content_type,
            content=body.content,
            path=str(ruta) if ruta is not None else None,
        )


def _parse_file_name(content: bytes, content_type: str | None) -> str:
    """El endpoint fileName responde texto plano o un string JSON."""
    text = content.decode("utf-8-sig").strip().strip("\x00")
    if not text:
        return ""
    looks_json = text[:1] in {'"', "{", "["} or (
        content_type is not None and "json" in content_type.lower()
    )
    if not looks_json:
        return text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, str):
        return parsed.strip()
    if isinstance(parsed, dict):
        for key in ("name", "fileName", "filename"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return text


def _nombre_seguro(name: str | None, archivo_id: str) -> str:
    """Solo el nombre de archivo: descarta directorios y ``..``."""
    candidate = Path(name or "").name.strip().rstrip(".")
    if not candidate or candidate in {".", ".."}:
        return archivo_id
    return candidate


def _ruta_destino(destino: Path, nombre: str, archivo_id: str) -> Path:
    """Ruta dentro de ``destino``. Si el nombre ya existe, le añade el id."""
    root = destino.resolve()
    filename = _nombre_seguro(nombre, archivo_id)
    candidate = (root / filename).resolve()
    if not candidate.is_relative_to(root):
        filename = archivo_id
        candidate = (root / filename).resolve()
    if candidate.exists():
        path = Path(filename)
        candidate = (root / f"{path.stem}-{archivo_id}{path.suffix}").resolve()
    return candidate


def _iter_work_items(kanban: Any):
    """Aplana la respuesta del kanban → work items.

    Estructura: lista por tipo → ``statuses[]`` (columnas) → ``workItems[]``.
    """
    if not isinstance(kanban, list):
        return
    for branch in kanban:
        if not isinstance(branch, dict):
            continue
        for status in branch.get("statuses", []):
            if not isinstance(status, dict):
                continue
            for wi in status.get("workItems", []):
                if isinstance(wi, dict):
                    yield wi
