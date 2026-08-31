from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.backoffice import Document, DocumentVersion, Representation, Transaction
from app.models.client_portal import ClientPortalGrant
from app.models.user import User
from app.services import audit_service
from app.services.keycloak_auth_service import KeycloakIdentity
from app.utils.helpers import new_uuid

settings = get_settings()
CLIENT_SHAREABLE_CLASSIFICATION = "client_shareable"


def create_grant(
    db: Session,
    *,
    actor: User,
    representation_id: str,
    email: str,
) -> ClientPortalGrant:
    representation = db.get(Representation, representation_id)
    if representation is None:
        raise LookupError("Representation not found")
    normalized_email = email.strip().casefold()
    if "@" not in normalized_email:
        raise ValueError("A valid client email is required")

    existing = db.scalars(
        select(ClientPortalGrant).where(
            ClientPortalGrant.keycloak_issuer == settings.keycloak_issuer,
            ClientPortalGrant.email == normalized_email,
            ClientPortalGrant.representation_id == representation_id,
        )
    ).first()
    if existing is not None:
        if existing.status == "active":
            return existing
        existing.status = "active"
        existing.revoked_at = None
        existing.revoked_by_user_id = None
        grant = existing
    else:
        grant = ClientPortalGrant(
            id=new_uuid(),
            brokerage_id=representation.brokerage_id,
            representation_id=representation.id,
            email=normalized_email,
            keycloak_issuer=settings.keycloak_issuer,
            created_by_user_id=actor.id,
            status="active",
        )
        db.add(grant)

    audit_service.record(
        db,
        actor=actor,
        action="client_portal.grant_created",
        resource_type="client_portal_grant",
        resource_id=grant.id,
        brokerage_id=representation.brokerage_id,
        next_state="active",
        metadata={"representation_id": representation.id, "email": normalized_email},
    )
    db.commit()
    db.refresh(grant)
    return grant


def revoke_grant(db: Session, *, actor: User, grant_id: str) -> ClientPortalGrant:
    grant = db.get(ClientPortalGrant, grant_id)
    if grant is None:
        raise LookupError("Client portal grant not found")
    if grant.status != "revoked":
        grant.status = "revoked"
        grant.revoked_at = datetime.now(timezone.utc)
        grant.revoked_by_user_id = actor.id
        audit_service.record(
            db,
            actor=actor,
            action="client_portal.grant_revoked",
            resource_type="client_portal_grant",
            resource_id=grant.id,
            brokerage_id=grant.brokerage_id,
            previous_state="active",
            next_state="revoked",
            metadata={"representation_id": grant.representation_id},
        )
        db.commit()
        db.refresh(grant)
    return grant


def resolve_active_grants(db: Session, identity: KeycloakIdentity) -> list[ClientPortalGrant]:
    grants = list(
        db.scalars(
            select(ClientPortalGrant).where(
                ClientPortalGrant.keycloak_issuer == identity.issuer,
                ClientPortalGrant.status == "active",
                (ClientPortalGrant.keycloak_subject == identity.subject)
                | (
                    (ClientPortalGrant.keycloak_subject.is_(None))
                    & (ClientPortalGrant.email == identity.email)
                ),
            )
        )
    )
    if not grants:
        raise PermissionError("No active LeCrown client engagement is assigned to this account")

    now = datetime.now(timezone.utc)
    for grant in grants:
        if grant.keycloak_subject is None:
            result = db.execute(
                update(ClientPortalGrant)
                .where(
                    ClientPortalGrant.id == grant.id,
                    ClientPortalGrant.keycloak_subject.is_(None),
                    ClientPortalGrant.status == "active",
                )
                .values(keycloak_subject=identity.subject)
            )
            if result.rowcount != 1:
                db.refresh(grant)
                if grant.keycloak_subject != identity.subject:
                    db.rollback()
                    raise PermissionError("Client portal identity was assigned to another account")
            grant.keycloak_subject = identity.subject
        elif grant.keycloak_subject != identity.subject:
            raise PermissionError("Client portal identity does not match the assigned account")
        grant.last_authenticated_at = now
        db.add(grant)
    db.commit()
    return grants


def representation_records(
    db: Session,
    grants: list[ClientPortalGrant],
) -> tuple[list[Representation], list[Transaction], list[tuple[Document, DocumentVersion]]]:
    representation_ids = {grant.representation_id for grant in grants}
    representations = list(
        db.scalars(select(Representation).where(Representation.id.in_(representation_ids)))
    )
    transactions = list(
        db.scalars(select(Transaction).where(Transaction.representation_id.in_(representation_ids)))
    )
    transaction_ids = {transaction.id for transaction in transactions}
    if not transaction_ids:
        return representations, transactions, []

    documents = list(
        db.scalars(
            select(Document).where(
                Document.transaction_id.in_(transaction_ids),
                Document.classification == CLIENT_SHAREABLE_CLASSIFICATION,
            )
        )
    )
    visible_versions: list[tuple[Document, DocumentVersion]] = []
    for document in documents:
        version = db.scalars(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.scan_status == "clean",
                DocumentVersion.render_status == "complete",
            )
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        ).first()
        if version is not None:
            visible_versions.append((document, version))
    return representations, transactions, visible_versions
