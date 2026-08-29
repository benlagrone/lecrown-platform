from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.backoffice import AgentProfile, Brokerage, Representation, RoleAssignment, Transaction
from app.models.user import User
from app.services import audit_service, authorization_service
from app.utils.helpers import new_uuid


def create_brokerage(
    db: Session,
    *,
    actor: User,
    legal_name: str,
    license_number: str | None,
    designated_broker_user_id: str | None,
) -> Brokerage:
    if not actor.is_admin:
        raise PermissionError("Platform administrator access required")
    brokerage = Brokerage(
        id=new_uuid(),
        legal_name=legal_name.strip(),
        license_number=(license_number or "").strip() or None,
        designated_broker_user_id=designated_broker_user_id,
        policy_version="draft",
    )
    if not brokerage.legal_name:
        raise ValueError("Brokerage legal name is required")
    if designated_broker_user_id and db.get(User, designated_broker_user_id) is None:
        raise LookupError("Designated broker user not found")
    db.add(brokerage)
    if designated_broker_user_id:
        db.add(
            RoleAssignment(
                id=new_uuid(),
                brokerage_id=brokerage.id,
                user_id=designated_broker_user_id,
                role="designated_broker",
                granted_by_user_id=actor.id,
                starts_at=datetime.now(timezone.utc),
            )
        )
    audit_service.record(
        db,
        actor=actor,
        action="brokerage.created",
        resource_type="brokerage",
        resource_id=brokerage.id,
        brokerage_id=brokerage.id,
        next_state="active",
    )
    db.commit()
    db.refresh(brokerage)
    return brokerage


