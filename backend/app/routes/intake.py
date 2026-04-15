from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin, require_intake_key
from app.schemas.intake import (
    IntakeDashboardRead,
    IntakeLeadCreate,
    IntakeLeadRead,
    IntakeLeadResponse,
)
from app.services import intake_service

router = APIRouter()


@router.post("/lead", response_model=IntakeLeadResponse, status_code=status.HTTP_201_CREATED)
def create_intake_lead(
    payload: IntakeLeadCreate,
    db: Session = Depends(get_db),
    _: None = Depends(require_intake_key),
) -> IntakeLeadResponse:
    submission = intake_service.create_lead_submission(db, payload)
    return IntakeLeadResponse(
        submission_id=submission.id,
        status=submission.status,
        delivery_target=submission.delivery_target,
        delivery_status=submission.delivery_status,
        delivery_record_id=submission.delivery_record_id,
        source_site=submission.source_site,
        business_context=submission.business_context,
        product_context=submission.product_context,
        created_at=submission.created_at,
    )


@router.get("/dashboard", response_model=IntakeDashboardRead)
def get_intake_dashboard(
    source_limit: int = Query(default=12, ge=1, le=50),
    recent_limit: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> IntakeDashboardRead:
    return intake_service.get_dashboard(db, source_limit=source_limit, recent_limit=recent_limit)


@router.get("/list", response_model=list[IntakeLeadRead])
def list_intake_leads(
    source_site: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_admin),
) -> list[IntakeLeadRead]:
    return intake_service.list_submissions(db, source_site=source_site, limit=limit)
