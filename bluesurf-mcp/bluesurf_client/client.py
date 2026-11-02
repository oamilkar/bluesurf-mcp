"""Cliente de BlueSurf (la fachada de alto nivel).

Expone las lecturas centradas en el objetivo: los tickets (work items) asignados
al usuario. En BlueSurf no hay un endpoint "asignados a mí"; se resuelve consultando
el kanban de un proyecto con el filtro ``assignedTo`` puesto en el id del usuario
actual. También adjunta un archivo, publica un comentario y registra tiempo
en el daily report.

Ciclo de vida:
- Construcción sin efectos: ``BlueSurfClient(base_url=...)``.
- Autenticación explícita: ``await client.login(auth)`` (inyección por método).
- Limpieza: ``await client.aclose()``, o usa ``async with`` que la hace sola.
"""

from __future__ import annotations

import copy
import html
import json
import mimetypes
from datetime import date
from pathlib import Path
from typing import Any

from bluesurf_client.auth.base import AuthProvider
from bluesurf_client.constants import DEFAULT_BASE_URL, IDENTITY_COOKIE
from bluesurf_client.models import (
    Attachment,
    CategoriaReporte,
    Comment,
    DownloadedFile,
    ProyectoReporte,
    ReporteDiario,
    Ticket,
    User,
)
from bluesurf_client.session import BlueSurfSession

