from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.backoffice import DocumentUploadRead, DocumentVersionRead
from app.services import document_service

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadRead)
async def upload_document(
    brokerage_id: str = Form(...),
    name: str = Form(...),
    transaction_id: str | None = Form(default=None),
    classification: str = Form(default="brokerage_confidential"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadRead:
    try:
        content = await file.read(document_service.settings.document_max_bytes + 1)
        document, version = document_service.upload(
            db,
            actor=current_user,
            brokerage_id=brokerage_id,
            name=name,
            transaction_id=transaction_id,
            classification=classification,
            media_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentUploadRead(
        document_id=document.id,
        brokerage_id=document.brokerage_id,
        transaction_id=document.transaction_id,
        name=document.name,
        classification=document.classification,
        retention_policy=document.retention_policy,
        version=DocumentVersionRead.model_validate(version),
    )
