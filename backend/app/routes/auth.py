from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import authenticate_admin, create_access_token, get_current_admin

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(payload.username))


@router.get("/me")
def me(current_admin: dict = Depends(get_current_admin)) -> dict:
    return current_admin
