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
class ProyectoReporte:
    """Proyecto activo que se puede usar al registrar tiempo."""

    id: str | None
    small_code: str | None = None
    code: str | None = None
    name: str | None = None
    category_ids: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ProyectoReporte":
        category_ids: list[str] = []
        for category in data.get("categories") or []:
            if isinstance(category, dict) and category.get("categoryId"):
                category_ids.append(str(category["categoryId"]))
        return cls(
            id=_str_or_none(data.get("id")),
            small_code=_str_or_none(data.get("smallCode")),
            code=_str_or_none(data.get("code")),
            name=_str_or_none(data.get("name")),
            category_ids=category_ids,
        )

    def publico(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "smallCode": self.small_code,
            "code": self.code,
            "name": self.name,
            "categoryIds": list(self.category_ids),
        }


@dataclass(slots=True)
class CategoriaReporte:
    """Subcategoría del usuario, con su categoría padre."""

    id: str
    name: str | None = None
    category_id: str | None = None
    category_name: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CategoriaReporte":
        return cls(
            id=str(data.get("id", "")),
            name=_str_or_none(data.get("name")),
            category_id=_str_or_none(data.get("categoryId")),
            category_name=_str_or_none(data.get("categoryName")),
        )

    def publico(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "categoryId": self.category_id,
            "categoryName": self.category_name,
        }


@dataclass(slots=True)
class EsfuerzoDiario:
    """Una línea de tiempo del daily report."""

    id: str | None = None
    description: str | None = None
    executed: float | None = None
    pending: float | None = None
    project_id: str | None = None
    work_item_id: str | None = None
    task_id: str | None = None
    category_id: str | None = None
    subcategory_id: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "EsfuerzoDiario":
        return cls(
            id=_str_or_none(data.get("id")),
            description=_str_or_none(data.get("description")),
            executed=_float_or_none(data.get("executed")),
            pending=_float_or_none(data.get("pending")),
            project_id=_str_or_none(data.get("projectId")),
            work_item_id=_str_or_none(data.get("workItemId")),
            task_id=_str_or_none(data.get("taskId")),
            category_id=_str_or_none(data.get("categoryId")),
            subcategory_id=_str_or_none(data.get("subcategoryId")),
        )

    def publico(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "executed": self.executed,
            "pending": self.pending,
            "projectId": self.project_id,
            "workItemId": self.work_item_id,
            "taskId": self.task_id,
            "categoryId": self.category_id,
            "subcategoryId": self.subcategory_id,
        }


@dataclass(slots=True)
class ReporteDiario:
    """Daily report de un día, más el documento crudo para reenviarlo."""

    id: str
    fecha: str
    status: int = 0
    cerrado: bool = False
    executed_hours: float = 0
    efforts: list[EsfuerzoDiario] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_json(cls, data: dict[str, Any], fecha: str) -> "ReporteDiario":
        date = data.get("date")
        fecha_real = str(date)[:10] if isinstance(date, str) and len(date) >= 10 else fecha
        status = data.get("status")
        status_num = int(status) if isinstance(status, (int, float)) else 0
        efforts = [
            EsfuerzoDiario.from_json(item)
            for item in data.get("efforts") or []
            if isinstance(item, dict)
        ]
        hours = data.get("executedHours")
        return cls(
            id=str(data.get("id", "")),
            fecha=fecha_real,
            status=status_num,
            cerrado=status_num == 2,
            executed_hours=float(hours) if isinstance(hours, (int, float)) else 0,
            efforts=efforts,
            raw=data,
        )

    def publico(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fecha": self.fecha,
            "status": self.status,
            "cerrado": self.cerrado,
            "executedHours": self.executed_hours,
            "efforts": [effort.publico() for effort in self.efforts],
        }


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


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _float_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


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