def grant_role(
    db: Session,
    *,
    actor: User,
    brokerage_id: str,
    user_id: str,
    role: str,
) -> RoleAssignment:
    if db.get(Brokerage, brokerage_id) is None:
        raise LookupError("Brokerage not found")
    authorization_service.require_permission(
        db, user=actor, brokerage_id=brokerage_id, permission="agents.assign"
    )
    if role not in authorization_service.ROLE_PERMISSIONS:
        raise ValueError("Unsupported brokerage role")
    if db.get(User, user_id) is None:
        raise LookupError("User not found")
    assignment = RoleAssignment(
        id=new_uuid(),
        brokerage_id=brokerage_id,
        user_id=user_id,
        role=role,
        granted_by_user_id=actor.id,
        starts_at=datetime.now(timezone.utc),
    )
    db.add(assignment)
    audit_service.record(
        db,
        actor=actor,
        action="role.granted",
        resource_type="role_assignment",
        resource_id=assignment.id,
        brokerage_id=brokerage_id,
        next_state="active",
        metadata={"user_id": user_id, "role": role},
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def create_agent_profile(
    db: Session,
    *,
    actor: User,
    brokerage_id: str,
    user_id: str,
    license_number: str | None,
) -> AgentProfile:
    if db.get(Brokerage, brokerage_id) is None:
        raise LookupError("Brokerage not found")
    authorization_service.require_permission(
        db, user=actor, brokerage_id=brokerage_id, permission="agents.assign"
    )
    if db.get(User, user_id) is None:
        raise LookupError("User not found")
    existing = db.scalars(
        select(AgentProfile).where(
            AgentProfile.brokerage_id == brokerage_id, AgentProfile.user_id == user_id
        )
    ).first()
    if existing:
        raise ValueError("Agent profile already exists")
    profile = AgentProfile(
        id=new_uuid(),
        brokerage_id=brokerage_id,
        user_id=user_id,
        license_number=(license_number or "").strip() or None,
        sponsorship_status="pending",
        authority_status="inactive",
    )
    db.add(profile)
    audit_service.record(
        db,
        actor=actor,
        action="agent_profile.created",
        resource_type="agent_profile",
        resource_id=profile.id,
        brokerage_id=brokerage_id,
        next_state="inactive",
    )
    db.commit()
    db.refresh(profile)
    return profile


def activate_agent_profile(
    db: Session,
    *,
    actor: User,
    brokerage_id: str,
    profile_id: str,
) -> AgentProfile:
    authorization_service.require_permission(
        db, user=actor, brokerage_id=brokerage_id, permission="agents.assign"
    )
    profile = db.get(AgentProfile, profile_id)
    if profile is None or profile.brokerage_id != brokerage_id:
        raise LookupError("Agent profile not found in brokerage")
    previous_state = profile.authority_status
    profile.sponsorship_status = "active"
    profile.authority_status = "active"
    profile.verified_at = datetime.now(timezone.utc)
    db.add(profile)
    audit_service.record(
        db,
        actor=actor,
        action="agent_profile.activated",
        resource_type="agent_profile",
        resource_id=profile.id,
        brokerage_id=brokerage_id,
        previous_state=previous_state,
        next_state="active",
    )
    db.commit()
    db.refresh(profile)
    return profile


def _require_active_agent(db: Session, *, brokerage_id: str, user_id: str) -> AgentProfile:
    profile = db.scalars(
        select(AgentProfile).where(
            AgentProfile.brokerage_id == brokerage_id,
            AgentProfile.user_id == user_id,
            AgentProfile.sponsorship_status == "active",
            AgentProfile.authority_status == "active",
        )
    ).first()
    if profile is None:
        raise ValueError("Responsible agent is not active in the brokerage")
    return profile


def create_representation(
    db: Session,
    *,
    actor: User,
    brokerage_id: str,
    client_name: str,
    representation_type: str,
    responsible_agent_user_id: str,
    client_crm_reference: str | None = None,
) -> Representation:
    authorization_service.require_permission(
        db, user=actor, brokerage_id=brokerage_id, permission="representations.create"
    )
    if representation_type not in {"buyer", "seller", "landlord", "tenant"}:
        raise ValueError("Unsupported representation type")
    _require_active_agent(
        db, brokerage_id=brokerage_id, user_id=responsible_agent_user_id
    )
    representation = Representation(
        id=new_uuid(),
        brokerage_id=brokerage_id,
        client_name=client_name.strip(),
        client_crm_reference=(client_crm_reference or "").strip() or None,
        representation_type=representation_type,
        responsible_agent_user_id=responsible_agent_user_id,
        status="draft",
    )
    if not representation.client_name:
        raise ValueError("Client name is required")
    db.add(representation)
    audit_service.record(
        db,
        actor=actor,
        action="representation.created",
        resource_type="representation",
        resource_id=representation.id,
        brokerage_id=brokerage_id,
        next_state="draft",
    )
    db.commit()
    db.refresh(representation)
    return representation


def create_transaction(
    db: Session,
    *,
    actor: User,
    brokerage_id: str,
    representation_id: str,
    transaction_type: str,
    responsible_agent_user_id: str,
    property_reference: str | None = None,
) -> Transaction:
    authorization_service.require_permission(
        db, user=actor, brokerage_id=brokerage_id, permission="transactions.create"
    )
    representation = db.get(Representation, representation_id)
    if representation is None or representation.brokerage_id != brokerage_id:
        raise LookupError("Representation not found in brokerage")
    if transaction_type not in {"purchase", "sale", "lease", "management"}:
        raise ValueError("Unsupported transaction type")
    _require_active_agent(
        db, brokerage_id=brokerage_id, user_id=responsible_agent_user_id
    )
    transaction = Transaction(
        id=new_uuid(),
        brokerage_id=brokerage_id,
        representation_id=representation_id,
        property_reference=(property_reference or "").strip() or None,
        transaction_type=transaction_type,
        responsible_agent_user_id=responsible_agent_user_id,
        status="draft",
    )
    db.add(transaction)
    audit_service.record(
        db,
        actor=actor,
        action="transaction.created",
        resource_type="transaction",
        resource_id=transaction.id,
        brokerage_id=brokerage_id,
        next_state="draft",
    )
    db.commit()
    db.refresh(transaction)
    return transaction
