from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.content import ContentCreate, ContentRead
from app.services import content_service

router = APIRouter()
TenantName = Literal["development", "properties"]


@router.post("/create", response_model=ContentRead)
def create_content(payload: ContentCreate, db: Session = Depends(get_db)) -> ContentRead:
    return content_service.create(db, payload)


@router.get("/list", response_model=list[ContentRead])
def list_content(tenant: TenantName, db: Session = Depends(get_db)) -> list[ContentRead]:
    return content_service.list_for_tenant(db, tenant)
