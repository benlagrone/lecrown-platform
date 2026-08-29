from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.backoffice import RoleAssignment
from app.models.user import User


ROLE_PERMISSIONS = {
    "designated_broker": {"*"},
    "delegated_supervisor": {
        "agents.assign",
        "representations.create",
        "representations.approve",
        "transactions.create",
        "transactions.review",
        "documents.prepare",
    },
    "transaction_coordinator": {
        "representations.create",
        "transactions.create",
        "documents.prepare",
    },
    "agent": {
        "representations.create",
        "transactions.create",
        "documents.prepare",
    },
    "compliance_reviewer": {"transactions.review", "documents.download_sensitive"},
    "finance_user": {"commissions.prepare", "reports.export"},
    "read_only_auditor": {"envelopes.audit", "reports.export"},
}


def active_roles(db: Session, *, user: User, brokerage_id: str) -> set[str]:
    if user.is_admin:
        return {"platform_administrator"}
    now = datetime.now(timezone.utc)
    assignments = db.scalars(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.brokerage_id == brokerage_id,
            RoleAssignment.revoked_at.is_(None),
            or_(RoleAssignment.starts_at.is_(None), RoleAssignment.starts_at <= now),
            or_(RoleAssignment.ends_at.is_(None), RoleAssignment.ends_at > now),
        )
    ).all()
    return {assignment.role for assignment in assignments}


def has_permission(db: Session, *, user: User, brokerage_id: str, permission: str) -> bool:
    if user.is_admin:
        return True
    for role in active_roles(db, user=user, brokerage_id=brokerage_id):
        permissions = ROLE_PERMISSIONS.get(role, set())
        if "*" in permissions or permission in permissions:
            return True
    return False


def require_permission(db: Session, *, user: User, brokerage_id: str, permission: str) -> None:
    if not has_permission(db, user=user, brokerage_id=brokerage_id, permission=permission):
        raise PermissionError(f"Permission required: {permission}")
