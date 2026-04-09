from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import unescape
from math import ceil
from urllib.parse import quote, urlencode, urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.gov_contract import (
    GovContractAgencyPreference,
    GovContractImportRun,
    GovContractKeywordRule,
    GovContractOpportunity,
)
from app.schemas.intake import IntakeLeadCreate
from app.services import intake_service
from app.utils.helpers import new_uuid

settings = get_settings()

SOURCE_NAME = "txsmartbuy_esbd"
FEDERAL_FORECAST_SOURCE_NAME = "federal_forecast"
GRANTS_GOV_SOURCE_NAME = "grants_gov"
SBA_SUBNET_SOURCE_NAME = "sba_subnet"
GMAIL_RFQ_SOURCE_NAME = "gmail_rfqs"
SOURCE_LABELS = {
    SOURCE_NAME: "Texas ESBD",
    FEDERAL_FORECAST_SOURCE_NAME: "Federal Forecast",
    GRANTS_GOV_SOURCE_NAME: "Grants.gov",
    SBA_SUBNET_SOURCE_NAME: "SBA SUBNet",
    GMAIL_RFQ_SOURCE_NAME: "Gmail RFQs",
}
OPEN_STATUS_CODES = {"1", "6"}
FEDERAL_FORECAST_CLOSED_STATUS_NAMES = {
    "awarded",
    "cancelled",
    "option ended closed out",
}
FEDERAL_FORECAST_QUERY_FORMAT = "json"
GRANTS_GOV_OPEN_STATUS_NAMES = {"posted", "forecasted"}
STATUS_NAME_TO_CODE = {
    "posted": "1",
    "awarded": "2",
    "posting cancelled": "3",
    "new": "4",
    "closed": "5",
    "addendum posted": "6",
    "cancelled": "7",
    "pending on files": "8",
    "pending on posting date": "9",
    "expired": "10",
    "no award": "11",
}
DEFAULT_MATCH_RULES: tuple[tuple[str, int], ...] = (
    ("property management", 9),
    ("real estate", 8),
    ("building maintenance", 7),
    ("facility maintenance", 7),
    ("facilities maintenance", 7),
    ("information technology", 7),
    ("facility management", 6),
    ("facilities management", 6),
    ("construction", 6),
    ("site development", 6),
    ("site work", 6),
    ("renovation", 6),
    ("rehabilitation", 6),
    ("general contractor", 6),
    ("cybersecurity", 6),
    ("managed it services", 6),
    ("software development", 6),
    ("systems integration", 6),
    ("application development", 5),
    ("appraisal", 5),
    ("demolition", 5),
    ("roofing", 5),
    ("concrete", 5),
    ("asphalt", 5),
    ("paving", 5),
    ("cloud services", 5),
    ("cloud migration", 5),
    ("network infrastructure", 5),
    ("hvac", 4),
    ("electrical", 4),
    ("plumbing", 4),
    ("landscaping", 4),
    ("janitorial", 4),
    ("custodial", 4),
    ("painting", 4),
    ("fencing", 4),
    ("flooring", 4),
    ("data center", 4),
    ("help desk", 4),
    ("maintenance and repair", 4),
    ("service desk", 4),
    ("technical support", 4),
    ("surveying", 4),
    ("mowing", 3),
    ("grounds maintenance", 3),
)
DEFAULT_EXTRA_KEYWORD_WEIGHT = 3
DEFAULT_AGENCY_AFFINITY_SCORE = 5
NON_MATCHING_AGENCY_AFFINITY_SCORE = 3
COMPETITION_SIGNAL_RULES: tuple[tuple[str, int], ...] = (
    ("property management", 2),
    ("grounds maintenance", 2),
    ("janitorial", 2),
    ("custodial", 2),
    ("cybersecurity", 2),
    ("roofing", 1),
    ("plumbing", 1),
    ("electrical", 1),
    ("hvac", 1),
    ("help desk", 1),
    ("network infrastructure", 1),
    ("service desk", 1),
    ("software development", 1),
    ("systems integration", 1),
    ("surveying", 1),
    ("appraisal", 1),
    ("statewide", -2),
    ("job order contract", -2),
    ("joc", -2),
    ("idiq", -2),
    ("on call", -1),
    ("multiple award", -2),
    ("master agreement", -2),
    ("general contractor", -1),
    ("construction", -1),
    ("design build", -2),
    ("cmar", -2),
    ("professional services", -1),
    ("consulting", -1),
)
DEFAULT_BUSINESS_CONTEXT = "LeCrown Development"
DEFAULT_PRODUCT_CONTEXT = "Government Contract"


class GovContractSourceError(RuntimeError):
    """Raised when an upstream opportunity source cannot be fetched or parsed."""


@dataclass
class GovContractSourceRecord:
    source_key: str
    solicitation_id: str
    source_url: str
    title: str
    agency_name: str | None
    agency_number: str | None
    status_code: str | None
    status_name: str | None
    due_date: date | None
    due_time: str | None
    posting_date: date | None
    source_created_at: datetime | None
    source_last_modified_at: datetime | None
    nigp_codes: str | None
    raw_payload: dict[str, object]


@dataclass
class GovContractFetchResult:
    request_payload: dict[str, object]
    source_total_records: int
    csv_text: str
    records: list[GovContractSourceRecord]


HTML_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _strip_html(value: object | None) -> str | None:
    if value is None:
        return None
    text = unescape(str(value))
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip().upper(), "%m/%d/%Y %I:%M %p")
    except ValueError:
        return None


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip()).date()
    except ValueError:
        return None


