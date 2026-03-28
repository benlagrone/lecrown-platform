from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.youtube import YouTubePublishRequest, YouTubePublishResponse
from app.services import youtube_service

router = APIRouter()


@router.post("/publish", response_model=YouTubePublishResponse)
def publish(payload: YouTubePublishRequest, db: Session = Depends(get_db)) -> YouTubePublishResponse:
    return youtube_service.publish(db, payload)
