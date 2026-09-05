from __future__ import annotations

import os

import requests
from fastapi import HTTPException, status

from app.config import get_settings
from app.models.content import Content
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _stub_response(content: Content, style: str) -> dict:
    media = content.media or {}
    video_path = media.get("video_path") or settings.video_stub_video_path or None
    video_url = media.get("video_url") or settings.video_stub_video_url or None

    return {
        "status": "complete",
        "content_id": content.id,
        "style": style,
        "video_path": video_path,
        "video_url": video_url,
        "job_id": f"stub-{content.id}",
        "provider": "stub",
    }


def generate_video(content: Content, *, style: str | None = None) -> dict:
    selected_style = style or settings.video_render_default_style

    if settings.video_render_mode == "stub":
        return _stub_response(content, selected_style)

    if settings.video_render_mode != "http":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsupported VIDEO_RENDER_MODE '{settings.video_render_mode}'",
        )

    base_url = settings.video_server_url.rstrip("/")
    endpoint = settings.video_render_endpoint
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    payload = {
        "content_id": content.id,
        "script": content.body,
        "title": content.title,
        "tenant": content.tenant,
        "style": selected_style,
        "tags": content.tags,
    }

    try:
        response = requests.post(
            f"{base_url}{endpoint}",
            json=payload,
            timeout=settings.video_render_timeout_seconds,
        )
    except requests.RequestException as exc:
        logger.exception("Video render request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Video render request failed",
        ) from exc

    try:
        render_payload = response.json()
    except ValueError:
        render_payload = {"raw": response.text}

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=render_payload)

    return render_payload
