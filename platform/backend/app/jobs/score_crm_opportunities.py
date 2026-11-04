"""Persistent, score-only EspoCRM worker. Never creates Opportunities or changes auth."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import SessionLocal
from app.services.candidate_inbox import CandidateInboxError, collection_lock
from app.services.crm_pursuit_automation import catalog_evidence, read_json, synchronize
from app.services.crm_pursuit_sync import Client, MODEL_PATH, write_private


def evidence(records):
    try:
        with collection_lock(), SessionLocal() as db:
            return catalog_evidence(records, db)
    except CandidateInboxError:
        return None


def healthy(directory, now=None):
    status = read_json(directory / "health.json", {})
    now = now or datetime.now(timezone.utc)
    if status.get("status") != "ok" or not status.get("checked_at"):
        return False
    age = (now - datetime.fromisoformat(status["checked_at"])).total_seconds()
    return 0 <= age <= max(180, int(os.getenv("CRM_PURSUIT_POLL_SECONDS", "60")) * 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    directory = Path(os.getenv("CRM_PURSUIT_STATE_DIR", "/app/data/crm-pursuit-scoring"))
    if args.healthcheck:
        raise SystemExit(0 if healthy(directory) else 1)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    interval = max(30, int(os.getenv("CRM_PURSUIT_POLL_SECONDS", "60")))
    client, failures = None, 0
    with open(directory / "worker.lock", "a+") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            delay = interval
            try:
                client = client or Client()
                model = json.loads(MODEL_PATH.read_text())
                result = synchronize(client, model, directory, evidence)
                result["source_sha"] = os.getenv("SOURCE_SHA", "unknown")
                write_private(directory / "health.json", result)
                print(json.dumps(result), flush=True)
                failures = 0
            except Exception as exc:
                failures += 1
                delay = min(900, interval * (2 ** min(failures, 4)))
                delay = max(delay, getattr(exc, "retry_after", 0))
                result = {"status": "error", "error_type": type(exc).__name__,
                          "checked_at": datetime.now(timezone.utc).isoformat(), "retry_seconds": delay}
                write_private(directory / "health.json", result)
                print(json.dumps(result), flush=True)
                if client:
                    client.session.close()
                client = None
                if args.once:
                    raise SystemExit(1)
            if args.once:
                return
            time.sleep(delay)


if __name__ == "__main__":
    main()
