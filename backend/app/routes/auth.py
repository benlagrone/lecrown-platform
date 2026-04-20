from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_admin, get_current_user
from app.models.user import User
from app.services import auth_service

router = APIRouter()


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


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


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


def _build_token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user),
        user=AuthUserRead.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = auth_service.authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _build_token_response(user)


@router.get("/me", response_model=AuthUserRead)
def me(current_user: User = Depends(get_current_user)) -> AuthUserRead:
    return AuthUserRead.model_validate(current_user)


@router.post("/change-password", response_model=AuthUserRead)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthUserRead:
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
    return [UserInviteRead.model_validate(invite) for invite in auth_service.list_user_invites(db)]


@router.post("/invitations", response_model=UserInviteCreateResponse)
def create_invitation(
    payload: UserInviteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
) -> UserInviteCreateResponse:
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