def _parse_feed_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_unix_timestamp(value: object | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _parse_embedded_datetimes(value: object | None) -> list[datetime]:
    if value is None:
        return []

    datetimes: list[datetime] = []
    for match in re.findall(r'datetime=["\']([^"\']+)["\']', str(value)):
        parsed = _parse_feed_timestamp(match)
        if parsed is not None:
            datetimes.append(parsed)
    return datetimes


def _parse_source_listing_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.search(r"_(\d{9,})$", value)
    if not match:
        return None
    return _parse_unix_timestamp(match.group(1))


def _format_source_url(base_url: str, params: dict[str, object] | None = None) -> str:
    if not params:
        return base_url
    return f"{base_url}?{urlencode(params)}"


def _parse_bool(value: object | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def _fit_bucket(score: int) -> str:
    if score >= 10:
        return "high"
    if score >= settings.gov_contract_match_min_score:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _normalize_match_score(score: int) -> int:
    return max(0, min(10, round(score / 2)))


def _score_timing(due_date: date | None, *, today: date) -> tuple[int, int | None]:
    if due_date is None:
        return 5, None

    days_until_due = (due_date - today).days
    if days_until_due < 0:
        return 0, days_until_due
    if days_until_due <= 2:
        return 2, days_until_due
    if days_until_due <= 6:
        return 5, days_until_due
    if days_until_due <= 21:
        return 8, days_until_due
    if days_until_due <= 45:
        return 6, days_until_due
    return 4, days_until_due


def _score_competition(parts: list[str | None]) -> int:
    haystack = _normalize_text(" ".join(part for part in parts if part))
    score = 5

    for phrase, adjustment in COMPETITION_SIGNAL_RULES:
        normalized_phrase = _normalize_text(phrase)
        if normalized_phrase and normalized_phrase in haystack:
            score += adjustment

    return max(1, min(10, score))


def _score_agency_affinity(
    agency_name: str | None,
    agency_preferences: list[GovContractAgencyPreference],
) -> tuple[int, list[str]]:
    if not agency_preferences:
        return DEFAULT_AGENCY_AFFINITY_SCORE, []

    normalized_agency_name = _normalize_text(agency_name)
    if not normalized_agency_name:
        return NON_MATCHING_AGENCY_AFFINITY_SCORE, []

    matched_preferences = [
        preference
        for preference in agency_preferences
        if _normalize_text(preference.agency_name) in normalized_agency_name
    ]
    if not matched_preferences:
        return NON_MATCHING_AGENCY_AFFINITY_SCORE, []

    return max(preference.weight for preference in matched_preferences), [
        preference.agency_name for preference in matched_preferences
    ]


def _build_score_breakdown(
    *,
    raw_score: int,
    parts: list[str | None],
    agency_name: str | None,
    agency_preferences: list[GovContractAgencyPreference],
    due_date: date | None,
    today: date,
) -> tuple[int, dict[str, int | list[str] | None]]:
    closeness_score = _normalize_match_score(raw_score)
    timing_score, days_until_due = _score_timing(due_date, today=today)
    competition_score = _score_competition(parts)
    agency_affinity_score, matched_agency_preferences = _score_agency_affinity(
        agency_name,
        agency_preferences,
    )
    priority_score = max(
        0,
        min(
            100,
            round(
                (
                    closeness_score * 0.40
                    + timing_score * 0.20
                    + competition_score * 0.15
                    + agency_affinity_score * 0.25
                )
                * 10
            ),
        ),
    )

    return priority_score, {
        "closeness": closeness_score,
        "timing": timing_score,
        "competition": competition_score,
        "agency_affinity": agency_affinity_score,
        "matched_agency_preferences": matched_agency_preferences,
        "days_until_due": days_until_due,
        "raw_match_score": raw_score,
    }


def build_default_keyword_rules() -> list[tuple[str, int]]:
    rules: list[tuple[str, int]] = []
    seen_phrases: set[str] = set()

    for phrase, weight in DEFAULT_MATCH_RULES:
        normalized_phrase = _normalize_text(phrase)
        if normalized_phrase and normalized_phrase not in seen_phrases:
            rules.append((phrase, weight))
            seen_phrases.add(normalized_phrase)

    for keyword in settings.gov_contract_extra_keywords:
        normalized_keyword = _normalize_text(keyword)
        if normalized_keyword and normalized_keyword not in seen_phrases:
            rules.append((keyword, DEFAULT_EXTRA_KEYWORD_WEIGHT))
            seen_phrases.add(normalized_keyword)

    return rules


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_open_contract(status_code: str | None, due_date: date | None, *, today: date) -> bool:
    if status_code not in OPEN_STATUS_CODES:
        return False
    if due_date is None:
        return True
    return due_date >= today


def _is_open_federal_contract(status_name: str | None) -> bool:
    normalized_status_name = _normalize_text(status_name)
    if not normalized_status_name:
        return True
    return normalized_status_name not in FEDERAL_FORECAST_CLOSED_STATUS_NAMES


def _is_open_grants_contract(
    status_name: str | None,
    due_date: date | None,
    archive_date: date | None,
    *,
    today: date,
) -> bool:
    normalized_status_name = _normalize_text(status_name)
    if normalized_status_name and normalized_status_name not in GRANTS_GOV_OPEN_STATUS_NAMES:
        return False
    if archive_date and archive_date < today:
        return False
    if due_date and due_date < today:
        return False
    return True


def _score_text_parts(parts: list[str | None], match_rules: list[tuple[str, int]]) -> tuple[int, list[str]]:
    haystack = _normalize_text(
        " ".join(part for part in parts if part)
    )
    score = 0
    matched_keywords: list[str] = []
    seen_phrases: set[str] = set()
    padded_haystack = f" {haystack} " if haystack else " "

    for phrase, weight in match_rules:
        normalized_phrase = _normalize_text(phrase)
        if (
            normalized_phrase
            and normalized_phrase not in seen_phrases
            and f" {normalized_phrase} " in padded_haystack
        ):
            matched_keywords.append(phrase)
            score += weight
            seen_phrases.add(normalized_phrase)

    return score, matched_keywords


def _payload_score_parts(raw_payload: dict[str, object] | dict[str, str] | None) -> list[str | None]:
    if not isinstance(raw_payload, dict):
        return []

    ordered_keys = (
        "body",
        "description",
        "summary_description",
        "organization",
        "department",
        "top_level_agency_name",
        "place_of_performance",
        "naics",
        "acquisition_strategy",
        "contract_type",
        "estimated_contract_value",
        "funding_instruments",
        "funding_categories",
        "funding_category_description",
        "applicant_types",
        "applicant_eligibility_description",
        "estimated_total_program_funding",
        "award_floor",
        "award_ceiling",
    )
    return [_clean(_strip_html(raw_payload.get(key))) for key in ordered_keys]


def _record_score_parts(record: GovContractSourceRecord) -> list[str | None]:
    return [
        record.title,
        record.agency_name,
        record.nigp_codes,
        *_payload_score_parts(record.raw_payload),
    ]


def _score_record(
    record: GovContractSourceRecord,
    match_rules: list[tuple[str, int]],
) -> tuple[int, list[str]]:
    return _score_text_parts(_record_score_parts(record), match_rules)


def _opportunity_score_parts(opportunity: GovContractOpportunity) -> list[str | None]:
    return [
        opportunity.title,
        opportunity.agency_name,
        opportunity.nigp_codes,
        *_payload_score_parts(opportunity.raw_payload),
    ]


def _score_opportunity(
    opportunity: GovContractOpportunity,
    match_rules: list[tuple[str, int]],
) -> tuple[int, list[str]]:
    return _score_text_parts(_opportunity_score_parts(opportunity), match_rules)


def _resolve_window(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    window_days: int | None = None,
) -> tuple[date, date]:
    days = window_days or settings.gov_contract_window_days
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=days - 1))
    if resolved_start > resolved_end:
        raise ValueError("start_date must be on or before end_date")
    return resolved_start, resolved_end


def _build_request_payload(start_date: date, end_date: date) -> dict[str, object]:
    return {
        "page": 1,
        "dateRange": "custom",
        "startDate": start_date.strftime("%m/%d/%Y"),
        "endDate": end_date.strftime("%m/%d/%Y"),
        "isCSV": True,
    }


def _build_contract_description(record: GovContractOpportunity, notes: str | None = None) -> str:
    source_label = SOURCE_LABELS.get(record.source, record.source)
    lines = [
        f"Public-sector opportunity sourced from {source_label}.",
        f"Title: {record.title}",
        f"Solicitation ID: {record.solicitation_id}",
    ]
    if record.agency_name:
        lines.append(f"Agency: {record.agency_name}")
    elif record.agency_number:
        lines.append(f"Agency Number: {record.agency_number}")
    if record.status_name:
        lines.append(f"Status: {record.status_name}")
    if record.posting_date:
        lines.append(f"Posting Date: {record.posting_date.isoformat()}")
    if record.due_date:
        due_line = f"Due Date: {record.due_date.isoformat()}"
        if record.due_time:
            due_line += f" at {record.due_time}"
        lines.append(due_line)
    if record.matched_keywords:
        lines.append(f"Matched Keywords: {', '.join(record.matched_keywords)}")
    if record.nigp_codes:
        lines.append(f"NIGP Codes: {record.nigp_codes}")
    contact_email = _clean((record.raw_payload or {}).get("sender_email")) or _clean(
        (record.raw_payload or {}).get("agency_email_address")
    )
    if contact_email:
        lines.append(f"Contact Email: {contact_email}")
    contract_type = _clean((record.raw_payload or {}).get("contract_type"))
    if contract_type:
        lines.append(f"Contract Type: {contract_type}")
    estimated_contract_value = _clean((record.raw_payload or {}).get("estimated_contract_value"))
    if estimated_contract_value:
        lines.append(f"Estimated Contract Value: {estimated_contract_value}")
    acquisition_strategy = _clean((record.raw_payload or {}).get("acquisition_strategy"))
    if acquisition_strategy:
        lines.append(f"Acquisition Strategy: {acquisition_strategy}")
    top_level_agency_name = _clean((record.raw_payload or {}).get("top_level_agency_name"))
    if top_level_agency_name:
        lines.append(f"Top-Level Agency: {top_level_agency_name}")
    funding_instruments = _clean((record.raw_payload or {}).get("funding_instruments"))
    if funding_instruments:
        lines.append(f"Funding Instruments: {funding_instruments}")
    funding_categories = _clean((record.raw_payload or {}).get("funding_categories"))
    if funding_categories:
        lines.append(f"Funding Categories: {funding_categories}")
    applicant_types = _clean((record.raw_payload or {}).get("applicant_types"))
    if applicant_types:
        lines.append(f"Applicant Types: {applicant_types}")
    estimated_total_program_funding = _clean((record.raw_payload or {}).get("estimated_total_program_funding"))
    if estimated_total_program_funding:
        lines.append(f"Estimated Total Program Funding: {estimated_total_program_funding}")
    award_floor = _clean((record.raw_payload or {}).get("award_floor"))
    if award_floor:
        lines.append(f"Award Floor: {award_floor}")
    award_ceiling = _clean((record.raw_payload or {}).get("award_ceiling"))
    if award_ceiling:
        lines.append(f"Award Ceiling: {award_ceiling}")
    summary_description = _clean(_strip_html((record.raw_payload or {}).get("summary_description")))
    if summary_description:
        lines.append(f"Summary: {summary_description}")
    additional_info_url = _clean((record.raw_payload or {}).get("additional_info_url"))
    if additional_info_url:
        lines.append(f"Additional Info URL: {additional_info_url}")
    performance_start_date = _clean((record.raw_payload or {}).get("performance_start_date"))
    if performance_start_date:
        lines.append(f"Performance Start Date: {performance_start_date}")
    contact_name = _clean((record.raw_payload or {}).get("contact_name"))
    if contact_name:
        lines.append(f"Point of Contact: {contact_name}")
    contact_phone = _clean((record.raw_payload or {}).get("contact_phone"))
    if contact_phone:
        lines.append(f"Contact Phone: {contact_phone}")
    lines.append(f"Source URL: {record.source_url}")
    if notes:
        lines.append(f"Operator Notes: {notes.strip()}")
    return "\n".join(lines)