_PATH_CURRENT_USER = "/api/instance/currentUser"
_PATH_MY_PROJECTS = "/api/user/current/project"
_PATH_KANBAN = "/api/project/{project}/kanban"
_PATH_WORKITEM = "/api/workItem/{code}"
_PATH_FILE_NAME = "/api/workItem/{work_item_id}/fileName/{file_id}"
_PATH_FILE = "/api/workItem/{work_item_id}/file/{file_id}"
_PATH_IMAGE = "/api/workItem/{work_item_id}/image/{file_id}"
_PATH_UPLOAD = "/api/workItem/{work_item_id}/file"
_PATH_COMMENT = "/api/WorkItem/{work_item_id}/comment"
_PATH_PROJECTS = "/api/project"
_PATH_SUBCATEGORIES = "/api/user/current/subcategory"
_PATH_DAILY_REPORT = "/api/effort/myDailyReport/{fecha}"
_PATH_SAVE_DAILY_REPORT = "/api/Effort/DailyReport"

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
    """Fachada sobre la API de BlueSurf."""

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

    async def adjuntar_archivo(self, code: str, ruta: Path | str) -> Attachment:
        """Sube un archivo local a la sección Files del ticket.

        El POST va al id del work item, no al código. Devuelve el archivo nuevo
        que apareció en la respuesta.
        """
        origen = Path(ruta)
        if not origen.is_file():
            raise FileNotFoundError(f"No existe el archivo {origen}")
        ticket = await self.obtener_ticket(code)
        if not ticket.id:
            raise LookupError(f"El ticket {code} no tiene id")
        previos = _ids_de_archivos(ticket)
        nombre = _nombre_seguro(origen.name, origen.name)
        contenido = origen.read_bytes()
        tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"

        data = await self._session.post_multipart(
            _PATH_UPLOAD.format(work_item_id=ticket.id),
            files=lambda: {"file": (nombre, contenido, tipo)},
        )
        return _adjunto_nuevo(data, previos, nombre, ticket.id)

    async def agregar_comentario(self, code: str, texto: str) -> Comment:
        """Publica un comentario. El texto se escapa y se envuelve en ``<p>``.

        El campo multipart ``comment`` lleva el JSON ``{"comment": "<p>…</p>"}``.
        """
        limpio = texto.strip()
        if not limpio:
            raise ValueError("El comentario está vacío")
        ticket = await self.obtener_ticket(code)
        if not ticket.id:
            raise LookupError(f"El ticket {code} no tiene id")
        previos = {item.id for item in ticket.comments if item.id}
        payload = json.dumps(
            {"comment": f"<p>{html.escape(limpio)}</p>"},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        data = await self._session.post_multipart(
            _PATH_COMMENT.format(work_item_id=ticket.id),
            files=lambda: {"comment": (None, payload)},
        )
        return _comentario_nuevo(data, previos)

    async def proyectos_reporte(self) -> list[ProyectoReporte]:
        """Proyectos activos para registrar tiempo, con sus categorías."""
        data = await self._session.get_json(
            _PATH_PROJECTS, params={"includeCategories": "true"}
        )
        if not isinstance(data, list):
            return []
        return [
            ProyectoReporte.from_json(item)
            for item in data
            if isinstance(item, dict) and item.get("status") == 1
        ]

    async def listar_categorias(
        self, proyecto: str | None = None
    ) -> list[CategoriaReporte]:
        """Subcategorías del usuario.

        Con ``proyecto`` (smallCode) solo las de ese proyecto. ``registrar_tiempo``
        resuelve el nombre contra el catálogo completo.
        """
        catalogo = await self._catalogo_categorias()
        codigo = _texto_opcional(proyecto)
        if not codigo:
            return catalogo
        project = _buscar_proyecto(await self.proyectos_reporte(), codigo)
        permitidas = set(project.category_ids)
        return [
            categoria
            for categoria in catalogo
            if categoria.category_id is not None and categoria.category_id in permitidas
        ]

    async def mi_reporte_diario(self, fecha: str) -> ReporteDiario:
        """Daily report de un día. ``cerrado`` es true cuando ``status`` es 2."""
        dia = _exigir_fecha(fecha)
        data = await self._session.get_json(_PATH_DAILY_REPORT.format(fecha=dia))
        if not isinstance(data, dict):
            raise ValueError(f"El reporte del {dia} no es un objeto")
        return ReporteDiario.from_json(data, dia)

    async def registrar_tiempo(
        self,
        fecha: str,
        lineas: list[dict[str, Any]],
        confirmar: bool = False,
    ) -> ReporteDiario:
        """Agrega una o más líneas al daily report y reenvía el día en un solo POST.

        Si el día ya está cerrado, o alguna línea es inválida, no escribe.
        Cada línea lleva horas, categoria y, si aplica, descripcion, proyecto,
        ticket y pendiente. Sin ticket la descripción es obligatoria.
        """
        dia = _exigir_fecha(fecha)
        if not lineas:
            raise ValueError("Hay que indicar al menos una línea")
        preparadas = [_preparar_linea(linea, indice) for indice, linea in enumerate(lineas)]

        reporte = await self.mi_reporte_diario(dia)
        if reporte.cerrado:
            raise ValueError(f"El reporte del {dia} ya está cerrado")

        catalogo = await self._catalogo_categorias()
        proyectos = (
            await self.proyectos_reporte()
            if any(linea["proyecto"] for linea in preparadas)
            else None
        )
        resueltas: list[dict[str, Any]] = []
        for indice, linea in enumerate(preparadas):
            try:
                resueltas.append(await self._resolver_linea(linea, catalogo, proyectos))
            except Exception as error:
                raise _error_de_linea(indice, error) from None

        body = copy.deepcopy(reporte.raw)
        body["status"] = 2 if confirmar else 0
        previos = body.get("efforts")
        body["efforts"] = [
            *(previos if isinstance(previos, list) else []),
            *resueltas,
        ]
        await self._session.post_json(_PATH_SAVE_DAILY_REPORT, body)
        return await self.mi_reporte_diario(dia)

    async def _resolver_linea(
        self,
        linea: dict[str, Any],
        catalogo: list[CategoriaReporte],
        proyectos: list[ProyectoReporte] | None,
    ) -> dict[str, Any]:
        categoria = str(linea["categoria"])
        elegida = _resolver_categoria(catalogo, categoria)
        if not elegida.category_id:
            raise ValueError(f'La categoría "{categoria}" no tiene categoryId')

        project_id: str | None = None
        codigo_proyecto = linea["proyecto"]
        if codigo_proyecto:
            project = _buscar_proyecto(proyectos or [], str(codigo_proyecto))
            if not project.id:
                raise LookupError(f"El proyecto {codigo_proyecto} no tiene id")
            project_id = project.id

        work_item_id: str | None = None
        codigo_ticket = linea["ticket"]
        if codigo_ticket:
            item = await self.obtener_ticket(str(codigo_ticket))
            if not item.id:
                raise LookupError(f"El ticket {codigo_ticket} no tiene id")
            if not item.project_id:
                raise ValueError(
                    f"El ticket {codigo_ticket} no tiene proyecto; "
                    "no se puede registrar tiempo ligado"
                )
            if project_id and project_id != item.project_id:
                raise ValueError(
                    f"El ticket {codigo_ticket} pertenece a otro proyecto, "
                    f"no a {codigo_proyecto}"
                )
            project_id = item.project_id
            work_item_id = item.id

        return {
            "projectId": project_id,
            "taskId": None,
            "workItemId": work_item_id,
            "description": linea["descripcion"],
            "executed": linea["executed"],
            "pending": linea["pending"],
            "categoryId": elegida.category_id,
            "subcategoryId": elegida.id,
            "deleted": False,
        }

    async def _catalogo_categorias(self) -> list[CategoriaReporte]:
        data = await self._session.get_json(_PATH_SUBCATEGORIES)
        if not isinstance(data, list):
            return []
        return [
            CategoriaReporte.from_json(item) for item in data if isinstance(item, dict)
        ]

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


def _ids_de_archivos(ticket: Ticket) -> set[str]:
    ids: set[str] = set()
    for raw in ticket.raw.get("files") or []:
        if isinstance(raw, dict) and raw.get("id"):
            ids.add(str(raw["id"]))
    return ids


def _adjunto_nuevo(
    data: Any, previos: set[str], nombre: str, work_item_id: str
) -> Attachment:
    ticket = _ticket_de_respuesta(data)
    nuevos: list[Attachment] = []
    for raw in ticket.raw.get("files") or []:
        if not isinstance(raw, dict):
            continue
        adjunto = Attachment.from_json(raw)
        if not adjunto.id or adjunto.id in previos:
            continue
        if not adjunto.name:
            adjunto.name = nombre
        if not adjunto.work_item_id:
            adjunto.work_item_id = work_item_id
        nuevos.append(adjunto)
    if not nuevos:
        raise LookupError("BlueSurf no devolvió el archivo nuevo")
    return nuevos[-1]


def _comentario_nuevo(data: Any, previos: set[str]) -> Comment:
    ticket = _ticket_de_respuesta(data)
    nuevos = [item for item in ticket.comments if item.id and item.id not in previos]
    if not nuevos:
        raise LookupError("BlueSurf no devolvió el comentario nuevo")
    return nuevos[-1]


def _ticket_de_respuesta(data: Any) -> Ticket:
    if not isinstance(data, dict):
        raise LookupError("BlueSurf no devolvió el work item")
    return Ticket.from_json(data)


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


def _preparar_linea(linea: dict[str, Any], indice: int) -> dict[str, Any]:
    try:
        if not isinstance(linea, dict):
            raise ValueError("La línea debe ser un objeto")
        executed = _horas_validas(linea.get("horas"), "Las horas")
        descripcion = _texto_opcional(linea.get("descripcion"))
        proyecto = _texto_opcional(linea.get("proyecto"))
        ticket = _texto_opcional(linea.get("ticket"))
        if not ticket and not descripcion:
            raise ValueError(
                "La descripción es obligatoria cuando el tiempo no está ligado a un ticket"
            )
        pendiente = linea.get("pendiente")
        if not ticket and pendiente is not None:
            raise ValueError("pendiente solo aplica cuando hay un ticket")
        pending = (
            0
            if ticket and pendiente is None
            else _horas_validas(pendiente, "Las horas pendientes")
            if ticket
            else None
        )
        categoria = linea.get("categoria")
        if not isinstance(categoria, str) or not categoria.strip():
            raise ValueError("La categoría es obligatoria")
        return {
            "executed": executed,
            "descripcion": descripcion,
            "proyecto": proyecto,
            "ticket": ticket,
            "pending": pending,
            "categoria": categoria.strip(),
        }
    except Exception as error:
        raise _error_de_linea(indice, error) from None


def _error_de_linea(indice: int, error: Exception) -> Exception:
    if isinstance(error, LookupError):
        return LookupError(f"Línea {indice + 1}: {error}")
    return ValueError(f"Línea {indice + 1}: {error}")


def _texto_opcional(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    limpio = value.strip()
    return limpio or None


def _exigir_fecha(fecha: str) -> str:
    dia = fecha.strip()
    try:
        date.fromisoformat(dia)
    except ValueError:
        raise ValueError("La fecha debe ser YYYY-MM-DD") from None
    return dia


def _horas_validas(horas: float, etiqueta: str) -> float:
    if isinstance(horas, bool) or not isinstance(horas, (int, float)):
        raise ValueError(f"{etiqueta} deben ser un número mayor o igual a 0")
    if horas < 0 or horas != horas or horas in (float("inf"), float("-inf")):
        raise ValueError(f"{etiqueta} deben ser un número mayor o igual a 0")
    return round(float(horas), 3)


def _igual_texto(left: str | None, right: str) -> bool:
    return (left or "").strip().lower() == right.strip().lower()


def _buscar_proyecto(proyectos: list[ProyectoReporte], small_code: str) -> ProyectoReporte:
    found = [project for project in proyectos if _igual_texto(project.small_code, small_code)]
    if len(found) == 1:
        return found[0]
    if not found:
        codes = [project.small_code for project in proyectos if project.small_code]
        activos = ", ".join(codes) or "ninguno"
        raise LookupError(
            f'No hay un proyecto activo con smallCode "{small_code}". Activos: {activos}.'
        )
    raise LookupError(f'Hay varios proyectos con smallCode "{small_code}".')


def _resolver_categoria(catalogo: list[CategoriaReporte], texto: str) -> CategoriaReporte:
    raw = texto.strip()
    if not raw:
        raise ValueError("La categoría es obligatoria")
    category_name: str | None = None
    name = raw
    if ":" in raw:
        category_name, _, name = raw.partition(":")
        category_name = category_name.strip()
        name = name.strip()
        if not category_name or not name:
            raise ValueError(f'La categoría "{texto}" debe ser "Categoria: Nombre"')
    matches = [
        categoria
        for categoria in catalogo
        if _igual_texto(categoria.name, name)
        and (category_name is None or _igual_texto(categoria.category_name, category_name))
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise LookupError(f'No existe la categoría "{texto}"')
    opciones = ", ".join(
        f"{categoria.category_name}: {categoria.name}" for categoria in matches
    )
    raise ValueError(f'La categoría "{texto}" es ambigua. Indica una de: {opciones}.')
