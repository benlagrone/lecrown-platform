from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.user import User
from app.schemas.client_portal import (
    ClientDocumentRead,
    ClientPortalConfigRead,
    ClientPortalGrantCreate,
    ClientPortalGrantRead,
    ClientPortalIdentityRead,
    ClientPortalSessionRead,
    ClientRepresentationRead,
    ClientTransactionRead,
)
from app.services import client_portal_service, keycloak_auth_service
from app.services.keycloak_auth_service import KeycloakIdentity

router = APIRouter()
settings = get_settings()
bearer = HTTPBearer(auto_error=False)


def get_client_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> KeycloakIdentity:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(status_code=401, detail="Keycloak sign-in required")
    try:
        return keycloak_auth_service.verify_access_token(credentials.credentials)
    except keycloak_auth_service.KeycloakAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/config", response_model=ClientPortalConfigRead)
def portal_config() -> ClientPortalConfigRead:
    return ClientPortalConfigRead(
        ready=keycloak_auth_service.is_ready(),
        keycloak_url=settings.keycloak_base_url,
        realm=settings.keycloak_realm,
        client_id=settings.keycloak_client_id or None,
        required_roles=settings.keycloak_allowed_roles,
    )


@router.get("/session", response_model=ClientPortalSessionRead)
def portal_session(
    db: Session = Depends(get_db),
    identity: KeycloakIdentity = Depends(get_client_identity),
) -> ClientPortalSessionRead:
    try:
        grants = client_portal_service.resolve_active_grants(db, identity)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    representations, transactions, document_versions = client_portal_service.representation_records(db, grants)
    return ClientPortalSessionRead(
        identity=ClientPortalIdentityRead(
            subject=identity.subject,
            email=identity.email,
            name=identity.name,
        ),
        representations=[ClientRepresentationRead.model_validate(item) for item in representations],
        transactions=[ClientTransactionRead.model_validate(item) for item in transactions],
        documents=[
            ClientDocumentRead(
                id=document.id,
                transaction_id=document.transaction_id or "",
                name=document.name,
                version=version.version_number,
                media_type=version.media_type,
                size_bytes=version.size_bytes,
                created_at=version.created_at,
            )
            for document, version in document_versions
            if document.transaction_id
        ],
    )


@router.post("/admin/grants", response_model=ClientPortalGrantRead)
def create_portal_grant(
    payload: ClientPortalGrantCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> ClientPortalGrantRead:
    try:
        grant = client_portal_service.create_grant(
            db,
            actor=current_admin,
            representation_id=payload.representation_id,
            email=payload.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ClientPortalGrantRead.model_validate(grant)


@router.post("/admin/grants/{grant_id}/revoke", response_model=ClientPortalGrantRead)
def revoke_portal_grant(
    grant_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> ClientPortalGrantRead:
    try:
        grant = client_portal_service.revoke_grant(db, actor=current_admin, grant_id=grant_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ClientPortalGrantRead.model_validate(grant)
