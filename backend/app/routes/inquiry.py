from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.inquiry import InquiryCreate, InquiryRead
from app.services import inquiry_service

router = APIRouter()


@router.post("/create", response_model=InquiryRead)
def create_inquiry(payload: InquiryCreate, db: Session = Depends(get_db)) -> InquiryRead:
    return inquiry_service.create(db, payload)


@router.get("/list", response_model=list[InquiryRead])
def list_inquiries(db: Session = Depends(get_db)) -> list[InquiryRead]:
    return inquiry_service.list_for_properties(db)
