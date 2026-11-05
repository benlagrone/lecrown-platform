"""Sextant launchd trigger for Development's bounded portal collector."""
from __future__ import annotations

import fcntl
import json
from pathlib import Path
import stat
import sys
import urllib.request


KEY_PATH = Path.home() / ".config/lecrown-development/procurement-scheduler-key"
STATE_PATH = Path.home() / ".local/state/lecrown-development"
URL = "https://api.lecrowndevelopment.com/contracts/scheduled-refresh"


def main() -> int:
    if stat.S_IMODE(KEY_PATH.stat().st_mode) & 0o077:
        raise RuntimeError("Scheduler key must not be group- or world-readable")
    key = KEY_PATH.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("Scheduler key is empty")
    STATE_PATH.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (STATE_PATH / "refresh.lock").open("a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Previous procurement refresh is still running", flush=True)
            return 0
        request = urllib.request.Request(URL, method="POST", headers={
            "X-Procurement-Scheduler-Key": key,
            "Accept": "application/json",
        })
        with urllib.request.urlopen(request, timeout=175) as response:
            result = json.load(response)
        print(json.dumps({"status": "completed", **result}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Procurement refresh failed: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
