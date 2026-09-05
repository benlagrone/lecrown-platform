from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.distribution import DistributionPublishRequest, DistributionPublishResponse
from app.services import distribution_service

router = APIRouter()


@router.post("/publish", response_model=DistributionPublishResponse)
def publish(payload: DistributionPublishRequest, db: Session = Depends(get_db)) -> DistributionPublishResponse:
    return distribution_service.publish(db, payload)