def _derive_agency_lookup(response_payload: dict[str, object]) -> dict[str, str]:
    agency_lookup: dict[str, str] = {}
    for agency in response_payload.get("agencies", []):
        if not isinstance(agency, dict):
            continue
        agency_name = str(agency.get("agencyname") or "").strip()
        if not agency_name or " - " not in agency_name:
            continue
        _, agency_number = agency_name.rsplit(" - ", 1)
        agency_lookup[agency_number.strip()] = agency_name
    return agency_lookup


def _csv_rows_to_records(
    response_payload: dict[str, object],
    csv_text: str,
) -> list[GovContractSourceRecord]:
    agency_lookup = _derive_agency_lookup(response_payload)
    reader = csv.DictReader(io.StringIO(csv_text))
    records: list[GovContractSourceRecord] = []

    for row in reader:
        solicitation_id = (row.get("Solicitation ID") or "").strip()
        if not solicitation_id:
            continue
        agency_number = (row.get("Agency/Texas SmartBuy Member Number") or "").strip() or None
        records.append(
            GovContractSourceRecord(
                source_key=solicitation_id,
                solicitation_id=solicitation_id,
                source_url=f"{settings.gov_contract_source_base_url}/{quote(solicitation_id, safe='')}",
                title=(row.get("Name") or "").strip(),
                agency_name=agency_lookup.get(agency_number or "", agency_number),
                agency_number=agency_number,
                status_code=STATUS_NAME_TO_CODE.get(_normalize_text(row.get("Status"))),
                status_name=(row.get("Status") or "").strip() or None,
                due_date=_parse_date(row.get("Due Date")),
                due_time=(row.get("Due Time") or "").strip() or None,
                posting_date=_parse_date(row.get("Posting Date")),
                source_created_at=_parse_datetime(row.get("Created")),
                source_last_modified_at=_parse_datetime(row.get("Last Modified")),
                nigp_codes=(row.get("NIGP Codes") or "").strip() or None,
                raw_payload={key: value for key, value in row.items() if isinstance(value, str)},
            )
        )

    status_lookup = {
        line.get("solicitationId"): str(line.get("status") or "").strip() or None
        for line in response_payload.get("lines", [])
        if isinstance(line, dict)
    }
    for record in records:
        if record.solicitation_id in status_lookup:
            record.status_code = status_lookup[record.solicitation_id]

    return records


def fetch_txsmartbuy_contracts(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    window_days: int | None = None,
) -> GovContractFetchResult:
    resolved_start, resolved_end = _resolve_window(
        start_date=start_date,
        end_date=end_date,
        window_days=window_days,
    )
    payload = _build_request_payload(resolved_start, resolved_end)

    try:
        response = requests.post(
            settings.gov_contract_service_url,
            json=payload,
            timeout=settings.gov_contract_request_timeout_seconds,
        )
        response.raise_for_status()
        response_payload = response.json()
    except requests.RequestException as exc:
        raise GovContractSourceError(f"Failed to fetch ESBD contracts: {exc}") from exc
    except ValueError as exc:
        raise GovContractSourceError("ESBD returned an unreadable JSON payload") from exc

    csv_text = str(response_payload.get("csv") or "")
    if not csv_text:
        raise GovContractSourceError("ESBD response did not include CSV content")

    records = _csv_rows_to_records(response_payload, csv_text)
    return GovContractFetchResult(
        request_payload=payload,
        source_total_records=int(response_payload.get("totalRecordsFound") or len(records)),
        csv_text=csv_text,
        records=records,
    )


def _humanize_export_key(value: str) -> str:
    return value.split("_", 1)[-1].replace("_", " ").title()


def _federal_export_value(value: object | None) -> str:
    text = _clean(_strip_html(value))
    return text or ""


def _federal_export_csv(
    rows: list[dict[str, object]],
    *,
    view_labels: dict[str, str],
) -> str:
    header_keys: list[str] = []
    seen_keys: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen_keys:
                header_keys.append(key)
                seen_keys.add(key)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([view_labels.get(key, _humanize_export_key(key)) for key in header_keys])

    for row in rows:
        writer.writerow([_federal_export_value(row.get(key)) for key in header_keys])

    return output.getvalue()


def _build_federal_source_url(nid: str) -> str:
    return _format_source_url(
        settings.federal_contract_source_base_url,
        {"_a^g_nid": nid},
    )


def _build_federal_nigp_preview(
    *,
    naics: str | None,
    acquisition_strategy: str | None,
    contract_type: str | None,
    estimated_contract_value: str | None,
    place_of_performance: str | None,
) -> str | None:
    parts = [
        f"NAICS: {naics}" if naics else None,
        f"Acquisition Strategy: {acquisition_strategy}" if acquisition_strategy else None,
        f"Contract Type: {contract_type}" if contract_type else None,
        f"Estimated Value: {estimated_contract_value}" if estimated_contract_value else None,
        f"Performance: {place_of_performance}" if place_of_performance else None,
    ]
    joined = " | ".join(part for part in parts if part)
    return joined or None


def _federal_record_from_listing_item(item: dict[str, object]) -> GovContractSourceRecord | None:
    render = item.get("render")
    if not isinstance(render, dict):
        return None

    nid = _clean(str(render.get("nid") or item.get("nid") or ""))
    if not nid:
        return None

    department = _clean(_strip_html(render.get("field_result_id")))
    organization = _clean(_strip_html(render.get("field_organization")))
    agency_name = " / ".join(part for part in [department, organization] if part) or department or organization
    description = _clean(_strip_html(render.get("body")))
    award_status = _clean(_strip_html(render.get("field_award_status")))
    contract_type = _clean(_strip_html(render.get("field_contract_type")))
    estimated_award_fy = _clean(_strip_html(render.get("field_estimated_award_fy")))
    estimated_contract_value = _clean(_strip_html(render.get("field_estimated_contract_v_max")))
    naics = _clean(_strip_html(render.get("field_naics_code")))
    acquisition_strategy = _clean(_strip_html(render.get("field_acquisition_strategy")))
    place_of_performance = _clean(_strip_html(render.get("field_place_of_performance")))
    period_of_performance = _clean(_strip_html(render.get("field_period_of_performance")))
    source_listing_id = _clean(_strip_html(render.get("field_source_listing_id"))) or nid

    rank = item.get("rank") if isinstance(item.get("rank"), dict) else {}
    updated = rank.get("updated") if isinstance(rank.get("updated"), dict) else {}
    updated_at = _parse_unix_timestamp(updated.get("value"))
    created_at = _parse_source_listing_timestamp(source_listing_id) or updated_at
    performance_datetimes = _parse_embedded_datetimes(render.get("field_period_of_performance"))
    due_date = performance_datetimes[0].date() if performance_datetimes else None

    return GovContractSourceRecord(
        source_key=f"{FEDERAL_FORECAST_SOURCE_NAME}:{nid}",
        solicitation_id=source_listing_id,
        source_url=_build_federal_source_url(nid),
        title=_clean(_strip_html(render.get("title"))) or f"Federal Forecast {nid}",
        agency_name=agency_name,
        agency_number=None,
        status_code=None,
        status_name=award_status,
        due_date=due_date,
        due_time=None,
        posting_date=updated_at.date() if updated_at else None,
        source_created_at=created_at,
        source_last_modified_at=updated_at,
        nigp_codes=_build_federal_nigp_preview(
            naics=naics,
            acquisition_strategy=acquisition_strategy,
            contract_type=contract_type,
            estimated_contract_value=estimated_contract_value,
            place_of_performance=place_of_performance,
        ),
        raw_payload={
            "nid": nid,
            "source_listing_id": source_listing_id,
            "department": department,
            "organization": organization,
            "description": description,
            "award_status": award_status,
            "contract_type": contract_type,
            "estimated_award_fy": estimated_award_fy,
            "estimated_contract_value": estimated_contract_value,
            "naics": naics,
            "acquisition_strategy": acquisition_strategy,
            "place_of_performance": place_of_performance,
            "period_of_performance": period_of_performance,
        },
    )


