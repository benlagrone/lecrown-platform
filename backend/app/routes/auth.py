from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, create_privileged_token, get_current_admin, get_current_user
from app.config import get_settings
from app.models.user import User
from app.services import auth_service, workspace_auth_service

router = APIRouter()
settings = get_settings()


class AuthUserRead(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserRead


class AuthConfigResponse(BaseModel):
    mode: str
    google_client_id: Optional[str] = None
    allowed_domains: list[str]
    ready: bool


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=32)
    nonce: Optional[str] = Field(default=None, min_length=8, max_length=512)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class PrivilegedAuthRequest(BaseModel):
    password: Optional[str] = Field(default=None, min_length=1)
    google_credential: Optional[str] = Field(default=None, min_length=32)
    nonce: Optional[str] = Field(default=None, min_length=8, max_length=512)


class PrivilegedAuthResponse(BaseModel):
    privileged_token: str
    token_type: str = "bearer"


class UserInviteCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class UserInviteAcceptRequest(BaseModel):
    invite_code: str = Field(min_length=8)
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=8)


class UserInviteRead(BaseModel):
    id: str
    email: str
    created_by_user_id: str
    accepted_by_user_id: Optional[str] = None
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserInviteCreateResponse(UserInviteRead):
    invite_code: str
    email_delivery_status: str
    email_delivery_detail: Optional[str] = None
    reissued_existing: bool = False


def _build_token_response(user: User, *, auth_source: str = "password") -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user, auth_source=auth_source),
        user=AuthUserRead.model_validate(user),
    )


def _require_legacy_auth_enabled() -> None:
    if settings.workspace_auth_required:
        raise HTTPException(status_code=403, detail="Google Workspace sign-in required")


@router.get("/config", response_model=AuthConfigResponse)
def auth_config() -> AuthConfigResponse:
    workspace_mode = settings.workspace_auth_required
    return AuthConfigResponse(
        mode="google_workspace" if workspace_mode else "password",
        google_client_id=(settings.google_login_client_id.strip() or None) if workspace_mode else None,
        allowed_domains=settings.workspace_allowed_domains if workspace_mode else [],
        ready=workspace_auth_service.is_ready() if workspace_mode else True,
    )


@router.post("/google", response_model=TokenResponse)
def google_login(
    payload: GoogleLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    if not settings.workspace_auth_required:
        raise HTTPException(status_code=404, detail="Google Workspace sign-in is not enabled")
    try:
        user = workspace_auth_service.authenticate_workspace_user(
            db,
            credential=payload.credential,
            nonce=payload.nonce,
        )
    except workspace_auth_service.WorkspaceAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _build_token_response(user, auth_source="google_workspace")


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    _require_legacy_auth_enabled()
    user = auth_service.authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _build_token_response(user)


@router.get("/me", response_model=AuthUserRead)
def me(current_user: User = Depends(get_current_user)) -> AuthUserRead:
    return AuthUserRead.model_validate(current_user)


@router.post("/privileged-auth", response_model=PrivilegedAuthResponse)
def privileged_auth(
    payload: PrivilegedAuthRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PrivilegedAuthResponse:
    if settings.workspace_auth_required:
        if not payload.google_credential:
            raise HTTPException(status_code=401, detail="Recent Google Workspace sign-in required")
        try:
            verified_user = workspace_auth_service.authenticate_workspace_user(
                db,
                credential=payload.google_credential,
                nonce=payload.nonce,
            )
        except workspace_auth_service.WorkspaceAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if verified_user.id != current_user.id:
            raise HTTPException(status_code=401, detail="Google Workspace identity did not match")
    elif not payload.password or not auth_service.verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return PrivilegedAuthResponse(privileged_token=create_privileged_token(current_user))


@router.post("/change-password", response_model=AuthUserRead)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthUserRead:
    _require_legacy_auth_enabled()
    try:
        updated_user = auth_service.change_user_password(
            db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthUserRead.model_validate(updated_user)


@router.get("/invitations", response_model=list[UserInviteRead])
def list_invitations(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[UserInviteRead]:
    _require_legacy_auth_enabled()
    return [UserInviteRead.model_validate(invite) for invite in auth_service.list_user_invites(db)]


@router.post("/invitations", response_model=UserInviteCreateResponse)
def create_invitation(
    payload: UserInviteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> UserInviteCreateResponse:
    _require_legacy_auth_enabled()
    try:
        result = auth_service.create_user_invite(
            db,
            current_user=current_user,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    invite_response = UserInviteRead.model_validate(result.invite)
    return UserInviteCreateResponse(
        **invite_response.model_dump(),
        invite_code=result.invite_code,
        email_delivery_status=result.email_delivery_status,
        email_delivery_detail=result.email_delivery_detail,
        reissued_existing=result.reissued_existing,
    )


@router.delete("/invitations/{invite_id}", status_code=204)
def revoke_invitation(
    invite_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> Response:
    _require_legacy_auth_enabled()
    try:
        auth_service.revoke_user_invite(db, invite_id=invite_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/accept-invite", response_model=TokenResponse)
def accept_invitation(
    payload: UserInviteAcceptRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    _require_legacy_auth_enabled()
    try:
        user = auth_service.accept_user_invite(
            db,
            invite_code=payload.invite_code,
            username=payload.username,
            password=payload.password,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _build_token_response(user)
