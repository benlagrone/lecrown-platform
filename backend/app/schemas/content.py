from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TenantName = Literal["development", "properties"]


class DistributionConfig(BaseModel):
    linkedin: bool = False
    youtube: bool = False
    website: bool = True
    twitter: bool = False


class MediaConfig(BaseModel):
    video_generated: bool = False
    video_path: str | None = None
    video_url: str | None = None
    render_status: str | None = None
    render_job_id: str | None = None
    youtube_video_id: str | None = None
    youtube_status: str | None = None


class ContentCreate(BaseModel):
    tenant: TenantName
    type: str = Field(default="insight", min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    publish_linkedin: bool = False
    publish_site: bool = True
    distribution: DistributionConfig | None = None
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
    linkedin_post_id: str | None = None
    linkedin_status: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