def _fetch_federal_forecast_page(*, page: int, page_size: int) -> dict[str, object]:
    params = {
        "_format": FEDERAL_FORECAST_QUERY_FORMAT,
        "range": page_size,
        "page": page,
    }

    try:
        response = requests.get(
            settings.federal_contract_service_url,
            params=params,
            timeout=settings.federal_contract_request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise GovContractSourceError(f"Failed to fetch federal forecast contracts: {exc}") from exc
    except ValueError as exc:
        raise GovContractSourceError("Federal forecast returned an unreadable JSON payload") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("listing"), dict):
        raise GovContractSourceError("Federal forecast response did not include a listing payload")

    return payload


def fetch_federal_forecast_contracts() -> GovContractFetchResult:
    page_size = max(1, settings.federal_contract_page_size)
    first_page = _fetch_federal_forecast_page(page=1, page_size=page_size)
    listing = first_page.get("listing") or {}
    source_total_records = int(listing.get("total") or 0)
    total_pages = max(1, ceil(source_total_records / page_size)) if source_total_records else 1

    page_payloads = [first_page]
    for page_number in range(2, total_pages + 1):
        page_payloads.append(_fetch_federal_forecast_page(page=page_number, page_size=page_size))

    view_labels = {
        key: str(value.get("label") or "").strip()
        for key, value in (listing.get("view") or {}).items()
        if isinstance(value, dict)
    }
    export_rows: list[dict[str, object]] = []
    records: list[GovContractSourceRecord] = []

    for page_payload in page_payloads:
        page_listing = page_payload.get("listing") or {}
        items = page_listing.get("data") or {}
        if not isinstance(items, dict):
            continue

        for item in items.values():
            if not isinstance(item, dict):
                continue
            render = item.get("render")
            if isinstance(render, dict):
                export_rows.append(render)
            record = _federal_record_from_listing_item(item)
            if record is not None:
                records.append(record)

    csv_text = _federal_export_csv(export_rows, view_labels=view_labels)
    return GovContractFetchResult(
        request_payload={
            "page_size": page_size,
            "total_pages": total_pages,
            "source_total_records": source_total_records or len(records),
            "_format": FEDERAL_FORECAST_QUERY_FORMAT,
        },
        source_total_records=source_total_records or len(records),
        csv_text=csv_text,
        records=records,
    )


def _build_grants_nigp_preview(row: dict[str, str]) -> str | None:
    parts = [
        f"Funding Instruments: {_clean(row.get('funding_instruments'))}" if _clean(row.get("funding_instruments")) else None,
        f"Funding Categories: {_clean(row.get('funding_categories'))}" if _clean(row.get("funding_categories")) else None,
        f"Applicant Types: {_clean(row.get('applicant_types'))}" if _clean(row.get("applicant_types")) else None,
        f"Award Floor: {_clean(row.get('award_floor'))}" if _clean(row.get("award_floor")) else None,
        f"Award Ceiling: {_clean(row.get('award_ceiling'))}" if _clean(row.get("award_ceiling")) else None,
        f"Program Funding: {_clean(row.get('estimated_total_program_funding'))}"
        if _clean(row.get("estimated_total_program_funding"))
        else None,
    ]
    joined = " ; ".join(part for part in parts if part)
    return joined or None


def _grants_record_from_row(row: dict[str, str]) -> GovContractSourceRecord | None:
    opportunity_id = _clean(row.get("opportunity_id"))
    opportunity_number = _clean(row.get("opportunity_number")) or opportunity_id
    title = _clean(_strip_html(row.get("opportunity_title")))
    source_url = _clean(row.get("url")) or settings.grants_contract_source_base_url
    if not opportunity_number or not source_url or not title:
        return None

    agency_name = _clean(row.get("agency_name"))
    top_level_agency_name = _clean(row.get("top_level_agency_name"))
    summary_description = _clean(_strip_html(row.get("summary_description")))
    applicant_eligibility_description = _clean(_strip_html(row.get("applicant_eligibility_description")))
    agency_contact_description = _clean(_strip_html(row.get("agency_contact_description")))
    opportunity_status = _clean(row.get("opportunity_status"))
    close_date = _parse_iso_date(row.get("close_date"))
    forecasted_close_date = _parse_iso_date(row.get("forecasted_close_date"))
    post_date = _parse_iso_date(row.get("post_date"))
    forecasted_post_date = _parse_iso_date(row.get("forecasted_post_date"))
    due_date = close_date or forecasted_close_date
    posting_date = post_date or forecasted_post_date
    normalized_status = _normalize_text(opportunity_status)

    return GovContractSourceRecord(
        source_key=f"{GRANTS_GOV_SOURCE_NAME}:{opportunity_id or opportunity_number}",
        solicitation_id=opportunity_number,
        source_url=source_url,
        title=title,
        agency_name=agency_name,
        agency_number=_clean(row.get("agency_code")),
        status_code=STATUS_NAME_TO_CODE.get(normalized_status) or ("1" if normalized_status in GRANTS_GOV_OPEN_STATUS_NAMES else None),
        status_name=opportunity_status,
        due_date=due_date,
        due_time=None,
        posting_date=posting_date,
        source_created_at=_parse_feed_timestamp(row.get("created_at")),
        source_last_modified_at=_parse_feed_timestamp(row.get("updated_at")),
        nigp_codes=_build_grants_nigp_preview(row),
        raw_payload={
            "opportunity_id": opportunity_id,
            "description": summary_description,
            "summary_description": summary_description,
            "department": top_level_agency_name,
            "organization": agency_name,
            "top_level_agency_name": top_level_agency_name,
            "funding_instruments": _clean(row.get("funding_instruments")),
            "funding_categories": _clean(row.get("funding_categories")),
            "funding_category_description": _clean(_strip_html(row.get("funding_category_description"))),
            "applicant_types": _clean(row.get("applicant_types")),
            "applicant_eligibility_description": applicant_eligibility_description,
            "estimated_total_program_funding": _clean(row.get("estimated_total_program_funding")),
            "award_floor": _clean(row.get("award_floor")),
            "award_ceiling": _clean(row.get("award_ceiling")),
            "category": _clean(row.get("category")),
            "category_explanation": _clean(_strip_html(row.get("category_explanation"))),
            "agency_contact_description": agency_contact_description,
            "agency_email_address": _clean(row.get("agency_email_address")),
            "additional_info_url": _clean(row.get("additional_info_url")),
            "additional_info_url_description": _clean(_strip_html(row.get("additional_info_url_description"))),
            "opportunity_assistance_listings": _clean(row.get("opportunity_assistance_listings")),
            "is_cost_sharing": _parse_bool(row.get("is_cost_sharing")),
            "is_forecast": _parse_bool(row.get("is_forecast")),
            "forecasted_post_date": _clean(row.get("forecasted_post_date")),
            "forecasted_close_date": _clean(row.get("forecasted_close_date")),
            "forecasted_award_date": _clean(row.get("forecasted_award_date")),
            "forecasted_project_start_date": _clean(row.get("forecasted_project_start_date")),
            "archive_date": _clean(row.get("archive_date")),
            "fiscal_year": _clean(row.get("fiscal_year")),
        },
    )


