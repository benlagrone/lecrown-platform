from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.intake import IntakeLeadSubmission
from app.models.gov_contract import GovContractOpportunity
from app.schemas.intake import IntakeLeadCreate
from app.services import espocrm_service
from app.utils.helpers import new_uuid

settings = get_settings()

ESPO_STANDARD_LEAD_FIELDS = {
    "firstName",
    "lastName",
    "emailAddress",
    "phoneNumber",
    "description",
    "source",
}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_contact_name(first_name: str | None, last_name: str | None) -> str | None:
    parts = [part for part in (_clean(first_name), _clean(last_name)) if part]
    return " ".join(parts) or None


def _build_delivery_payload(payload: IntakeLeadCreate) -> dict[str, Any]:
    raw_lead_payload = payload.lead.model_dump(exclude_none=True)
    allowed_fields = ESPO_STANDARD_LEAD_FIELDS | set(settings.espocrm_allowed_extra_fields)
    delivery_payload = {
        key: value
        for key, value in raw_lead_payload.items()
        if key in allowed_fields
    }

    if not _clean(delivery_payload.get("lastName")):
        delivery_payload["lastName"] = "Website Lead"

    lead_source = _clean(raw_lead_payload.get("source"))
    configured_crm_source = _clean(settings.espocrm_lead_source)
    if configured_crm_source:
        delivery_payload["source"] = configured_crm_source
    elif lead_source:
        delivery_payload.pop("source", None)

    description_lines = []
    if _clean(delivery_payload.get("description")):
        description_lines.append(str(delivery_payload["description"]).strip())
    if lead_source:
        description_lines.append(f"Lead source: {lead_source}")
    business_context = _clean(payload.business_context) or _clean(raw_lead_payload.get("businessUnit"))
    if business_context:
        description_lines.append(f"Business context: {business_context}")
    product_context = _clean(payload.product_context) or _clean(raw_lead_payload.get("productType"))
    if product_context:
        description_lines.append(f"Product context: {product_context}")
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
    raw_lead_payload = payload.lead.model_dump(exclude_none=True)
    business_context = _clean(payload.business_context) or _clean(raw_lead_payload.get("businessUnit"))
    product_context = _clean(payload.product_context) or _clean(raw_lead_payload.get("productType"))
    lead_source = _clean(raw_lead_payload.get("source")) or _clean(delivery_payload.get("source"))

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


def _rebuild_submission_payload(submission: IntakeLeadSubmission) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if not isinstance(submission.raw_payload, dict):
        return None
    try:
        raw_payload = IntakeLeadCreate.model_validate(submission.raw_payload)
    except ValueError:
        return None

    delivery_payload = _build_delivery_payload(raw_payload)
    normalized_payload = _normalize(raw_payload, delivery_payload)
    return delivery_payload, normalized_payload


def _deliver_submission_to_crm(db: Session, submission: IntakeLeadSubmission) -> IntakeLeadSubmission:
    rebuilt_payload = _rebuild_submission_payload(submission)
    if rebuilt_payload:
        delivery_payload, normalized_payload = rebuilt_payload
        submission.delivery_payload = delivery_payload
        submission.normalized_payload = normalized_payload
    else:
        delivery_payload = submission.delivery_payload or {}
    submission.status = "received"
    submission.delivery_status = "pending"
    submission.delivery_record_id = None
    submission.delivery_response = None
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
    _sync_contract_funnel_status(db, submission)
    return submission


def _sync_contract_funnel_status(db: Session, submission: IntakeLeadSubmission) -> None:
    raw_payload = submission.raw_payload if isinstance(submission.raw_payload, dict) else {}
    metadata = raw_payload.get("metadata") if isinstance(raw_payload.get("metadata"), dict) else {}
    contract_id = metadata.get("contract_id")
    if not contract_id:
        return

    contract = db.get(GovContractOpportunity, contract_id)
    if contract is None:
        return

    contract.funnel_status = "funneled" if submission.delivery_status == "delivered" else "failed"
    contract.funnel_submission_id = submission.id
    contract.funnel_delivery_target = submission.delivery_target
    contract.funnel_delivery_status = submission.delivery_status
    contract.funnel_record_id = submission.delivery_record_id
    contract.funnel_payload = submission.delivery_payload
    contract.funnel_response = submission.delivery_response
    db.add(contract)
    db.commit()


def retry_lead_submission(db: Session, submission_id: str) -> IntakeLeadSubmission:
    submission = db.get(IntakeLeadSubmission, submission_id)
    if submission is None:
        raise ValueError("Intake submission not found")
    if submission.delivery_status == "delivered":
        return submission
    return _deliver_submission_to_crm(db, submission)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _delivery_error_message(submission: IntakeLeadSubmission) -> str | None:
    response = submission.delivery_response
    if not isinstance(response, dict):
        return None
    error = response.get("error")
    if isinstance(error, str) and error.strip():
        status_code = response.get("status_code")
        if status_code:
            return f"{error} ({status_code})"
        return error
    return None


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
                    "delivery_error": _delivery_error_message(submission),
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
