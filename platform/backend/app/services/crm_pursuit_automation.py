"""Idempotent score-only CRM synchronization using the collector's existing evidence."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models.gov_contract import GovContractImportRun, GovContractOpportunity, GovContractTrackedSource
from app.services.crm_pursuit_scoring import crm_values, input_hash, metadata_lines, model_hash, rank
from app.services.crm_pursuit_sync import SCORE_FIELDS, write_private


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def read_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def catalog_evidence(records, db):
    """Only complete Bonfire snapshots establish absence; no extra portal requests."""
    sources = list(db.scalars(select(GovContractTrackedSource).where(
        GovContractTrackedSource.active.is_(True),
        GovContractTrackedSource.extraction_mode == "bonfire_public_json",
    )))
    by_host = {}
    for source in sources:
        latest = db.scalars(select(GovContractImportRun).where(
            GovContractImportRun.source == source.source,
            GovContractImportRun.status == "completed",
            GovContractImportRun.completed_at.is_not(None),
        ).order_by(GovContractImportRun.completed_at.desc()).limit(1)).first()
        if latest:
            host = urlparse((latest.request_payload or {}).get("url") or source.listing_url).hostname
            if not host or not re.fullmatch(r"[a-z0-9-]+\.bonfirehub\.com", host):
                continue
            if host not in by_host or latest.completed_at > by_host[host][1].completed_at:
                by_host[host] = (source, latest)
    evidence = {}
    for record in records:
        source_url = metadata_lines(record).get("Source URL", "")
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or parsed.hostname not in by_host:
            continue
        source, latest = by_host[parsed.hostname]
        canonical = f"https://{parsed.hostname}{parsed.path.rstrip('/')}"
        matching = db.scalars(select(GovContractOpportunity).where(
            GovContractOpportunity.source == source.source,
            GovContractOpportunity.source_url.in_([canonical, canonical + "/"]),
        )).first()
        # Other URLs on a buyer's site (e.g. reference pages) are not solicitations.
        if not re.fullmatch(r"/opportunities/\d+/?", parsed.path):
            continue
        checked = latest.completed_at.replace(tzinfo=timezone.utc).isoformat()
        listed = matching and matching.last_seen_at >= latest.completed_at
        evidence[record["id"]] = {
            "url": f"https://{parsed.hostname}/PublicPortal/getOpenPublicOpportunitiesSectionData",
            "checked_at": checked,
            "status": "listed_open" if listed else "not_in_open_list",
            "project": {"DateClose": (matching.raw_payload or {}).get("date_close") or str(matching.due_date)}
                       if listed and matching.due_date else None,
            "provenance": "Development collector complete public snapshot",
        }
    return evidence


def synchronize(client, model, directory: Path, evidence_loader, now=None):
    now = now or datetime.now(timezone.utc)
    previous = read_json(directory / "state.json", {})
    pending = read_json(directory / "pending.json", {})
    records = client.opportunities()
    inputs = {r["id"]: input_hash(r) for r in records}
    source_urls = {r["id"]: metadata_lines(r).get("Source URL") for r in records}
    evidence = evidence_loader(records)
    if evidence is None:
        if not previous:
            raise RuntimeError("Waiting for the active collector before the first evidence snapshot")
        # Collection holds the shared lock: retain only evidence for unchanged source URLs.
        evidence = {key: value for key, value in previous.get("evidence", {}).items()
                    if key in inputs and source_urls[key] == previous.get("source_urls", {}).get(key)}
    day = now.astimezone(ZoneInfo("America/Chicago")).date()
    ranked = rank(records, evidence, model, day)
    decisions, values = {}, {}
    for row in ranked:
        semantic = copy.deepcopy(row)
        semantic.get("evidence", {}).pop("checked_at", None)
        decision = digest({"row": semantic, "model": model_hash(model)})
        key = row["id"]
        decisions[key] = decision
        if previous.get("decisions", {}).get(key) == decision:
            values[key] = previous["values"][key]
        elif pending.get("decisions", {}).get(key) == decision:
            values[key] = pending["values"][key]
        else:
            values[key] = crm_values(row, model, now)
        if set(values[key]) != set(SCORE_FIELDS):
            raise ValueError("Automatic updates must contain only the nine scoring fields")
    state = {"version": 1, "model_hash": model_hash(model), "inputs": inputs, "decisions": decisions,
             "values": values, "evidence": evidence, "source_urls": source_urls, "as_of": day.isoformat()}
    changes = [r for r in records if any(r.get(k) != v for k, v in values[r["id"]].items())]
    if changes:
        fields = client.call("GET", "/Metadata")["entityDefs"]["Opportunity"]["fields"]
        if not set(SCORE_FIELDS) <= set(fields):
            raise ValueError("Existing scoring fields are missing; automation does not modify CRM schema")
        write_private(directory / "pending.json", state)
        write_private(directory / "before.json", changes)
    written = 0
    for original in changes:
        key = original["id"]
        path = "/Opportunity/" + key
        fresh = client.call("GET", path)
        if input_hash(fresh) != inputs[key]:
            raise ValueError("CRM business details changed during scoring; retry from a fresh snapshot")
        payload = values[key]
        if any(fresh.get(k) != v for k, v in payload.items()):
            try:
                client.call("PUT", path, json={**payload, "_prev": {k: fresh.get(k) for k in payload}})
            except RuntimeError:
                verified = client.call("GET", path)
                if any(verified.get(k) != v for k, v in payload.items()):
                    raise
            written += 1
        verified = client.call("GET", path)
        if input_hash(verified) != inputs[key] or any(verified.get(k) != v for k, v in payload.items()):
            raise ValueError("CRM score/protected-field readback did not match")
    final = client.opportunities() if changes else records
    if {r["id"]: input_hash(r) for r in final} != inputs or any(
        any(r.get(k) != v for k, v in values[r["id"]].items()) for r in final
    ):
        raise ValueError("CRM changed during portfolio verification; refresh required")
    state["last_success"] = now.isoformat()
    write_private(directory / "state.json", state)
    receipt = {"status": "ok", "checked_at": now.isoformat(), "count": len(records),
               "written": written, "model_version": model["version"], "model_hash": model_hash(model),
               "protected_fields_unchanged": True,
               "review_required": sum(r["status"] == "Review - unmapped" for r in ranked)}
    write_private(directory / "receipt.json", receipt)
    return receipt
