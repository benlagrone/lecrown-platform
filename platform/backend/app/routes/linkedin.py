from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.linkedin import LinkedInPublishRequest, LinkedInPublishResponse
from app.services import linkedin_service

router = APIRouter()


@router.post("/publish", response_model=LinkedInPublishResponse)
def publish(payload: LinkedInPublishRequest, db: Session = Depends(get_db)) -> LinkedInPublishResponse:
    return linkedin_service.publish(db, payload.content_id)
