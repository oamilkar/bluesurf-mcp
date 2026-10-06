"""Modelos tipados de las entidades de BlueSurf.

Los campos reflejan la forma real observada en la API (work items y usuario
actual). Cada modelo conserva ``raw`` con el payload original para no perder
información que aún no se modela explícitamente.

En BlueSurf un "ticket" es un *work item*: sus campos de asignado/reportado vienen
planos (``assignedToId``, ``assignedToFullName``, …); aquí se agrupan en objetos
:class:`User` por comodidad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class User:
    """Un usuario de BlueSurf (asignado, reportado, autor)."""

    id: str
    blue_tag: str | None = None
    full_name: str | None = None
    email: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_current_user(cls, data: dict[str, Any]) -> "User":
        """Construye desde ``GET /api/instance/currentUser``."""
        return cls(
            id=str(data.get("id", "")),
            blue_tag=data.get("blueTag"),
            full_name=data.get("fullName"),
            email=data.get("email"),
            raw=data,
        )


@dataclass(slots=True)
class Comment:
    """Un comentario embebido en un work item."""

    id: str
    author: str | None = None
    body: str | None = None
    created_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Comment":
        return cls(
            id=str(data.get("id", "")),
            author=data.get("createdByFullName") or data.get("createdByBlueTag"),
            body=data.get("comment") or data.get("body") or data.get("text"),
            created_at=data.get("createdAt") or data.get("createdDateTime"),
            raw=data,
        )


@dataclass(slots=True)
class Attachment:
    """Un archivo de la sección Files de un work item."""

    id: str
    work_item_id: str
    name: str | None = None
    is_image: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Attachment":
        return cls(
            id=str(data.get("id", "")),
            work_item_id=str(data.get("workItemId", "")),
            name=data.get("name"),
            is_image=bool(data.get("isImage", False)),
            raw=data,
        )


@dataclass(slots=True)
class DownloadedFile:
    """Bytes de un adjunto ya descargado, y la ruta si se escribió a disco."""

    id: str
    name: str
    content_type: str | None
    content: bytes
    path: str | None = None


@dataclass(slots=True)
class Ticket:
    """Un work item (ticket) de BlueSurf."""

    id: str
    code: str | None = None
    name: str | None = None
    description: str | None = None
    type_name: str | None = None
    status_name: str | None = None
    status_is_final: bool = False
    priority_name: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    current_sprint_name: str | None = None
    assignee: User | None = None
    reporter: User | None = None
    estimated_effort: float | None = None
    total_hours: float | None = None
    created_at: str | None = None
    initiated_at: str | None = None
    finished_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Ticket":
        return cls(
            id=str(data.get("id", "")),
            code=data.get("code"),
            name=data.get("name"),
            description=data.get("description"),
            type_name=data.get("typeDisplayName") or data.get("typeName"),
            status_name=data.get("statusName"),
            status_is_final=bool(data.get("statusIsFinal", False)),
            priority_name=data.get("priorityDisplayName") or data.get("priorityName"),
            project_id=data.get("projectId"),
            project_name=data.get("projectName"),
            current_sprint_name=data.get("currentSprintName"),
            assignee=_user_from_prefixed(data, "assignedTo"),
            reporter=_user_from_prefixed(data, "reportedBy"),
            estimated_effort=data.get("estimatedEffort"),
            total_hours=data.get("totalHours"),
            created_at=data.get("createdAt"),
            initiated_at=data.get("initiatedAt"),
            finished_at=data.get("finishedAt"),
            raw=data,
        )

    @property
    def comments(self) -> list[Comment]:
        """Comentarios embebidos (el detalle del work item los trae inline)."""
        return [
            Comment.from_json(c)
            for c in self.raw.get("comments", [])
            if isinstance(c, dict)
        ]


def _user_from_prefixed(data: dict[str, Any], prefix: str) -> User | None:
    """Arma un :class:`User` desde campos planos tipo ``assignedToId`` etc."""
    user_id = data.get(f"{prefix}Id")
    if not user_id:
        return None
    return User(
        id=str(user_id),
        blue_tag=data.get(f"{prefix}BlueTag"),
        full_name=data.get(f"{prefix}FullName"),
        email=data.get(f"{prefix}Email"),
    )
