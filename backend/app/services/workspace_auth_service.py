from __future__ import annotations

import secrets
from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.user import User
from app.services import auth_service
from app.utils.helpers import new_uuid

settings = get_settings()


class WorkspaceAuthError(ValueError):
    pass


@dataclass(frozen=True)
class WorkspaceIdentity:
    subject: str
    email: str
    hosted_domain: str
    display_name: str | None = None


def is_ready() -> bool:
    return bool(
        settings.google_login_client_id.strip()
        and settings.workspace_allowed_domains
    )


def verify_google_credential(credential: str, *, nonce: str | None = None) -> WorkspaceIdentity:
    client_id = settings.google_login_client_id.strip()
    if not client_id or not settings.workspace_allowed_domains:
        raise WorkspaceAuthError("Google Workspace sign-in is not configured")

    try:
        claims = id_token.verify_oauth2_token(
            credential.strip(),
            google_requests.Request(),
            client_id,
        )
    except (ValueError, TypeError) as exc:
        raise WorkspaceAuthError("Google identity could not be verified") from exc

    subject = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip().casefold()
    hosted_domain = str(claims.get("hd") or "").strip().casefold()
    email_verified = claims.get("email_verified") is True
    expected_nonce = (nonce or "").strip()
    token_nonce = str(claims.get("nonce") or "").strip()

    if not subject or not email or not email_verified:
        raise WorkspaceAuthError("A verified Google Workspace email is required")
    if hosted_domain not in settings.workspace_allowed_domains:
        raise WorkspaceAuthError("Use a LeCrown Properties Workspace account")
    if email.rpartition("@")[2] != hosted_domain:
        raise WorkspaceAuthError("Google Workspace domain and email do not match")
    if expected_nonce and token_nonce != expected_nonce:
        raise WorkspaceAuthError("Google sign-in nonce did not match")

    display_name = str(claims.get("name") or "").strip() or None
    return WorkspaceIdentity(
        subject=subject,
        email=email,
        hosted_domain=hosted_domain,
        display_name=display_name,
    )


def authenticate_workspace_user(
    db: Session,
    *,
    credential: str,
    nonce: str | None = None,
) -> User:
    identity = verify_google_credential(credential, nonce=nonce)
    user = db.scalars(select(User).where(User.google_subject == identity.subject)).first()

    if user is None:
        user = db.scalars(select(User).where(func.lower(User.email) == identity.email)).first()
        if user is not None:
            conflicting_subject = (user.google_subject or "").strip()
            if conflicting_subject and conflicting_subject != identity.subject:
                raise WorkspaceAuthError("This Workspace email is linked to another Google identity")
            user.google_subject = identity.subject

    if user is None:
        username = _available_username(db, identity.email, identity.subject)
        user = User(
            id=new_uuid(),
            username=username,
            email=identity.email,
            google_subject=identity.subject,
            hashed_password=auth_service.hash_password(secrets.token_urlsafe(32)),
            is_active=True,
            is_admin=identity.email in settings.workspace_admin_emails,
        )
        db.add(user)
    else:
        user.email = identity.email
        if identity.email in settings.workspace_admin_emails:
            user.is_admin = True
        db.add(user)

    db.commit()
    db.refresh(user)
    if not user.is_active:
        raise WorkspaceAuthError("This LeCrown account is inactive")
    return user


def _available_username(db: Session, email: str, subject: str) -> str:
    base = email.partition("@")[0].strip().casefold() or "workspace-user"
    candidate = base
    suffix = subject[-8:].casefold()
    if db.scalars(select(User).where(func.lower(User.username) == candidate)).first() is not None:
        candidate = f"{base}-{suffix}"
    return candidate
