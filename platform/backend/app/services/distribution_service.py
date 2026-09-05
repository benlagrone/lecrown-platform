from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.distribution import DistributionPublishRequest
from app.schemas.youtube import YouTubePublishRequest
from app.config import get_settings
from app.services import ai_video_service, content_service, linkedin_service, twitter_service, youtube_service

settings = get_settings()


def publish(db: Session, payload: DistributionPublishRequest) -> dict:
    content = content_service.get_by_id(db, payload.content_id)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    results: dict[str, dict] = {}

    for channel in dict.fromkeys(payload.channels):
        if channel == "linkedin":
            results[channel] = linkedin_service.publish(db, content.id)
            continue

        if channel == "youtube":
            video_path = payload.youtube_video_path or (content.media or {}).get("video_path")
            video_url = (content.media or {}).get("video_url")
            if payload.youtube_video_path:
                content = ai_video_service.attach_video_asset(db, content, payload.youtube_video_path)
                video_path = payload.youtube_video_path
            if not video_path and not video_url:
                generated_source = ai_video_service.generate_video(db, content, style=payload.video_style)
                if generated_source.startswith(("http://", "https://")):
                    video_url = generated_source
                    video_path = None
                else:
                    video_path = generated_source
                content = content_service.get_by_id(db, content.id) or content
                video_url = (content.media or {}).get("video_url") or video_url
            results[channel] = youtube_service.publish(
                db,
                YouTubePublishRequest(
                    content_id=content.id,
                    video_path=video_path,
                    video_url=video_url,
                    privacy_status=payload.youtube_privacy_status,
                    category_id=settings.youtube_category_id,
                ),
            )
            content = content_service.get_by_id(db, content.id) or content
            continue

        if channel == "twitter":
            results[channel] = twitter_service.publish(content)
            continue

        if channel == "website":
            results[channel] = {
                "status": "not_implemented",
                "detail": "Website rendering is the next distribution target, but not wired yet.",
                "content_id": content.id,
            }
            continue

    return {"content_id": content.id, "results": results}
