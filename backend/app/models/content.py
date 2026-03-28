from sqlalchemy import Boolean, Column, DateTime, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


def default_distribution() -> dict:
    return {
        "linkedin": False,
        "youtube": False,
        "website": True,
        "twitter": False,
    }


def default_media() -> dict:
    return {
        "video_generated": False,
        "video_path": None,
        "video_url": None,
        "render_status": None,
        "render_job_id": None,
        "youtube_video_id": None,
        "youtube_status": None,
    }


class Content(Base):
    __tablename__ = "content"

    id = Column(String, primary_key=True)
    tenant = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    tags = Column(JSON, nullable=False, default=list)
    distribution = Column(JSON, nullable=False, default=default_distribution)
    media = Column(JSON, nullable=False, default=default_media)

    publish_linkedin = Column(Boolean, default=False, nullable=False)
    publish_site = Column(Boolean, default=True, nullable=False)
    linkedin_post_id = Column(String, nullable=True)
    linkedin_status = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
