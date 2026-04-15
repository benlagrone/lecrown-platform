from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.intake import IntakeLeadSubmission
from app.schemas.intake import IntakeLeadCreate
from app.services import espocrm_service
from app.utils.helpers import new_uuid

settings = get_settings()


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


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def get_dashboard(
    db: Session,
    *,
    source_limit: int = 12,
    recent_limit: int = 12,
) -> dict[str, Any]:
    submissions = list(
        db.scalars(select(IntakeLeadSubmission).order_by(desc(IntakeLeadSubmission.created_at))).all()
    )
    now = datetime.now(timezone.utc)
    today_cutoff = now - timedelta(days=1)
    week_cutoff = now - timedelta(days=7)

    overview = {
        "observed_source_sites": 0,
        "total_submissions": 0,
        "new_contacts_today": 0,
        "new_contacts_7d": 0,
        "delivered_submissions": 0,
        "failed_submissions": 0,
    }
    recent_contacts: list[dict[str, Any]] = []
    source_summaries: dict[str, dict[str, Any]] = {}

    for submission in submissions:
        created_at = _as_utc(submission.created_at)
        is_today = created_at >= today_cutoff
        is_week = created_at >= week_cutoff

        overview["total_submissions"] += 1
        if is_today:
            overview["new_contacts_today"] += 1
        if is_week:
            overview["new_contacts_7d"] += 1
        if submission.delivery_status == "delivered":
            overview["delivered_submissions"] += 1
        elif submission.delivery_status == "failed":
            overview["failed_submissions"] += 1

        if len(recent_contacts) < recent_limit:
            recent_contacts.append(
                {
                    "id": submission.id,
                    "source_site": submission.source_site,
                    "contact_name": submission.contact_name,
                    "email": submission.email,
                    "phone": submission.phone,
                    "business_context": submission.business_context,
                    "product_context": submission.product_context,
                    "page_url": submission.page_url,
                    "campaign": submission.campaign,
                    "status": submission.status,
                    "delivery_status": submission.delivery_status,
                    "delivery_record_id": submission.delivery_record_id,
                    "created_at": submission.created_at,
                }
            )

        summary = source_summaries.get(submission.source_site)
        if summary is None:
            summary = {
                "source_site": submission.source_site,
                "source_type": submission.source_type,
                "business_contexts": set(),
                "form_providers": set(),
                "form_names": set(),
                "total_submissions": 0,
                "delivered_submissions": 0,
                "failed_submissions": 0,
                "new_contacts_today": 0,
                "new_contacts_7d": 0,
                "last_submission_at": created_at,
                "last_contact_name": submission.contact_name,
                "last_page_url": submission.page_url,
                "last_delivery_status": submission.delivery_status,
            }
            source_summaries[submission.source_site] = summary

        summary["total_submissions"] += 1
        if submission.business_context:
            summary["business_contexts"].add(submission.business_context)
        if submission.form_provider:
            summary["form_providers"].add(submission.form_provider)
        if submission.form_name:
            summary["form_names"].add(submission.form_name)
        if submission.delivery_status == "delivered":
            summary["delivered_submissions"] += 1
        elif submission.delivery_status == "failed":
            summary["failed_submissions"] += 1
        if is_today:
            summary["new_contacts_today"] += 1
        if is_week:
            summary["new_contacts_7d"] += 1
        if created_at >= summary["last_submission_at"]:
            summary["last_submission_at"] = created_at
            summary["last_contact_name"] = submission.contact_name
            summary["last_page_url"] = submission.page_url
            summary["last_delivery_status"] = submission.delivery_status

    overview["observed_source_sites"] = len(source_summaries)

    sorted_sources = sorted(
        source_summaries.values(),
        key=lambda summary: summary["last_submission_at"],
        reverse=True,
    )[:source_limit]

    normalized_sources = [
        {
            **summary,
            "business_contexts": sorted(summary["business_contexts"]),
            "form_providers": sorted(summary["form_providers"]),
            "form_names": sorted(summary["form_names"]),
        }
        for summary in sorted_sources
    ]

    crm_is_configured = espocrm_service.is_configured()
    connections = [
        {
            "key": "intake_api",
            "label": "Intake API",
            "status": "protected" if settings.intake_api_key else "open",
            "detail": "Public sites can post new marketing leads to POST /intake/lead.",
            "value": "X-Intake-Key required" if settings.intake_api_key else "No intake key configured",
        },
        {
            "key": "espocrm",
            "label": "EspoCRM delivery",
            "status": "configured" if crm_is_configured else "attention",
            "detail": "Lead submissions are forwarded to EspoCRM after local intake storage.",
            "value": "Ready to deliver" if crm_is_configured else "CRM credentials or base URL missing",
        },
    ]

    return {
        "overview": overview,
        "connections": connections,
        "source_sites": normalized_sources,
        "recent_contacts": recent_contacts,
    }


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
