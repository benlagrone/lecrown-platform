"""Read-only EspoCRM source discovery; portal adapters remain platform-owned."""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select

from app.models.gov_contract import GovContractTrackedSource
from app.services import espocrm_service
from app.utils.helpers import new_uuid


def enabled(settings) -> bool:
    mode = settings.gov_contract_source_catalog.strip().lower()
    if mode not in {"auto", "espocrm", "static"}:
        raise espocrm_service.EspoCRMError("GOV_CONTRACT_SOURCE_CATALOG must be auto, espocrm, or static")
    # Partial configuration must fail visibly, not switch back to the static list.
    return mode == "espocrm" or (mode == "auto" and (
        espocrm_service.has_base_url() or espocrm_service.has_credentials()
    ))


def normalized_url(value: str) -> str:
    try:
        url = urlsplit(value.strip())
        if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password:
            return ""
        if url.port not in {None, 80, 443}:
            return ""
        # CustomerOrg identifies distinct JAGGAER buyers; tracking parameters do not.
        query = urlencode(sorted((k, v) for k, v in parse_qsl(url.query) if k.lower() == "customerorg"))
        return urlunsplit(("https", url.hostname.lower(), url.path.rstrip("/"), query, ""))
    except (ValueError, AttributeError):
        return ""


def bonfire_origin(url: str) -> str | None:
    normalized = normalized_url(url)
    parsed = urlsplit(normalized)
    if re.fullmatch(r"[a-z0-9-]+\.bonfirehub\.com", parsed.hostname or ""):
        if parsed.path in {"", "/portal"}:
            return f"https://{parsed.hostname}"
    return None


def account_id(source: GovContractTrackedSource) -> str | None:
    match = re.match(r"EspoCRM Account: ([A-Za-z0-9_-]+)\n", source.notes or "")
    return match.group(1) if match else None


def is_source(account: dict) -> bool:
    description = str(account.get("description") or "").strip().lower()
    return bool(re.match(
        r"(?:\[rfp source capture |procurement opportunity source\.|portal source\.|"
        r"direct public solicitation page\.|public solicitation |public procurement |"
        r"portal / registration required\.)", description,
    ))


def resource_type(source: GovContractTrackedSource) -> str:
    if source.extraction_mode == "reference":
        return "vendor_registration"
    if source.extraction_mode == "overlap":
        return "buyer_resource"
    return "opportunity_feed"


def sync(db, *, definitions, core_sources: set[str]) -> dict[str, int]:
    accounts = espocrm_service.list_accounts()
    candidates = [account for account in accounts if is_source(account)]
    if not candidates:
        raise espocrm_service.EspoCRMError("EspoCRM returned no classified procurement sources; snapshot retained")
    existing = list(db.scalars(select(GovContractTrackedSource)).all())
    by_account = {account_id(row): row for row in existing if account_id(row)}
    by_url = {normalized_url(row.listing_url): row for row in existing if normalized_url(row.listing_url)}
    by_source = {row.source: row for row in existing}
    legacy = {normalized_url(item.listing_url): item for item in definitions}
    active: set[str] = set(core_sources)
    seen_urls: set[str] = set()
    duplicates = 0
    for account in sorted(candidates, key=lambda item: item["id"]):
        crm_id = account["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", crm_id):
            raise espocrm_service.EspoCRMError("EspoCRM source has an invalid Account ID")
        url = normalized_url(str(account.get("website") or ""))
        if url and url in seen_urls:
            duplicates += 1
            continue
        seen_urls.add(url)
        definition = legacy.get(url)
        row = by_account.get(crm_id) or by_url.get(url)
        if row is None and definition:
            row = by_source.get(definition.source)
        if row is None:
            row = GovContractTrackedSource(id=new_uuid(), source=definition.source if definition else f"espocrm_{crm_id}")
        description = str(account.get("description") or "")
        classification = re.search(r"Classification:\s*([^\n.]+)", description, re.I)
        classification = classification.group(1).strip().lower() if classification else ""
        platform = re.search(r"Platform:\s*([^\n.]+)", description, re.I)
        row.label = str(account.get("name") or crm_id)
        row.listing_url = url
        row.platform_name = platform.group(1).strip() if platform else "EspoCRM source"
        row.jurisdiction_type = definition.jurisdiction_type if definition else "buyer"
        row.extraction_mode = "manual_review"
        row.load_scope = "catalog_only"
        if "registration or contract program only" in classification:
            row.extraction_mode = "reference"
        elif "overlap" in classification:
            row.extraction_mode = "overlap"
        elif bonfire_origin(url):
            row.extraction_mode = "bonfire_public_json"
            row.load_scope = "opportunities"
        elif definition and definition.load_scope == "opportunities":
            row.extraction_mode = definition.extraction_mode
            row.load_scope = definition.load_scope
        elif definition and definition.resource_type != "opportunity_feed":
            row.extraction_mode = "reference"
        row.cadence = "weekly"
        row.active = True
        row.notes = f"EspoCRM Account: {crm_id}\n{description}"
        active.add(row.source)
        db.add(row)
    for row in existing:
        if row.source not in active:
            row.active = False
    db.commit()
    return {"accounts_read": len(accounts), "classified_sources": len(candidates),
            "duplicate_urls": duplicates, "catalog_sources": len(active - core_sources)}
