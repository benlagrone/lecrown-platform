import mimetypes
import os
import tempfile

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.tenant import ensure_valid_tenant
from app.schemas.youtube import YouTubePublishRequest
from app.services import content_service, transform_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _tenant_tokens(tenant: str) -> tuple[str, str]:
    if tenant == "development":
        return settings.youtube_access_token_dev, settings.youtube_refresh_token_dev
    if tenant == "properties":
        return settings.youtube_access_token_prop, settings.youtube_refresh_token_prop
    return "", ""


def _download_video_url(video_url: str) -> str:
    try:
        response = requests.get(video_url, stream=True, timeout=(30, 600))
    except requests.RequestException as exc:
        logger.exception("Video download failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not download rendered video from the worker",
        ) from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        raise HTTPException(status_code=response.status_code, detail=payload)

    suffix = os.path.splitext(video_url)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                temp_file.write(chunk)
        return temp_file.name


def _resolve_access_token(tenant: str) -> str:
    access_token, refresh_token = _tenant_tokens(tenant)
    if access_token:
        return access_token

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"YouTube credentials are not configured for tenant '{tenant}'",
        )

    if not settings.youtube_client_id or not settings.youtube_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are required to refresh YouTube tokens",
        )

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.youtube_client_id,
                "client_secret": settings.youtube_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.exception("YouTube access token refresh failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not refresh YouTube access token",
        ) from exc

    try:
        token_payload = response.json()
    except ValueError:
        token_payload = {"raw": response.text}
    if response.status_code >= 400 or "access_token" not in token_payload:
        raise HTTPException(status_code=response.status_code, detail=token_payload)

    return token_payload["access_token"]


def _upload_video(
    *,
    access_token: str,
    title: str,
    description: str,
    video_path: str,
    tags: list[str],
    privacy_status: str,
    category_id: str,
    notify_subscribers: bool,
    embeddable: bool,
    contains_synthetic_media: bool,
) -> dict:
    if not os.path.isfile(video_path):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Video file does not exist at '{video_path}'",
        )

    file_size = os.path.getsize(video_path)
    mime_type = mimetypes.guess_type(video_path)[0] or "application/octet-stream"

    snippet = {
        "title": title,
        "description": description,
        "categoryId": category_id,
    }
    if tags:
        snippet["tags"] = tags

    status_body = {
        "privacyStatus": privacy_status,
        "embeddable": embeddable,
    }
    if contains_synthetic_media:
        status_body["containsSyntheticMedia"] = True

    metadata = {"snippet": snippet, "status": status_body}
    params = {
        "uploadType": "resumable",
        "part": "snippet,status",
        "notifySubscribers": str(notify_subscribers).lower(),
    }

    try:
        initiate_response = requests.post(
            YOUTUBE_UPLOAD_URL,
            params=params,
            json=metadata,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Length": str(file_size),
                "X-Upload-Content-Type": mime_type,
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.exception("YouTube upload session creation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create YouTube upload session",
        ) from exc

    if initiate_response.status_code >= 400:
        try:
            error_payload = initiate_response.json()
        except ValueError:
            error_payload = {"raw": initiate_response.text}
        raise HTTPException(status_code=initiate_response.status_code, detail=error_payload)

    upload_url = initiate_response.headers.get("Location")
    if not upload_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YouTube did not return an upload session URL",
        )

    try:
        with open(video_path, "rb") as video_file:
            upload_response = requests.put(
                upload_url,
                data=video_file,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": mime_type,
                    "Content-Length": str(file_size),
                },
                timeout=(30, 600),
            )
    except requests.RequestException as exc:
        logger.exception("YouTube video upload failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="YouTube video upload failed",
        ) from exc

    try:
        payload = upload_response.json()
    except ValueError:
        payload = {"raw": upload_response.text}

    if upload_response.status_code >= 400:
        raise HTTPException(status_code=upload_response.status_code, detail=payload)

    return payload


def publish(db: Session, payload: YouTubePublishRequest) -> dict:
    content = None
    temp_download_path = None
    if payload.content_id:
        content = content_service.get_by_id(db, payload.content_id)
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
        transformed = transform_service.build_youtube_payload(
            content,
            video_path=payload.video_path,
            privacy_status=payload.privacy_status,
            category_id=payload.category_id,
        )
        tenant = content.tenant
        title = payload.title or transformed["title"]
        description = payload.description or transformed["description"]
        tags = payload.tags or transformed["tags"]
        video_path = payload.video_path or transformed["video_path"]
        video_url = payload.video_url or (content.media or {}).get("video_url")
    else:
        tenant = ensure_valid_tenant(payload.tenant or "")
        title = payload.title or ""
        description = payload.description or ""
        tags = payload.tags
        video_path = payload.video_path
        video_url = payload.video_url

    if not video_path and video_url:
        temp_download_path = _download_video_url(video_url)
        video_path = temp_download_path

    if not video_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A video_path or video_url is required for YouTube publishing",
        )

    try:
        access_token = _resolve_access_token(tenant)
        try:
            youtube_payload = _upload_video(
                access_token=access_token,
                title=title,
                description=description,
                video_path=video_path,
                tags=tags,
                privacy_status=payload.privacy_status,
                category_id=payload.category_id or settings.youtube_category_id,
                notify_subscribers=payload.notify_subscribers,
                embeddable=payload.embeddable,
                contains_synthetic_media=payload.contains_synthetic_media,
            )
        except HTTPException:
            if content is not None:
                content_service.set_distribution_channel(content, "youtube", True)
                content_service.update_media(
                    content,
                    video_path=video_path if temp_download_path is None else None,
                    video_url=video_url,
                    youtube_status="failed",
                )
                content_service.save(db, content)
            raise
    finally:
        if temp_download_path and os.path.exists(temp_download_path):
            os.unlink(temp_download_path)

    if content is not None:
        content_service.set_distribution_channel(content, "youtube", True)
        content_service.update_media(
            content,
            video_generated=True,
            video_path=video_path if temp_download_path is None else None,
            video_url=video_url,
            render_status="complete",
            youtube_status="published",
            youtube_video_id=youtube_payload.get("id"),
        )
        content_service.save(db, content)

    return {
        "status": "published",
        "video_id": youtube_payload.get("id"),
        "content_id": content.id if content is not None else None,
        "youtube": youtube_payload,
    }
