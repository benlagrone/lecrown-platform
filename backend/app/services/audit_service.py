from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.backoffice import AuditEvent
from app.models.user import User
from app.utils.helpers import new_uuid


def record(
    db: Session,
    *,
    actor: User | None,
    action: str,
    resource_type: str,
    resource_id: str,
    brokerage_id: str | None = None,
    previous_state: str | None = None,
    next_state: str | None = None,
    reason: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=new_uuid(),
        brokerage_id=brokerage_id,
        actor_user_id=actor.id if actor else None,
        actor_type="user" if actor else "system",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        previous_state=previous_state,
        next_state=next_state,
        reason=reason,
        request_id=request_id,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event
