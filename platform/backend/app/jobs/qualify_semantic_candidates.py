"""Batched source descriptions and private, local rating-trained semantic qualification."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.gov_contract import GovContractImportRun, GovContractOpportunity
from app.services import candidate_inbox
from app.services.crm_pursuit_sync import retry_seconds, write_private
from app.services.gov_contract_service import serialize_opportunity
from app.services.opportunity_descriptions import description_fields, parse_bonfire_description, public_bonfire_url
from app.services.semantic_fit import CAPABILITIES, Encoder, build_projection, label_hash, state_dir


class DescriptionRateLimit(RuntimeError):
    def __init__(self, delay):
        self.delay = delay


def browser_description(browser, url):
    """Ordinary headless public navigation: no login, stealth, proxy or challenge solving."""
    page = browser.new_page()
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=20000)
        if response and response.status == 429:
            raise DescriptionRateLimit(retry_seconds(response.headers.get("retry-after")))
        page.locator("#opportunityMetaSection, .opportunityMetaSection").wait_for(timeout=15000)
        # Read only visible public scope; never interact with verification or registration forms.
        return parse_bonfire_description(page.content()) if public_bonfire_url(page.url) else ""
    except DescriptionRateLimit:
        raise
    except Exception:
        return ""
    finally:
        page.close()


def enrich_descriptions(db, snapshot, limit=10, browser=None):
    now = datetime.now(timezone.utc)
    rated = {e["candidate"]["source_key"]: e.get("fit_feedback", {}).get("rating")
             for e in snapshot.get("candidates", {}).values()}
    retry_at = now
    for run in db.scalars(select(GovContractImportRun).where(GovContractImportRun.status == "blocked")):
        value = (run.request_payload or {}).get("bonfire_retry_at")
        if value:
            retry_at = max(retry_at, datetime.fromisoformat(value))
    if retry_at > now:
        return {"attempted": 0, "deferred_until": retry_at.isoformat()}
    records = list(db.scalars(select(GovContractOpportunity)))
    path = state_dir() / "projection.json"
    projected = json.loads(path.read_text()).get("records", {}) if path.exists() else {}
    def priority(row):
        checked = (row.raw_payload or {}).get("qualification_description", {}).get("checked_at", "")
        score = projected.get(row.source_key, {}).get("score", 0)
        bucket = 0 if not rated.get(row.source_key) and score >= 65 else 1 if rated.get(row.source_key) == "high" else 2
        return (not row.is_open, bool(checked), bucket, -score, checked, row.id)
    records.sort(key=priority)
    attempted, available = 0, 0
    for row in records:
        if attempted >= limit:
            break
        if not public_bonfire_url(row.source_url):
            continue
        previous = (row.raw_payload or {}).get("qualification_description", {})
        checked = previous.get("checked_at")
        if checked and now - datetime.fromisoformat(checked) < timedelta(days=1):
            continue
        if description_fields(row)["description_text"] and not previous:
            continue
        if attempted:
            time.sleep(6)
        attempted += 1
        item = {"url": row.source_url, "checked_at": now.isoformat(), "status": "unavailable", "text": ""}
        try:
            response = requests.get(row.source_url, timeout=12, allow_redirects=False, stream=True,
                                    headers={"User-Agent": "LeCrown-Opportunity-Qualification/1.0"})
            with response:
                if response.status_code == 429:
                    until = now + timedelta(seconds=retry_seconds(response.headers.get("Retry-After")))
                    db.add(GovContractImportRun(id=__import__("uuid").uuid4().hex, source="semantic_description", status="blocked",
                           window_start=now.date(), window_end=now.date(), completed_at=now,
                           request_payload={"bonfire_retry_at": until.isoformat()}, error_message="Public description requests rate limited; shared collection deferred."))
                    db.commit()
                    break
                if response.status_code in {401, 403}:
                    item["status"] = "blocked"
                    if browser is not None and response.status_code == 403:
                        text = browser_description(browser, row.source_url)
                        if text:
                            item.update(status="available", text=text)
                            available += 1
                elif response.status_code == 200:
                    body = bytearray()
                    for block in response.iter_content(65536):
                        body.extend(block)
                        if len(body) > 2_000_000:
                            raise ValueError("Public page exceeds the bounded response size")
                    text = parse_bonfire_description(body.decode("utf-8", errors="replace"))
                    if text:
                        item.update(status="available", text=text)
                        available += 1
            # Preserve a previous full description if this refresh is blocked; do not erase evidence.
            if not item["text"] and previous.get("text"):
                item["text"] = previous["text"]
                item["last_success_at"] = previous.get("last_success_at") or previous.get("checked_at")
        except DescriptionRateLimit as error:
            until = now + timedelta(seconds=error.delay)
            db.add(GovContractImportRun(id=__import__("uuid").uuid4().hex, source="semantic_description", status="blocked",
                   window_start=now.date(), window_end=now.date(), completed_at=now,
                   request_payload={"bonfire_retry_at": until.isoformat()}, error_message="Public description browser rate limited; shared collection deferred."))
            db.commit()
            break
        except (requests.RequestException, ValueError):
            item["status"] = "unavailable"
            item["text"] = previous.get("text", "")
        row.raw_payload = {**(row.raw_payload or {}), "qualification_description": item}
        db.commit()
    return {"attempted": attempted, "available": available}


def run_once(encoder, enrich=True, browser=None):
    snapshot = candidate_inbox.snapshot()
    collection = {"attempted": 0}
    if enrich:
        try:
            with candidate_inbox.collection_lock(), SessionLocal() as db:
                collection = enrich_descriptions(db, snapshot, max(1, min(10, int(os.getenv("SEMANTIC_DESCRIPTION_BATCH_SIZE", "10")))), browser)
        except candidate_inbox.CandidateInboxError:
            collection = {"attempted": 0, "deferred": "Another source batch owns the collection lock"}
    with SessionLocal() as db:
        records = [serialize_opportunity(row).model_dump(mode="json") for row in db.scalars(select(GovContractOpportunity))]
    candidate_inbox.capture(records)
    snapshot = candidate_inbox.snapshot()
    fingerprint = __import__("hashlib").sha256(json.dumps({"labels": label_hash(snapshot), "model": encoder.artifact_hash, "capabilities": CAPABILITIES.read_text(), "records": [
        [r["source_key"], r["title"], r["description_text"]] for r in sorted(records, key=lambda r: r["source_key"])]}, sort_keys=True).encode()).hexdigest()
    path = state_dir() / "projection.json"
    previous = json.loads(path.read_text()) if path.exists() else {}
    if previous.get("fingerprint") == fingerprint:
        projection = previous
    else:
        projection = build_projection(records, snapshot, encoder)
        projection["fingerprint"] = fingerprint
        write_private(path, projection)
    receipt = {"status": "ok", "checked_at": datetime.now(timezone.utc).isoformat(), "source_sha": os.getenv("SOURCE_SHA", "unknown"),
               "candidate_count": len(records), "training_count": projection["training_count"], "description_count": projection["description_count"],
               "semantic_high": sum(r["qualified"] for r in projection["records"].values()), "evaluation": projection["evaluation"], "collection": collection}
    write_private(state_dir() / "health.json", receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    directory = state_dir()
    if args.healthcheck:
        try:
            health = json.loads((directory / "health.json").read_text())
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(health["checked_at"])).total_seconds()
            raise SystemExit(0 if health["status"] == "ok" and 0 <= age <= 360 else 1)
        except (ValueError, OSError, KeyError):
            raise SystemExit(1)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(directory / "worker.lock", "a+") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        encoder = Encoder(directory)
        from playwright.sync_api import sync_playwright
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        while True:
            try:
                print(json.dumps(run_once(encoder, enrich=(directory / "projection.json").exists(), browser=browser)), flush=True)
            except Exception as error:
                write_private(directory / "health.json", {"status": "error", "error_type": type(error).__name__, "checked_at": datetime.now(timezone.utc).isoformat()})
                print(json.dumps({"status": "error", "error_type": type(error).__name__}), flush=True)
                if args.once:
                    raise SystemExit(1)
            if args.once:
                return
            time.sleep(60)


if __name__ == "__main__":
    main()
