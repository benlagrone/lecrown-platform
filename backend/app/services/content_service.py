from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.tenant import ensure_valid_tenant
from app.models.content import Content, default_distribution, default_media
from app.schemas.content import ContentCreate
from app.utils.helpers import new_uuid


def _normalized_distribution(
    distribution: dict | None,
    *,
    publish_linkedin: bool = False,
    publish_site: bool = True,
) -> dict:
    normalized = default_distribution()
    normalized["linkedin"] = publish_linkedin
    normalized["website"] = publish_site
    if distribution:
        normalized.update(distribution)
    return normalized


def _normalized_media(media: dict | None) -> dict:
    normalized = default_media()
    if media:
        normalized.update(media)
    if normalized.get("video_path") == "":
        normalized["video_path"] = None
    if normalized.get("video_url") == "":
        normalized["video_url"] = None
    return normalized


def normalize_content(content: Content) -> Content:
    distribution = _normalized_distribution(
        content.distribution,
        publish_linkedin=content.publish_linkedin,
        publish_site=content.publish_site,
    )
    media = _normalized_media(content.media)
    content.distribution = distribution
    content.media = media
    content.publish_linkedin = bool(distribution["linkedin"])
    content.publish_site = bool(distribution["website"])
    return content


def save(db: Session, content: Content) -> Content:
    normalize_content(content)
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


def set_distribution_channel(content: Content, channel: str, enabled: bool) -> Content:
    normalize_content(content)
    distribution = dict(content.distribution)
    distribution[channel] = enabled
    content.distribution = distribution
    content.publish_linkedin = bool(distribution["linkedin"])
    content.publish_site = bool(distribution["website"])
    return content


def update_media(content: Content, **updates: object) -> Content:
    normalize_content(content)
    media = dict(content.media)
    media.update(updates)
    content.media = media
    return content


def create(db: Session, payload: ContentCreate) -> Content:
    ensure_valid_tenant(payload.tenant)
    distribution = _normalized_distribution(
        payload.distribution.model_dump() if payload.distribution else None,
        publish_linkedin=payload.publish_linkedin,
        publish_site=payload.publish_site,
    )
    media = _normalized_media(payload.media.model_dump())
    if distribution["youtube"] and media["video_path"]:
        media["video_generated"] = True
        media["youtube_status"] = media["youtube_status"] or "ready"

    content = Content(
        id=new_uuid(),
        tenant=payload.tenant,
        type=payload.type,
        title=payload.title,
        body=payload.body,
        tags=payload.tags,
        distribution=distribution,
        media=media,
        publish_linkedin=distribution["linkedin"],
        publish_site=distribution["website"],
        linkedin_status="queued" if distribution["linkedin"] else None,
    )
    return save(db, content)


def list_for_tenant(db: Session, tenant: str) -> list[Content]:
    ensure_valid_tenant(tenant)
    statement = select(Content).where(Content.tenant == tenant).order_by(desc(Content.created_at))
    return [normalize_content(content) for content in db.scalars(statement).all()]


def get_by_id(db: Session, content_id: str) -> Content | None:
    content = db.get(Content, content_id)
    if content is None:
        return None
    return normalize_content(content)
