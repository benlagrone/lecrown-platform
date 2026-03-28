import os

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.content import Content
from app.services import content_service, video_client


def attach_video_asset(db: Session, content: Content, video_path: str) -> Content:
    if not os.path.isfile(video_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Video file does not exist at '{video_path}'",
        )

    content_service.update_media(
        content,
        video_generated=True,
        video_path=video_path,
        video_url=None,
        render_status="complete",
        youtube_status="ready",
    )
    return content_service.save(db, content)


def generate_video(db: Session, content: Content, *, style: str | None = None) -> str:
    media = (content.media or {})
    video_path = media.get("video_path")
    if video_path and os.path.isfile(video_path):
        attach_video_asset(db, content, video_path)
        return video_path

    render_result = video_client.generate_video(content, style=style)
    render_status = render_result.get("status") or "unknown"
    rendered_video_path = render_result.get("video_path")
    rendered_video_url = render_result.get("video_url")
    render_job_id = render_result.get("job_id")

    if render_status != "complete":
        content_service.update_media(
            content,
            video_generated=False,
            render_status=render_status,
            render_job_id=render_job_id,
        )
        content_service.save(db, content)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Video generation did not complete synchronously",
                "render": render_result,
            },
        )

    if rendered_video_path and os.path.isfile(rendered_video_path):
        content_service.update_media(
            content,
            video_generated=True,
            video_path=rendered_video_path,
            video_url=rendered_video_url,
            render_status="complete",
            render_job_id=render_job_id,
            youtube_status="ready",
        )
        content_service.save(db, content)
        return rendered_video_path

    if rendered_video_url:
        content_service.update_media(
            content,
            video_generated=True,
            video_path=None,
            video_url=rendered_video_url,
            render_status="complete",
            render_job_id=render_job_id,
            youtube_status="ready",
        )
        content_service.save(db, content)
        return rendered_video_url

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": (
                "Video generation completed without a usable video source. Return a reachable "
                "video_path or video_url from the render worker."
            ),
            "render": render_result,
        },
    )