def fetch_grants_contracts() -> GovContractFetchResult:
    try:
        response = requests.get(
            settings.grants_contract_export_url,
            timeout=settings.grants_contract_request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GovContractSourceError(f"Failed to fetch Grants.gov opportunities: {exc}") from exc

    csv_text = response.text
    if not csv_text.strip():
        raise GovContractSourceError("Grants.gov export did not include CSV content")

    reader = csv.DictReader(io.StringIO(csv_text))
    records: list[GovContractSourceRecord] = []
    for row in reader:
        record = _grants_record_from_row({key: value for key, value in row.items() if isinstance(value, str)})
        if record is not None:
            records.append(record)

    return GovContractFetchResult(
        request_payload={"export_url": settings.grants_contract_export_url},
        source_total_records=len(records),
        csv_text=csv_text,
        records=records,
    )


def _sba_subnet_export_csv(rows: list[dict[str, str]]) -> str:
    fieldnames = [
        "solicitation_id",
        "business_name",
        "description",
        "closing_date",
        "performance_start_date",
        "place_of_performance",
        "naics",
        "contact_name",
        "contact_email",
        "contact_phone",
        "source_url",
    ]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return output.getvalue()


def _sba_subnet_record_from_row(row: dict[str, str]) -> GovContractSourceRecord | None:
    source_url = _clean(row.get("source_url"))
    solicitation_id = _clean(row.get("solicitation_id"))
    description = _clean(_strip_html(row.get("description")))
    business_name = _clean(_strip_html(row.get("business_name")))
    title = description or solicitation_id
    if not source_url or not solicitation_id or not title:
        return None

    return GovContractSourceRecord(
        source_key=f"{SBA_SUBNET_SOURCE_NAME}:{source_url}",
        solicitation_id=solicitation_id,
        source_url=source_url,
        title=title,
        agency_name=business_name,
        agency_number=None,
        status_code="1",
        status_name="Posted",
        due_date=_parse_date(row.get("closing_date")),
        due_time=None,
        posting_date=None,
        source_created_at=None,
        source_last_modified_at=None,
        nigp_codes=_clean(_strip_html(row.get("naics"))),
        raw_payload={
            "description": description,
            "organization": business_name,
            "place_of_performance": _clean(_strip_html(row.get("place_of_performance"))),
            "naics": _clean(_strip_html(row.get("naics"))),
            "performance_start_date": _clean(row.get("performance_start_date")),
            "contact_name": _clean(_strip_html(row.get("contact_name"))),
            "contact_email": _clean(row.get("contact_email")),
            "contact_phone": _clean(row.get("contact_phone")),
            "source_url": source_url,
        },
    )


def _fetch_sba_subnet_page(url: str) -> tuple[list[dict[str, str]], str | None]:
    try:
        response = requests.get(
            url,
            timeout=settings.sba_subnet_request_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise GovContractSourceError(f"Failed to fetch SBA SUBNet opportunities: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    table_rows = soup.select("table tbody tr")
    rows: list[dict[str, str]] = []

    for row in table_rows:
        cells = row.select("td")
        if len(cells) < 6:
            continue

        description_cell = cells[0]
        detail_link = description_cell.select_one('a[href]:not([href^="mailto:"]):not([href^="tel:"])')
        solicitation_id = _clean(detail_link.get_text(" ", strip=True) if detail_link else description_cell.get_text(" ", strip=True))
        business_name = _clean(
            description_cell.select_one(".subnet_business_name").get_text(" ", strip=True)
            if description_cell.select_one(".subnet_business_name")
            else None
        )
        description = _clean(description_cell.select_one("p").get_text(" ", strip=True) if description_cell.select_one("p") else None)
        contact_cell = cells[5]
        contact_name = _clean(contact_cell.select_one('a[href^="mailto:"]').get_text(" ", strip=True) if contact_cell.select_one('a[href^="mailto:"]') else contact_cell.get_text(" ", strip=True))
        contact_email = None
        contact_phone = None
        email_link = contact_cell.select_one('a[href^="mailto:"]')
        if email_link and email_link.get("href"):
            contact_email = _clean(email_link.get("href").replace("mailto:", "", 1))
        phone_link = contact_cell.select_one('a[href^="tel:"]')
        if phone_link:
            contact_phone = _clean(phone_link.get_text(" ", strip=True))

        source_url = urljoin(url, detail_link.get("href")) if detail_link and detail_link.get("href") else url
        rows.append(
            {
                "solicitation_id": solicitation_id or "",
                "business_name": business_name or "",
                "description": description or "",
                "closing_date": cells[1].get_text(" ", strip=True),
                "performance_start_date": cells[2].get_text(" ", strip=True),
                "place_of_performance": cells[3].get_text(" ", strip=True),
                "naics": cells[4].get_text(" ", strip=True),
                "contact_name": contact_name or "",
                "contact_email": contact_email or "",
                "contact_phone": contact_phone or "",
                "source_url": source_url,
            }
        )

    next_link = soup.select_one("a.usa-pagination__link.usa-pagination__next-page")
    next_url = urljoin(url, next_link.get("href")) if next_link and next_link.get("href") else None
    return rows, next_url


def fetch_sba_subnet_contracts() -> GovContractFetchResult:
    rows: list[dict[str, str]] = []
    records: list[GovContractSourceRecord] = []
    next_url: str | None = settings.sba_subnet_source_url
    seen_urls: set[str] = set()
    pages_fetched = 0

    while next_url and next_url not in seen_urls:
        if pages_fetched >= max(1, settings.sba_subnet_max_pages):
            raise GovContractSourceError("SBA SUBNet pagination exceeded the configured page limit")
        seen_urls.add(next_url)
        page_rows, next_url = _fetch_sba_subnet_page(next_url)
        pages_fetched += 1
        if not page_rows:
            break
        rows.extend(page_rows)

    seen_source_keys: set[str] = set()
    for row in rows:
        record = _sba_subnet_record_from_row(row)
        if record is None or record.source_key in seen_source_keys:
            continue
        seen_source_keys.add(record.source_key)
        records.append(record)

    return GovContractFetchResult(
        request_payload={
            "source_url": settings.sba_subnet_source_url,
            "pages_fetched": pages_fetched,
        },
        source_total_records=len(records),
        csv_text=_sba_subnet_export_csv(rows),
        records=records,
    )


def fetch_gmail_rfq_feed(*, limit: int | None = None) -> dict[str, object]:
    if not settings.gmail_rfq_feed_enabled:
        raise GovContractSourceError("Gmail RFQ feed is not configured for this environment")

    params = {
        "label": settings.gmail_rfq_feed_label,
        "limit": limit or settings.gmail_rfq_feed_limit,
    }

    try:
        response = requests.get(
            settings.gmail_rfq_feed_url,
            params=params,
            timeout=settings.gmail_rfq_feed_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise GovContractSourceError(f"Failed to fetch Gmail RFQ feed: {exc}") from exc
    except ValueError as exc:
        raise GovContractSourceError("Gmail RFQ feed returned unreadable JSON") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise GovContractSourceError("Gmail RFQ feed did not include an items list")

    return payload


def _records_from_gmail_feed(feed_payload: dict[str, object]) -> list[GovContractSourceRecord]:
    records: list[GovContractSourceRecord] = []

    for item in feed_payload.get("items", []):
        if not isinstance(item, dict):
            continue

        title = _clean(item.get("title") or item.get("subject"))
        source_key = _clean(item.get("source_key"))
        source_url = _clean(item.get("source_url") or item.get("gmail_url"))
        if not title or not source_key or not source_url:
            continue

        status_name = _clean(item.get("status_name")) or "New"
        records.append(
            GovContractSourceRecord(
                source_key=source_key,
                solicitation_id=_clean(item.get("solicitation_id")) or source_key,
                source_url=source_url,
                title=title,
                agency_name=_clean(item.get("agency_name")),
                agency_number=None,
                status_code=STATUS_NAME_TO_CODE.get(_normalize_text(status_name), "4"),
                status_name=status_name,
                due_date=_parse_iso_date(_clean(item.get("due_date"))),
                due_time=_clean(item.get("due_time")),
                posting_date=_parse_iso_date(_clean(item.get("posting_date"))),
                source_created_at=_parse_feed_timestamp(_clean(item.get("message_at"))),
                source_last_modified_at=_parse_feed_timestamp(_clean(item.get("message_at"))),
                nigp_codes=None,
                raw_payload={key: value for key, value in item.items()},
            )
        )

    return records


def _gmail_record_sort_key(record: GovContractSourceRecord) -> tuple[datetime, date]:
    return (
        record.source_last_modified_at or record.source_created_at or datetime.min.replace(tzinfo=timezone.utc),
        record.posting_date or date.min,
    )


def _dedupe_gmail_records(records: list[GovContractSourceRecord]) -> list[GovContractSourceRecord]:
    latest_by_source_key: dict[str, GovContractSourceRecord] = {}

    for record in records:
        existing = latest_by_source_key.get(record.source_key)
        if existing is None or _gmail_record_sort_key(record) >= _gmail_record_sort_key(existing):
            latest_by_source_key[record.source_key] = record

    return sorted(latest_by_source_key.values(), key=_gmail_record_sort_key, reverse=True)


def _keyword_rules_statement():
    return select(GovContractKeywordRule).order_by(desc(GovContractKeywordRule.weight), GovContractKeywordRule.phrase)


def _agency_preferences_statement():
    return select(GovContractAgencyPreference).order_by(
        desc(GovContractAgencyPreference.weight),
        GovContractAgencyPreference.agency_name,
    )


def _seed_default_keyword_rules(db: Session) -> None:
    existing_keyword_id = db.scalars(select(GovContractKeywordRule.id).limit(1)).first()
    if existing_keyword_id is not None:
        return

    for phrase, weight in build_default_keyword_rules():
        db.add(
            GovContractKeywordRule(
                id=new_uuid(),
                phrase=phrase,
                weight=weight,
            )
        )

    db.commit()


def list_keyword_rules(db: Session) -> list[GovContractKeywordRule]:
    _seed_default_keyword_rules(db)
    return list(db.scalars(_keyword_rules_statement()).all())


def list_agency_preferences(db: Session) -> list[GovContractAgencyPreference]:
    return list(db.scalars(_agency_preferences_statement()).all())


def _load_match_rules(db: Session) -> list[tuple[str, int]]:
    return [(rule.phrase, rule.weight) for rule in list_keyword_rules(db)]


def _load_agency_preferences(db: Session) -> list[GovContractAgencyPreference]:
    return list_agency_preferences(db)


def _find_keyword_rule(db: Session, keyword_rule_id: str) -> GovContractKeywordRule | None:
    return db.get(GovContractKeywordRule, keyword_rule_id)


def _find_agency_preference(db: Session, agency_preference_id: str) -> GovContractAgencyPreference | None:
    return db.get(GovContractAgencyPreference, agency_preference_id)


def _validate_keyword_phrase(db: Session, phrase: str, *, exclude_id: str | None = None) -> str:
    cleaned_phrase = _clean(phrase)
    if not cleaned_phrase:
        raise ValueError("Keyword phrase is required")

    normalized_phrase = _normalize_text(cleaned_phrase)
    for rule in list_keyword_rules(db):
        if exclude_id and rule.id == exclude_id:
            continue
        if _normalize_text(rule.phrase) == normalized_phrase:
            raise ValueError("Keyword already exists")

    return cleaned_phrase


def _validate_agency_name(
    db: Session,
    agency_name: str,
    *,
    exclude_id: str | None = None,
) -> str:
    cleaned_agency_name = _clean(agency_name)
    if not cleaned_agency_name:
        raise ValueError("Agency name is required")

    normalized_agency_name = _normalize_text(cleaned_agency_name)
    for preference in list_agency_preferences(db):
        if exclude_id and preference.id == exclude_id:
            continue
        if _normalize_text(preference.agency_name) == normalized_agency_name:
            raise ValueError("Agency preference already exists")

    return cleaned_agency_name


def _append_payload_keywords(
    matched_keywords: list[str],
    raw_payload: dict[str, object] | dict[str, str] | None,
) -> tuple[list[str], int]:
    raw_keywords = raw_payload.get("matched_keywords") if isinstance(raw_payload, dict) else []
    payload_keyword_count = 0

    for keyword in raw_keywords or []:
        cleaned = _clean(keyword)
        if not cleaned:
            continue
        payload_keyword_count += 1
        if cleaned not in matched_keywords:
            matched_keywords.append(cleaned)

    return matched_keywords, payload_keyword_count


def _mark_run_failed(db: Session, run: GovContractImportRun, message: str) -> None:
    db.rollback()
    run.status = "failed"
    run.error_message = message
    run.completed_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()
    db.refresh(run)


def _score_gmail_record(
    record: GovContractSourceRecord,
    match_rules: list[tuple[str, int]],
) -> tuple[int, list[str]]:
    score, matched_keywords = _score_record(record, match_rules)
    matched_keywords, payload_keyword_count = _append_payload_keywords(matched_keywords, record.raw_payload)
    score = max(score + payload_keyword_count, settings.gmail_rfq_match_score_floor)
    return score, matched_keywords


def _is_open_gmail_record(record: GovContractSourceRecord, *, today: date) -> bool:
    if record.due_date is None:
        return True
    return record.due_date >= today


def _get_opportunity_by_source_key(db: Session, source_key: str) -> GovContractOpportunity | None:
    statement = select(GovContractOpportunity).where(GovContractOpportunity.source_key == source_key)
    return db.scalars(statement).first()


def get_contract_by_id(db: Session, contract_id: str) -> GovContractOpportunity | None:
    return db.get(GovContractOpportunity, contract_id)


def _score_gmail_opportunity(
    opportunity: GovContractOpportunity,
    match_rules: list[tuple[str, int]],
) -> tuple[int, list[str]]:
    score, matched_keywords = _score_opportunity(opportunity, match_rules)
    matched_keywords, payload_keyword_count = _append_payload_keywords(matched_keywords, opportunity.raw_payload)
    score = max(score + payload_keyword_count, settings.gmail_rfq_match_score_floor)
    return score, matched_keywords


def rescore_stored_opportunities(db: Session) -> None:
    match_rules = _load_match_rules(db)
    agency_preferences = _load_agency_preferences(db)
    today = date.today()
    statement = select(GovContractOpportunity)

    for opportunity in db.scalars(statement).all():
        score_parts = _opportunity_score_parts(opportunity)
        if opportunity.source == GMAIL_RFQ_SOURCE_NAME:
            score, matched_keywords = _score_gmail_opportunity(opportunity, match_rules)
            opportunity.is_open = _is_open_gmail_record(
                GovContractSourceRecord(
                    source_key=opportunity.source_key,
                    solicitation_id=opportunity.solicitation_id,
                    source_url=opportunity.source_url,
                    title=opportunity.title,
                    agency_name=opportunity.agency_name,
                    agency_number=opportunity.agency_number,
                    status_code=opportunity.status_code,
                    status_name=opportunity.status_name,
                    due_date=opportunity.due_date,
                    due_time=opportunity.due_time,
                    posting_date=opportunity.posting_date,
                    source_created_at=opportunity.source_created_at,
                    source_last_modified_at=opportunity.source_last_modified_at,
                    nigp_codes=opportunity.nigp_codes,
                    raw_payload=opportunity.raw_payload or {},
                ),
                today=today,
            )
            opportunity.is_match = True
        elif opportunity.source == FEDERAL_FORECAST_SOURCE_NAME:
            score, matched_keywords = _score_opportunity(opportunity, match_rules)
            opportunity.is_open = _is_open_federal_contract(opportunity.status_name)
            opportunity.is_match = score >= settings.gov_contract_match_min_score
        elif opportunity.source == GRANTS_GOV_SOURCE_NAME:
            score, matched_keywords = _score_opportunity(opportunity, match_rules)
            opportunity.is_open = _is_open_grants_contract(
                opportunity.status_name,
                opportunity.due_date,
                _parse_iso_date(_clean((opportunity.raw_payload or {}).get("archive_date"))),
                today=today,
            )
            opportunity.is_match = score >= settings.gov_contract_match_min_score
        else:
            score, matched_keywords = _score_opportunity(opportunity, match_rules)
            opportunity.is_open = _is_open_contract(opportunity.status_code, opportunity.due_date, today=today)
            opportunity.is_match = score >= settings.gov_contract_match_min_score

        priority_score, score_breakdown = _build_score_breakdown(
            raw_score=score,
            parts=score_parts,
            agency_name=opportunity.agency_name,
            agency_preferences=agency_preferences,
            due_date=opportunity.due_date,
            today=today,
        )
        opportunity.score = score
        opportunity.priority_score = priority_score
        opportunity.fit_bucket = _fit_bucket(score)
        opportunity.matched_keywords = matched_keywords
        opportunity.score_breakdown = score_breakdown
        db.add(opportunity)


def create_keyword_rule(db: Session, *, phrase: str, weight: int) -> GovContractKeywordRule:
    cleaned_phrase = _validate_keyword_phrase(db, phrase)
    keyword_rule = GovContractKeywordRule(
        id=new_uuid(),
        phrase=cleaned_phrase,
        weight=weight,
    )
    db.add(keyword_rule)
    db.flush()
    rescore_stored_opportunities(db)
    db.commit()
    db.refresh(keyword_rule)
    return keyword_rule


def create_agency_preference(
    db: Session,
    *,
    agency_name: str,
    weight: int,
) -> GovContractAgencyPreference:
    cleaned_agency_name = _validate_agency_name(db, agency_name)
    agency_preference = GovContractAgencyPreference(
        id=new_uuid(),
        agency_name=cleaned_agency_name,
        weight=weight,
    )
    db.add(agency_preference)
    db.flush()
    rescore_stored_opportunities(db)
    db.commit()
    db.refresh(agency_preference)
    return agency_preference


def update_keyword_rule(
    db: Session,
    keyword_rule_id: str,
    *,
    phrase: str,
    weight: int,
) -> GovContractKeywordRule:
    keyword_rule = _find_keyword_rule(db, keyword_rule_id)
    if keyword_rule is None:
        raise LookupError("Keyword not found")

    keyword_rule.phrase = _validate_keyword_phrase(db, phrase, exclude_id=keyword_rule_id)
    keyword_rule.weight = weight
    db.add(keyword_rule)
    db.flush()
    rescore_stored_opportunities(db)
    db.commit()
    db.refresh(keyword_rule)
    return keyword_rule


def update_agency_preference(
    db: Session,
    agency_preference_id: str,
    *,
    agency_name: str,
    weight: int,
) -> GovContractAgencyPreference:
    agency_preference = _find_agency_preference(db, agency_preference_id)
    if agency_preference is None:
        raise LookupError("Agency preference not found")

    agency_preference.agency_name = _validate_agency_name(
        db,
        agency_name,
        exclude_id=agency_preference_id,
    )
    agency_preference.weight = weight
    db.add(agency_preference)
    db.flush()
    rescore_stored_opportunities(db)
    db.commit()
    db.refresh(agency_preference)
    return agency_preference


def delete_keyword_rule(db: Session, keyword_rule_id: str) -> None:
    keyword_rule = _find_keyword_rule(db, keyword_rule_id)
    if keyword_rule is None:
        raise LookupError("Keyword not found")

    db.delete(keyword_rule)
    db.flush()
    rescore_stored_opportunities(db)
    db.commit()


def delete_agency_preference(db: Session, agency_preference_id: str) -> None:
    agency_preference = _find_agency_preference(db, agency_preference_id)
    if agency_preference is None:
        raise LookupError("Agency preference not found")

    db.delete(agency_preference)
    db.flush()
    rescore_stored_opportunities(db)
    db.commit()


def _persist_source_records(
    db: Session,
    *,
    run: GovContractImportRun,
    source_name: str,
    fetched: GovContractFetchResult,
    is_open_resolver,
) -> GovContractImportRun:
    match_rules = _load_match_rules(db)
    agency_preferences = _load_agency_preferences(db)
    run.request_payload = fetched.request_payload
    run.source_total_records = fetched.source_total_records
    run.total_records = len(fetched.records)
    run.csv_bytes = len(fetched.csv_text.encode("utf-8"))

    now = datetime.now(timezone.utc)
    today = date.today()
    matched_records = 0
    open_records = 0

    for record in fetched.records:
        score_parts = _record_score_parts(record)
        score, matched_keywords = _score_record(record, match_rules)
        is_match = score >= settings.gov_contract_match_min_score
        is_open = is_open_resolver(record, today=today)
        priority_score, score_breakdown = _build_score_breakdown(
            raw_score=score,
            parts=score_parts,
            agency_name=record.agency_name,
            agency_preferences=agency_preferences,
            due_date=record.due_date,
            today=today,
        )

        opportunity = _get_opportunity_by_source_key(db, record.source_key)
        if opportunity is None:
            opportunity = GovContractOpportunity(
                id=new_uuid(),
                source=source_name,
                source_key=record.source_key,
                first_seen_at=now,
            )

        opportunity.source_url = record.source_url
        opportunity.title = record.title
        opportunity.solicitation_id = record.solicitation_id
        opportunity.agency_name = record.agency_name
        opportunity.agency_number = record.agency_number
        opportunity.status_code = record.status_code
        opportunity.status_name = record.status_name
        opportunity.due_date = record.due_date
        opportunity.due_time = record.due_time
        opportunity.posting_date = record.posting_date
        opportunity.source_created_at = record.source_created_at
        opportunity.source_last_modified_at = record.source_last_modified_at
        opportunity.nigp_codes = record.nigp_codes
        opportunity.score = score
        opportunity.priority_score = priority_score
        opportunity.fit_bucket = _fit_bucket(score)
        opportunity.is_match = is_match
        opportunity.is_open = is_open
        opportunity.matched_keywords = matched_keywords
        opportunity.score_breakdown = score_breakdown
        opportunity.raw_payload = record.raw_payload
        opportunity.funnel_status = opportunity.funnel_status or "discovered"
        opportunity.last_seen_at = now

        db.add(opportunity)

        if is_match:
            matched_records += 1
        if is_open:
            open_records += 1

    run.status = "completed"
    run.matched_records = matched_records
    run.open_records = open_records
    run.completed_at = now
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def refresh_contracts(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    window_days: int | None = None,
) -> GovContractImportRun:
    resolved_start, resolved_end = _resolve_window(
        start_date=start_date,
        end_date=end_date,
        window_days=window_days,
    )
    run = GovContractImportRun(
        id=new_uuid(),
        source=SOURCE_NAME,
        status="running",
        window_start=resolved_start,
        window_end=resolved_end,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        fetched = fetch_txsmartbuy_contracts(
            start_date=resolved_start,
            end_date=resolved_end,
            window_days=window_days,
        )
        return _persist_source_records(
            db,
            run=run,
            source_name=SOURCE_NAME,
            fetched=fetched,
            is_open_resolver=lambda record, *, today: _is_open_contract(record.status_code, record.due_date, today=today),
        )
    except GovContractSourceError as exc:
        _mark_run_failed(db, run, str(exc))
        raise
    except Exception as exc:
        _mark_run_failed(db, run, str(exc))
        raise


def refresh_federal_contracts(db: Session) -> GovContractImportRun:
    today = date.today()
    run = GovContractImportRun(
        id=new_uuid(),
        source=FEDERAL_FORECAST_SOURCE_NAME,
        status="running",
        window_start=today,
        window_end=today,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        fetched = fetch_federal_forecast_contracts()
        return _persist_source_records(
            db,
            run=run,
            source_name=FEDERAL_FORECAST_SOURCE_NAME,
            fetched=fetched,
            is_open_resolver=lambda record, *, today: _is_open_federal_contract(record.status_name),
        )
    except GovContractSourceError as exc:
        _mark_run_failed(db, run, str(exc))
        raise
    except Exception as exc:
        _mark_run_failed(db, run, str(exc))
        raise


def refresh_grants_contracts(db: Session) -> GovContractImportRun:
    today = date.today()
    run = GovContractImportRun(
        id=new_uuid(),
        source=GRANTS_GOV_SOURCE_NAME,
        status="running",
        window_start=today,
        window_end=today,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        fetched = fetch_grants_contracts()
        return _persist_source_records(
            db,
            run=run,
            source_name=GRANTS_GOV_SOURCE_NAME,
            fetched=fetched,
            is_open_resolver=lambda record, *, today: _is_open_grants_contract(
                record.status_name,
                record.due_date,
                _parse_iso_date(_clean((record.raw_payload or {}).get("archive_date"))),
                today=today,
            ),
        )
    except GovContractSourceError as exc:
        _mark_run_failed(db, run, str(exc))
        raise
    except Exception as exc:
        _mark_run_failed(db, run, str(exc))
        raise


def refresh_sba_subnet_contracts(db: Session) -> GovContractImportRun:
    today = date.today()
    run = GovContractImportRun(
        id=new_uuid(),
        source=SBA_SUBNET_SOURCE_NAME,
        status="running",
        window_start=today,
        window_end=today,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        fetched = fetch_sba_subnet_contracts()
        return _persist_source_records(
            db,
            run=run,
            source_name=SBA_SUBNET_SOURCE_NAME,
            fetched=fetched,
            is_open_resolver=lambda record, *, today: _is_open_contract(record.status_code, record.due_date, today=today),
        )
    except GovContractSourceError as exc:
        _mark_run_failed(db, run, str(exc))
        raise
    except Exception as exc:
        _mark_run_failed(db, run, str(exc))
        raise


def refresh_gmail_contracts(db: Session, *, limit: int | None = None) -> GovContractImportRun:
    today = date.today()
    run = GovContractImportRun(
        id=new_uuid(),
        source=GMAIL_RFQ_SOURCE_NAME,
        status="running",
        window_start=today,
        window_end=today,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        feed_payload = fetch_gmail_rfq_feed(limit=limit)
        records = _dedupe_gmail_records(_records_from_gmail_feed(feed_payload))
        match_rules = _load_match_rules(db)
        agency_preferences = _load_agency_preferences(db)
        run.request_payload = {
            "feed_url": settings.gmail_rfq_feed_url,
            "label": settings.gmail_rfq_feed_label,
            "limit": limit or settings.gmail_rfq_feed_limit,
            "feed_count": feed_payload.get("count"),
        }
        run.source_total_records = int(feed_payload.get("count") or len(records))
        run.total_records = len(records)

        now = datetime.now(timezone.utc)
        matched_records = 0
        open_records = 0

        for record in records:
            score_parts = _record_score_parts(record)
            score, matched_keywords = _score_gmail_record(record, match_rules)
            is_open = _is_open_gmail_record(record, today=today)
            priority_score, score_breakdown = _build_score_breakdown(
                raw_score=score,
                parts=score_parts,
                agency_name=record.agency_name,
                agency_preferences=agency_preferences,
                due_date=record.due_date,
                today=today,
            )

            opportunity = _get_opportunity_by_source_key(db, record.source_key)
            if opportunity is None:
                opportunity = GovContractOpportunity(
                    id=new_uuid(),
                    source=GMAIL_RFQ_SOURCE_NAME,
                    source_key=record.source_key,
                    first_seen_at=now,
                )

            opportunity.source_url = record.source_url
            opportunity.title = record.title
            opportunity.solicitation_id = record.solicitation_id
            opportunity.agency_name = record.agency_name
            opportunity.agency_number = record.agency_number
            opportunity.status_code = record.status_code
            opportunity.status_name = record.status_name
            opportunity.due_date = record.due_date
            opportunity.due_time = record.due_time
            opportunity.posting_date = record.posting_date
            opportunity.source_created_at = record.source_created_at
            opportunity.source_last_modified_at = record.source_last_modified_at
            opportunity.nigp_codes = record.nigp_codes
            opportunity.score = score
            opportunity.priority_score = priority_score
            opportunity.fit_bucket = _fit_bucket(score)
            opportunity.is_match = True
            opportunity.is_open = is_open
            opportunity.matched_keywords = matched_keywords
            opportunity.score_breakdown = score_breakdown
            opportunity.raw_payload = record.raw_payload
            opportunity.funnel_status = opportunity.funnel_status or "discovered"
            opportunity.last_seen_at = now

            db.add(opportunity)
            matched_records += 1
            if is_open:
                open_records += 1

        run.status = "completed"
        run.matched_records = matched_records
        run.open_records = open_records
        run.completed_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    except GovContractSourceError as exc:
        _mark_run_failed(db, run, str(exc))
        raise
    except Exception as exc:
        _mark_run_failed(db, run, str(exc))
        raise


def list_contracts(
    db: Session,
    *,
    limit: int = 25,
    matches_only: bool = True,
    open_only: bool = True,
    min_priority_score: int = 0,
    source: str | None = None,
) -> list[GovContractOpportunity]:
    statement = select(GovContractOpportunity)
    if source:
        statement = statement.where(GovContractOpportunity.source == source)
    if matches_only:
        statement = statement.where(GovContractOpportunity.is_match.is_(True))
    if open_only:
        statement = statement.where(GovContractOpportunity.is_open.is_(True))
    if min_priority_score > 0:
        statement = statement.where(GovContractOpportunity.priority_score >= min_priority_score)
    statement = statement.order_by(
        desc(GovContractOpportunity.priority_score),
        desc(GovContractOpportunity.score),
        GovContractOpportunity.due_date,
        desc(GovContractOpportunity.posting_date),
        desc(GovContractOpportunity.last_seen_at),
    ).limit(limit)
    return list(db.scalars(statement).all())


def list_import_runs(db: Session, *, limit: int = 10) -> list[GovContractImportRun]:
    statement = select(GovContractImportRun).order_by(desc(GovContractImportRun.created_at)).limit(limit)
    return list(db.scalars(statement).all())


def export_contracts_csv(
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    window_days: int | None = None,
) -> tuple[str, date, date]:
    resolved_start, resolved_end = _resolve_window(
        start_date=start_date,
        end_date=end_date,
        window_days=window_days,
    )
    fetched = fetch_txsmartbuy_contracts(
        start_date=resolved_start,
        end_date=resolved_end,
        window_days=window_days,
    )
    return fetched.csv_text, resolved_start, resolved_end


def export_federal_contracts_csv() -> tuple[str, date]:
    fetched = fetch_federal_forecast_contracts()
    return fetched.csv_text, date.today()


def export_grants_contracts_csv() -> tuple[str, date]:
    fetched = fetch_grants_contracts()
    return fetched.csv_text, date.today()


def funnel_contract_to_crm(
    db: Session,
    contract_id: str,
    *,
    notes: str | None = None,
    force: bool = False,
) -> GovContractOpportunity:
    contract = get_contract_by_id(db, contract_id)
    if contract is None:
        raise ValueError("Contract not found")

    if contract.funnel_delivery_status == "delivered" and not force:
        return contract

    description = _build_contract_description(contract, notes=notes)
    source_context = {
        "source_site": "txsmartbuy.gov",
        "form_provider": "txsmartbuy",
        "form_name": "esbd_opportunity",
        "lead_source": "Government Contracts",
    }
    if contract.source == GMAIL_RFQ_SOURCE_NAME:
        source_context = {
            "source_site": "gmail",
            "form_provider": "gmail",
            "form_name": "rfq_opportunity",
            "lead_source": "Gmail RFQs",
        }
    elif contract.source == GRANTS_GOV_SOURCE_NAME:
        source_context = {
            "source_site": "simpler.grants.gov",
            "form_provider": "grants_gov",
            "form_name": "grant_opportunity",
            "lead_source": "Grants.gov Opportunities",
        }
    elif contract.source == SBA_SUBNET_SOURCE_NAME:
        source_context = {
            "source_site": "sba.gov",
            "form_provider": "sba_subnet",
            "form_name": "subcontracting_opportunity",
            "lead_source": "SBA SUBNet Opportunities",
        }

    payload = IntakeLeadCreate(
        source_site=source_context["source_site"],
        source_type="government_contract",
        form_provider=source_context["form_provider"],
        form_name=source_context["form_name"],
        external_entry_id=contract.solicitation_id,
        page_url=contract.source_url,
        business_context=DEFAULT_BUSINESS_CONTEXT,
        product_context=DEFAULT_PRODUCT_CONTEXT,
        metadata={
            "contract_id": contract.id,
            "source": contract.source,
            "source_label": SOURCE_LABELS.get(contract.source, contract.source),
            "source_key": contract.source_key,
            "title": contract.title,
            "agency_name": contract.agency_name,
            "agency_number": contract.agency_number,
            "status_name": contract.status_name,
            "due_date": contract.due_date.isoformat() if contract.due_date else None,
            "posting_date": contract.posting_date.isoformat() if contract.posting_date else None,
            "score": contract.score,
            "fit_bucket": contract.fit_bucket,
            "matched_keywords": list(contract.matched_keywords or []),
            "notes": _clean(notes),
        },
        lead={
            "firstName": "Government",
            "lastName": contract.solicitation_id,
            "description": description,
            "source": source_context["lead_source"],
            "businessUnit": DEFAULT_BUSINESS_CONTEXT,
            "productType": DEFAULT_PRODUCT_CONTEXT,
        },
    )

    submission = intake_service.create_lead_submission(db, payload)
    contract.funnel_status = "funneled" if submission.delivery_status == "delivered" else "failed"
    contract.funnel_submission_id = submission.id
    contract.funnel_delivery_target = submission.delivery_target
    contract.funnel_delivery_status = submission.delivery_status
    contract.funnel_record_id = submission.delivery_record_id
    contract.funnel_payload = submission.delivery_payload
    contract.funnel_response = submission.delivery_response
    contract.funneled_at = datetime.now(timezone.utc)

    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract
