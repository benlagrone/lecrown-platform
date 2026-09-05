from __future__ import annotations

from app.models.content import Content


def build_linkedin_text(content: Content) -> str:
    return f"{content.title}\n\n{content.body}".strip()


def build_youtube_payload(
    content: Content,
    *,
    video_path: str | None = None,
    privacy_status: str = "private",
    category_id: str = "22",
) -> dict:
    description_parts = [content.body.strip()]
    if content.tags:
        description_parts.append("Tags: " + ", ".join(content.tags))
    description_parts.append(f"Tenant: {content.tenant}")

    return {
        "title": content.title[:100],
        "description": "\n\n".join(part for part in description_parts if part)[:5000],
        "tags": content.tags,
        "video_path": video_path or (content.media or {}).get("video_path"),
        "privacy_status": privacy_status,
        "category_id": category_id,
    }
