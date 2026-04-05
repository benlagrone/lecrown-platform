from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TenantName = Literal["development", "properties"]


class DistributionConfig(BaseModel):
    linkedin: bool = False
    youtube: bool = False
    website: bool = True
    twitter: bool = False


class MediaConfig(BaseModel):
    video_generated: bool = False
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    render_status: Optional[str] = None
    render_job_id: Optional[str] = None
    youtube_video_id: Optional[str] = None
    youtube_status: Optional[str] = None


class ContentCreate(BaseModel):
    tenant: TenantName
    type: str = Field(default="insight", min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    publish_linkedin: bool = False
    publish_site: bool = True
    distribution: Optional[DistributionConfig] = None
    media: MediaConfig = Field(default_factory=MediaConfig)


class ContentRead(BaseModel):
    id: str
    tenant: TenantName
    type: str
    title: str
    body: str
    tags: list[str]
    distribution: DistributionConfig
    media: MediaConfig
    publish_linkedin: bool
    publish_site: bool
    linkedin_post_id: Optional[str] = None
    linkedin_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
