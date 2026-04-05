from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.intake import IntakeLeadSubmission
from app.schemas.intake import IntakeLeadCreate
from app.services import espocrm_service
from app.utils.helpers import new_uuid


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_contact_name(first_name: str | None, last_name: str | None) -> str | None:
    parts = [part for part in (_clean(first_name), _clean(last_name)) if part]
    return " ".join(parts) or None


def _build_delivery_payload(payload: IntakeLeadCreate) -> dict[str, Any]:
    delivery_payload = payload.lead.model_dump(exclude_none=True)

    if not _clean(delivery_payload.get("lastName")):
        delivery_payload["lastName"] = "Website Lead"

    if payload.business_context and not _clean(delivery_payload.get("businessUnit")):
        delivery_payload["businessUnit"] = payload.business_context.strip()

    if payload.product_context and not _clean(delivery_payload.get("productType")):
        delivery_payload["productType"] = payload.product_context.strip()

    description_lines = []
    if _clean(delivery_payload.get("description")):
        description_lines.append(str(delivery_payload["description"]).strip())
    description_lines.append(f"Source site: {payload.source_site}")
    if payload.page_url:
        description_lines.append(f"Page URL: {payload.page_url}")
    if payload.form_provider:
        description_lines.append(f"Form provider: {payload.form_provider}")
    if payload.form_id:
        description_lines.append(f"Form ID: {payload.form_id}")
    if payload.external_entry_id:
        description_lines.append(f"Entry ID: {payload.external_entry_id}")
    if payload.campaign:
        description_lines.append(f"Campaign: {payload.campaign}")

    delivery_payload["description"] = "\n\n".join(description_lines)
    return delivery_payload


def _normalize(payload: IntakeLeadCreate, delivery_payload: dict[str, Any]) -> dict[str, Any]:
    business_context = _clean(payload.business_context) or _clean(delivery_payload.get("businessUnit"))
    product_context = _clean(payload.product_context) or _clean(delivery_payload.get("productType"))
    lead_source = _clean(delivery_payload.get("source"))

    return {
        "source_site": payload.source_site,
        "source_type": payload.source_type,
        "form_provider": payload.form_provider,
        "form_id": payload.form_id,
        "form_name": payload.form_name,
        "external_entry_id": payload.external_entry_id,
        "page_url": payload.page_url,
        "campaign": payload.campaign,
        "business_context": business_context,
        "product_context": product_context,
        "lead_source": lead_source,
        "contact": {
            "first_name": _clean(delivery_payload.get("firstName")),
            "last_name": _clean(delivery_payload.get("lastName")),
            "name": _build_contact_name(
                delivery_payload.get("firstName"),
                delivery_payload.get("lastName"),
            ),
            "email": _clean(delivery_payload.get("emailAddress")),
            "phone": _clean(delivery_payload.get("phoneNumber")),
        },
        "message": _clean(delivery_payload.get("description")),
        "metadata": dict(payload.metadata),
    }


def create_lead_submission(db: Session, payload: IntakeLeadCreate) -> IntakeLeadSubmission:
    raw_payload = payload.model_dump(mode="json")
    delivery_payload = _build_delivery_payload(payload)
    normalized = _normalize(payload, delivery_payload)

    submission = IntakeLeadSubmission(
        id=new_uuid(),
        source_site=payload.source_site,
        source_type=payload.source_type,
        form_provider=payload.form_provider,
        form_id=payload.form_id,
        form_name=payload.form_name,
        external_entry_id=payload.external_entry_id,
        page_url=payload.page_url,
        campaign=payload.campaign,
        business_context=normalized.get("business_context"),
        product_context=normalized.get("product_context"),
        contact_name=normalized["contact"].get("name"),
        email=normalized["contact"].get("email"),
        phone=normalized["contact"].get("phone"),
        lead_source=normalized.get("lead_source"),
        message=normalized.get("message"),
        status="received",
        delivery_target="espocrm",
        delivery_status="pending",
        raw_payload=raw_payload,
        normalized_payload=normalized,
        delivery_payload=delivery_payload,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    try:
        delivery_response = espocrm_service.create_lead(delivery_payload)
        submission.status = "processed"
        submission.delivery_status = "delivered"
        submission.delivery_record_id = delivery_response.get("id")
        submission.delivery_response = delivery_response
    except espocrm_service.EspoCRMError as exc:
        submission.status = "delivery_failed"
        submission.delivery_status = "failed"
        submission.delivery_response = {
            "error": str(exc),
            "status_code": exc.status_code,
            "body": exc.body,
        }

    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_submissions(
    db: Session,
    *,
    source_site: str | None = None,
    limit: int = 50,
) -> list[IntakeLeadSubmission]:
    statement = select(IntakeLeadSubmission)
    if source_site:
        statement = statement.where(IntakeLeadSubmission.source_site == source_site)
    statement = statement.order_by(desc(IntakeLeadSubmission.created_at)).limit(limit)
    return list(db.scalars(statement).all())
