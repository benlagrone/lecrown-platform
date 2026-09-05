from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.content import TenantName

YouTubePrivacyStatus = Literal["private", "unlisted", "public"]


class YouTubePublishRequest(BaseModel):
    content_id: Optional[str] = None
    tenant: Optional[TenantName] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    video_path: Optional[str] = Field(default=None, min_length=1)
    video_url: Optional[str] = Field(default=None, min_length=1)
    tags: list[str] = Field(default_factory=list)
    privacy_status: YouTubePrivacyStatus = "private"
    category_id: str = "22"
    notify_subscribers: bool = False
    embeddable: bool = True
    contains_synthetic_media: bool = False

    @model_validator(mode="after")
    def validate_direct_publish_mode(self) -> "YouTubePublishRequest":
        if self.content_id:
            return self

        missing = [
            field_name
            for field_name in ("tenant", "title", "description")
            if getattr(self, field_name) in (None, "")
        ]
        if self.video_path in (None, "") and self.video_url in (None, ""):
            missing.append("video_path or video_url")
        if missing:
            raise ValueError(
                "Direct YouTube publish requires tenant, title, description, and a video source "
                f"when content_id is not provided. Missing: {', '.join(missing)}"
            )
        return self


class YouTubePublishResponse(BaseModel):
    status: str
    video_id: Optional[str] = None
    content_id: Optional[str] = None
    youtube: dict
