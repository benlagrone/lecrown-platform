"""Promote verified semantic High fits to EspoCRM without giving the qualifier CRM credentials."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.database import SessionLocal
from app.services import candidate_inbox
from app.services.crm_pursuit_sync import write_private
from app.services.gov_contract_service import auto_promote_semantic_qualified


def healthy(directory, now=None):
    try:
        health = json.loads((directory / "health.json").read_text())
        now = now or datetime.now(timezone.utc)
        age = (now - datetime.fromisoformat(health["checked_at"])).total_seconds()
        return health.get("status") == "ok" and 0 <= age <= 360
    except (KeyError, OSError, ValueError):
        return False


def run_once():
    snapshot = candidate_inbox.snapshot()
    with SessionLocal() as db:
        result = auto_promote_semantic_qualified(db, snapshot)
    return {**result, "checked_at": datetime.now(timezone.utc).isoformat(), "source_sha": os.getenv("SOURCE_SHA", "unknown")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--healthcheck", action="store_true")
    args = parser.parse_args()
    directory = Path(os.getenv("SEMANTIC_PROMOTION_STATE_DIR", "/app/data/semantic-promotion"))
    if args.healthcheck:
        raise SystemExit(0 if healthy(directory) else 1)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    interval = max(30, int(os.getenv("SEMANTIC_PROMOTION_POLL_SECONDS", "60")))
    with open(directory / "worker.lock", "a+") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                receipt = run_once()
                write_private(directory / "health.json", receipt)
                print(json.dumps(receipt), flush=True)
            except Exception as exc:
                receipt = {"status": "error", "error_type": type(exc).__name__, "checked_at": datetime.now(timezone.utc).isoformat(),
                           "source_sha": os.getenv("SOURCE_SHA", "unknown")}
                write_private(directory / "health.json", receipt)
                print(json.dumps(receipt), flush=True)
                if args.once:
                    raise SystemExit(1)
            if args.once:
                return
            time.sleep(interval)


if __name__ == "__main__":
    main()
