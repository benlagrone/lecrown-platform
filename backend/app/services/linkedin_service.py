import requests
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services import content_service, transform_service
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _resolve_org_id(tenant: str) -> str:
    if tenant == "development":
        return settings.linkedin_org_id_dev
    if tenant == "properties":
        return settings.linkedin_org_id_prop
    return ""


def publish(db: Session, content_id: str) -> dict:
    content = content_service.get_by_id(db, content_id)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    if not settings.linkedin_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LINKEDIN_TOKEN is not configured",
        )

    org_id = _resolve_org_id(content.tenant)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LinkedIn organization ID is not configured for tenant '{content.tenant}'",
        )

    text = transform_service.build_linkedin_text(content)
    payload = {
        "author": f"urn:li:organization:{org_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    headers = {
        "Authorization": f"Bearer {settings.linkedin_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    try:
        response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=payload,
            headers=headers,
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.exception("LinkedIn publish request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LinkedIn publish request failed",
        ) from exc

    try:
        linkedin_payload = response.json()
    except ValueError:
        linkedin_payload = {"raw": response.text}

    if response.status_code >= 400:
        content.linkedin_status = "failed"
        content_service.set_distribution_channel(content, "linkedin", True)
        content_service.save(db, content)
        raise HTTPException(status_code=response.status_code, detail=linkedin_payload)

    content.linkedin_status = "published"
    content.linkedin_post_id = linkedin_payload.get("id")
    content_service.set_distribution_channel(content, "linkedin", True)
    content_service.save(db, content)

    return {
        "status": "published",
        "content_id": content.id,
        "linkedin": linkedin_payload,
    }
