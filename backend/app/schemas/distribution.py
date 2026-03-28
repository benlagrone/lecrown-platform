from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.youtube import YouTubePrivacyStatus

DistributionChannel = Literal["linkedin", "youtube", "twitter", "website"]


class DistributionPublishRequest(BaseModel):
    content_id: str = Field(min_length=1)
    channels: list[DistributionChannel] = Field(min_length=1)
    youtube_video_path: str | None = None
    video_style: str | None = None
    youtube_privacy_status: YouTubePrivacyStatus = "private"


class DistributionPublishResponse(BaseModel):
    content_id: str
    results: dict[str, dict]
