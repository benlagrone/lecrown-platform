#!/usr/bin/env python3
"""Compatibility entry point for the packaged, manual CRM pursuit scoring CLI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "platform/backend"))
from app.services.crm_pursuit_sync import *  # noqa: F403

if __name__ == "__main__":
    main()
