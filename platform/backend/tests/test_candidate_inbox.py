from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pydantic import ValidationError

from app.schemas.gov_contract import GovContractPromotionRequest
from app.services import candidate_inbox as inbox, espocrm_service as espo
from app.core.database import Base
from app.models.gov_contract import GovContractOpportunity
from app.services import gov_contract_service


class CandidateInboxTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "candidates.json"
        self.setting = patch.object(inbox.settings, "procurement_candidate_json_path", str(self.path))
        self.setting.start()
        self.record = {"id": "local-1", "source_key": "buyer:rfp-1", "title": "Construction management"}
        self.marker = f"ProcurementCandidate: {inbox.candidate_id(self.record['source_key'])}"
        self.payload = {"name": "Construction management", "amount": 25000, "amountCurrency": "USD", "closeDate": "2027-01-01", "stage": "Prospecting", "description": "User-reviewed candidate"}

    def tearDown(self):
        self.setting.stop()
        self.directory.cleanup()

    def test_capture_is_local_deduplicated_and_preserves_promotion(self):
        with patch.object(espo, "create_opportunity") as create:
            inbox.capture([self.record, self.record])
            self.assertEqual(1, len(inbox.snapshot()["candidates"]))
            create.assert_not_called()
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)

    def test_stored_candidate_promotes_to_opportunity_not_lead(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                row = GovContractOpportunity(id="local-1", source="test", source_key=self.record["source_key"],
                    source_url="https://buyer.example/rfp/1", title=self.record["title"], solicitation_id="RFP-1")
                db.add(row)
                db.commit()
                request = GovContractPromotionRequest(confirmed=True, amount=25000, close_date="2027-01-01")
                with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", return_value={"id": "crm-1"}) as create, patch.object(espo, "get_opportunity", return_value={"id": "crm-1", "description": self.marker}), patch.object(espo, "create_lead") as create_lead:
                    result = gov_contract_service.promote_candidate_to_crm(db, row.id, request)
                self.assertEqual("espocrm_opportunity", result.funnel_delivery_target)
                self.assertEqual("delivered", result.funnel_delivery_status)
                self.assertEqual(25000, create.call_args.args[0]["amount"])
                create_lead.assert_not_called()
                saved = next(iter(inbox.snapshot()["candidates"].values()))
                self.assertEqual("promoted", saved["promotion"]["status"])
                self.assertEqual("crm-1", saved["candidate"]["funnel_record_id"])
        finally:
            engine.dispose()

    def test_selection_creates_opportunity_once_and_verifies_it(self):
        inbox.capture([self.record])
        with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", return_value={"id": "crm-1"}) as create, patch.object(espo, "get_opportunity", return_value={"id": "crm-1", "description": self.marker}) as get:
            first = inbox.promote(self.record["source_key"], self.payload)
            inbox.capture([{**self.record, "title": "Updated source title"}])
            second = inbox.promote(self.record["source_key"], self.payload)
        create.assert_called_once()
        self.assertEqual(2, get.call_count)
        self.assertEqual("promoted", first["status"])
        self.assertEqual("crm-1", second["crm_record_id"])
        self.assertTrue(create.call_args.args[0]["description"].startswith(self.marker))

    def test_uncertain_write_is_not_blindly_retried(self):
        inbox.capture([self.record])
        with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", side_effect=espo.EspoCRMError("timeout")) as create:
            with self.assertRaises(inbox.CandidateInboxError):
                inbox.promote(self.record["source_key"], self.payload)
            with self.assertRaisesRegex(inbox.CandidateInboxError, "uncertain"):
                inbox.promote(self.record["source_key"], self.payload)
        create.assert_called_once()
        receipt = next(iter(inbox.snapshot()["candidates"].values()))["promotion"]
        self.assertEqual("uncertain", receipt["status"])
        with patch.object(espo, "find_opportunity", return_value={"id": "recovered"}), patch.object(espo, "create_opportunity") as create, patch.object(espo, "get_opportunity", return_value={"id": "recovered", "description": self.marker}):
            result = inbox.promote(self.record["source_key"], self.payload)
        self.assertEqual("recovered", result["crm_record_id"])
        create.assert_not_called()

    def test_verification_failure_retains_record_id_for_safe_retry(self):
        inbox.capture([self.record])
        with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", return_value={"id": "crm-1"}), patch.object(espo, "get_opportunity", side_effect=espo.EspoCRMError("read unavailable")):
            with self.assertRaises(inbox.CandidateInboxError):
                inbox.promote(self.record["source_key"], self.payload)
        with patch.object(espo, "create_opportunity") as create, patch.object(espo, "get_opportunity", return_value={"id": "crm-1", "description": self.marker}):
            self.assertEqual("crm-1", inbox.promote(self.record["source_key"], self.payload)["crm_record_id"])
        create.assert_not_called()

    def test_concurrent_promotion_creates_one_record(self):
        inbox.capture([self.record])
        with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", return_value={"id": "crm-1"}) as create, patch.object(espo, "get_opportunity", return_value={"id": "crm-1", "description": self.marker}), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: inbox.promote(self.record["source_key"], self.payload), range(2)))
        create.assert_called_once()
        self.assertEqual(["crm-1", "crm-1"], [item["crm_record_id"] for item in results])

    def test_corrupt_inbox_is_not_overwritten(self):
        self.path.write_text("not json", encoding="utf-8")
        with self.assertRaises(inbox.CandidateInboxError):
            inbox.capture([self.record])
        self.assertEqual("not json", self.path.read_text(encoding="utf-8"))

    def test_collection_lock_prevents_overlapping_batches(self):
        with inbox.collection_lock():
            with self.assertRaisesRegex(inbox.CandidateInboxError, "already running"):
                with inbox.collection_lock():
                    pass
        with inbox.collection_lock():
            pass

    def test_promotion_requires_confirmation_and_valid_estimates_when_supplied(self):
        for payload in ({}, {"confirmed": False, "amount": 1, "close_date": "2027-01-01"},
                        {"confirmed": True, "amount": float("nan"), "close_date": "2027-01-01"},
                        {"confirmed": True, "amount": -1, "close_date": "2027-01-01"}):
            with self.assertRaises(ValidationError):
                GovContractPromotionRequest(**payload)

    def test_prospect_allows_unknowns_but_later_stages_require_estimates(self):
        for values in ({}, {"amount": None, "close_date": None}, {"amount": 25000},
                       {"close_date": "2027-01-01"}):
            request = GovContractPromotionRequest(confirmed=True, **values)
            self.assertEqual("Prospecting", request.stage)
        self.assertIsNone(GovContractPromotionRequest(confirmed=True).amount)
        self.assertIsNone(GovContractPromotionRequest(confirmed=True).close_date)
        for stage in ("Qualification", "Proposal", "Negotiation"):
            for values in ({}, {"amount": 25000}, {"close_date": "2027-01-01"}):
                with self.subTest(stage=stage, values=values), self.assertRaises(ValidationError):
                    GovContractPromotionRequest(confirmed=True, stage=stage, **values)
            request = GovContractPromotionRequest(confirmed=True, stage=stage, amount=0, close_date="2027-01-01")
            self.assertEqual(0, request.amount)

    def test_prospect_payload_preserves_unknown_or_explicit_estimates(self):
        from datetime import date

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as db:
                for index, values in enumerate(({}, {"amount": 0}, {"amount": 25000},
                                                {"close_date": "2027-01-01"},
                                                {"amount": 25000, "close_date": "2027-01-01"})):
                    with self.subTest(values=values):
                        row = GovContractOpportunity(id=f"prospect-{index}", source="test",
                            source_key=f"prospect-{index}", source_url="https://buyer.example/rfp/1",
                            title="Software development", solicitation_id=f"RFP-{index}",
                            due_date=date(2026, 11, 15))
                        db.add(row)
                        db.commit()
                        marker = f"ProcurementCandidate: {inbox.candidate_id(row.source_key)}"
                        request = GovContractPromotionRequest(confirmed=True, **values)
                        with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", return_value={"id": f"crm-{index}"}) as create, patch.object(espo, "get_opportunity", return_value={"id": f"crm-{index}", "description": marker}):
                            gov_contract_service.promote_candidate_to_crm(db, row.id, request)
                        payload = create.call_args.args[0]
                        self.assertEqual(values.get("amount"), payload["amount"])
                        self.assertEqual(values.get("close_date"), payload["closeDate"])
                        self.assertNotEqual("2026-11-15", payload["closeDate"])
                        self.assertEqual("Prospecting", payload["stage"])
                        if "amount" in values:
                            self.assertEqual("USD", payload["amountCurrency"])
                        else:
                            self.assertNotIn("amountCurrency", payload)
                            self.assertIn("Estimated USD value: unknown", payload["description"])
                        if "close_date" not in values:
                            self.assertIn("Expected close date: unknown", payload["description"])
                        self.assertNotIn("Estimated USD value and expected close date reviewed", payload["description"])
                        saved = inbox.snapshot()["candidates"][inbox.candidate_id(row.source_key)]
                        self.assertEqual(values.get("amount"), saved["promotion"]["payload"]["amount"])
                        self.assertEqual(values.get("close_date"), saved["promotion"]["payload"]["closeDate"])
        finally:
            engine.dispose()

    def test_definite_rejection_can_be_corrected_without_uncertain_retry(self):
        inbox.capture([self.record])
        with patch.object(espo, "find_opportunity", return_value=None), patch.object(espo, "create_opportunity", side_effect=espo.EspoCRMError("invalid field", status_code=400)):
            with self.assertRaises(inbox.CandidateInboxError):
                inbox.promote(self.record["source_key"], self.payload)
        receipt = next(iter(inbox.snapshot()["candidates"].values()))["promotion"]
        self.assertEqual("failed", receipt["status"])


if __name__ == "__main__":
    unittest.main()
