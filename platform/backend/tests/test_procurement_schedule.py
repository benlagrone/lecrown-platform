from __future__ import annotations

import hashlib
import hmac
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routes import gov_contract as routes
from app.services import gov_contract_service


class ProcurementScheduleTest(unittest.TestCase):
    def test_only_derived_scheduler_key_is_accepted(self):
        with patch.object(routes.settings, "secret_key", "test-secret"):
            key = hmac.new(b"test-secret", b"lecrown-procurement-scheduler-v1", hashlib.sha256).hexdigest()
            self.assertIsNone(routes.require_procurement_scheduler_key(key))
            for invalid in (None, "wrong-key"):
                with self.assertRaises(HTTPException) as error:
                    routes.require_procurement_scheduler_key(invalid)
                self.assertEqual(401, error.exception.status_code)

    def test_default_secret_cannot_enable_scheduler(self):
        with patch.object(routes.settings, "secret_key", "change-me-in-production"):
            with self.assertRaises(HTTPException) as error:
                routes.require_procurement_scheduler_key("any")
            self.assertEqual(503, error.exception.status_code)

    def test_refresh_returns_bounded_summary_and_preserves_lock_error(self):
        runs = [SimpleNamespace(status="completed", total_records=4),
                SimpleNamespace(status="blocked", total_records=0)]
        with patch.object(gov_contract_service, "refresh_tracked_procurement_sources", return_value=runs):
            self.assertEqual({"sources": 2, "completed": 1, "blocked": 1, "records": 4},
                             routes.scheduled_refresh(db=object()))
        with patch.object(gov_contract_service, "refresh_tracked_procurement_sources",
                          side_effect=gov_contract_service.GovContractSourceError("busy")):
            with self.assertRaises(HTTPException) as error:
                routes.scheduled_refresh(db=object())
            self.assertEqual(409, error.exception.status_code)
