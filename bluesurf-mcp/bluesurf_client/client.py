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

from typing import Any

from bluesurf_client.auth.base import AuthProvider
from bluesurf_client.constants import DEFAULT_BASE_URL, IDENTITY_COOKIE
from bluesurf_client.models import Ticket, User
from bluesurf_client.session import BlueSurfSession

_PATH_CURRENT_USER = "/api/instance/currentUser"
_PATH_MY_PROJECTS = "/api/user/current/project"
_PATH_KANBAN = "/api/project/{project}/kanban"
_PATH_WORKITEM = "/api/workItem/{code}"

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
