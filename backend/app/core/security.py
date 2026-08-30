from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services import auth_service

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user: User, *, auth_source: str = "password") -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "auth_source": auth_source,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_privileged_token(user: User) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.privileged_auth_expire_minutes
    )
    payload = {
        "sub": user.id,
        "purpose": "privileged_action",
        "auth_time": datetime.now(timezone.utc).timestamp(),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def authenticate_access_token(db: Session, token: str) -> User:
    payload = decode_access_token(token)
    auth_service.ensure_bootstrap_admin_user(db)

    subject = str(payload.get("sub") or "").strip()
    user = db.get(User, subject)
    if user is None and subject:
        user = db.query(User).filter(User.username == subject).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if settings.workspace_auth_required:
        email_domain = user.email.strip().casefold().rpartition("@")[2]
        if (
            payload.get("auth_source") != "google_workspace"
            or not (user.google_subject or "").strip()
            or email_domain not in settings.workspace_allowed_domains
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google Workspace sign-in required",
            )
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    return authenticate_access_token(db, token)


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_privileged_token(
    current_user: User = Depends(get_current_user),
    x_privileged_token: Optional[str] = Header(default=None),
) -> User:
    if not x_privileged_token:
        raise HTTPException(status_code=401, detail="Recent authentication required")
    payload = decode_access_token(x_privileged_token)
    if payload.get("purpose") != "privileged_action" or payload.get("sub") != current_user.id:
        raise HTTPException(status_code=401, detail="Invalid privileged token")
    return current_user


def require_intake_key(x_intake_key: Optional[str] = Header(default=None)) -> None:
    if not settings.intake_api_key:
        return
    if x_intake_key != settings.intake_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid intake key",
        )
