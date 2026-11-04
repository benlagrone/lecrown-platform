from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from app.services.crm_pursuit_scoring import assessment, crm_values, input_hash, rank, validate_model

ROOT = Path(__file__).resolve().parents[3]
MODEL = json.loads((ROOT / "data/crm-pursuit-model.json").read_text())
TODAY = date(2026, 11, 4)


def opportunity(identifier="a", name="Requirements Database Management System", status="Open Opportunity", solicitation="RFP-1", due="2026-11-18"):
    return {"id": identifier, "name": name, "stage": "Prospecting", "amount": None, "closeDate": None, "probability": 10,
            "description": f"Status: {status}\nSolicitation ID: {solicitation}\nDue Date: {due}\nSource URL: https://buyer.bonfirehub.com/opportunities/1"}


def evidence(identifier="a", status="listed_open", checked="2026-11-04T12:00:00+00:00"):
    return {identifier: {"status": status, "checked_at": checked, "project": {"DateClose": "2026-11-18 21:00:00"}}}


class PursuitScoringTest(unittest.TestCase):
    def test_model_is_valid(self):
        validate_model(MODEL)

    def test_finances_are_unknown_not_invented(self):
        record = opportunity()
        original = copy.deepcopy(record)
        row = assessment(record, evidence(), MODEL, TODAY)
        self.assertIsNone(row["win_probability_percent"])
        self.assertIsNone(row["financial_profit_usd"])
        self.assertEqual(0, row["assumed_software_contractor_cost_usd"])
        self.assertEqual("Low", row["confidence"])
        self.assertEqual(original, record)

    def test_primary_bids_sort_before_subcontracting(self):
        prime = opportunity("prime", "Cellular Therapy Lab Software")
        sub = opportunity("sub", "Requirements Database Management System", status="Subcontract opportunity")
        rows = rank([sub, prime], {**evidence("prime"), **evidence("sub")}, MODEL, TODAY)
        self.assertEqual("prime", rows[0]["id"])
        self.assertEqual("Sub - qualify", rows[1]["status"])

    def test_forecast_and_rfi_are_capture_not_paid_bids(self):
        forecast = opportunity(status="Forecast")
        rfi = opportunity(solicitation="RFI-27-00004")
        for record in [forecast, rfi]:
            self.assertEqual("Prime - capture", assessment(record, evidence(), MODEL, TODAY)["status"])

    def test_closed_or_missing_open_record_cannot_win_on_keywords(self):
        closed = opportunity("closed", "AI Innovation Challenge")
        live = opportunity("live", "Cellular Therapy Lab Software")
        rows = rank([closed, live], {**evidence("closed", "not_in_open_list"), **evidence("live")}, MODEL, TODAY)
        self.assertEqual("live", rows[0]["id"])
        self.assertEqual("Hold - not listed open", rows[1]["status"])

    def test_stale_evidence_does_not_establish_bid_availability(self):
        row = assessment(opportunity(), evidence(checked="2026-10-28T12:00:00+00:00"), MODEL, TODAY)
        self.assertEqual("Prime - source review", row["status"])
        self.assertEqual("unavailable", row["public_status"])

    def test_source_date_replaces_stored_deadline_without_changing_crm(self):
        record = opportunity(due="2026-10-01")
        row = assessment(record, evidence(), MODEL, TODAY)
        self.assertEqual("2026-11-18", row["due_date"])
        self.assertEqual("Prime - qualify", row["status"])
        self.assertIn("2026-10-01", record["description"])

    def test_energy_integration_is_in_scope_without_inventing_field_quotes(self):
        row = assessment(opportunity(name="Electric Vehicle Consulting and Charging Infrastructure Installation"), evidence(), MODEL, TODAY)
        self.assertEqual("energy_integration", row["profile"])
        self.assertEqual("Prime - qualify", row["status"])
        self.assertTrue(any("separately quoted" in flag for flag in row["flags"]))
        self.assertIsNone(row["financial_profit_usd"])

    def test_unknown_scope_remains_unscored(self):
        row = assessment(opportunity(name="New unreviewed scope"), evidence(), MODEL, TODAY)
        self.assertIsNone(row["priority"])
        self.assertEqual("Review - unmapped", row["status"])

    def test_score_payload_does_not_modify_business_fields(self):
        row = rank([opportunity()], evidence(), MODEL, TODAY)[0]
        payload = crm_values(row, MODEL, datetime(2026, 11, 4, tzinfo=timezone.utc))
        self.assertTrue(all(key.startswith("cPursuit") or key in {"cWinLikelihoodScore", "cProfitabilityPotential", "cStrategicPotential"} for key in payload))
        self.assertFalse(set(payload) & {"amount", "closeDate", "stage", "probability", "description", "name"})
        self.assertIn("NOT CALIBRATED WIN PERCENTAGES", payload["cPursuitAssessment"])
        self.assertNotIn("2,875", payload["cPursuitAssessment"])
        self.assertNotIn("36/hour", payload["cPursuitAssessment"])

    def test_duplicates_and_invalid_model_fail_closed(self):
        with self.assertRaises(ValueError):
            rank([opportunity(), opportunity()], evidence(), MODEL, TODAY)
        bad = copy.deepcopy(MODEL)
        bad["weights"]["win"] = 10
        with self.assertRaises(ValueError):
            validate_model(bad)

    def test_input_hash_ignores_scores_but_tracks_protected_content(self):
        record = opportunity()
        self.assertEqual(input_hash(record), input_hash({**record, "cPursuitRank": 2}))
        self.assertNotEqual(input_hash(record), input_hash({**record, "amount": 100}))


class ApplySafetyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("pursuit_cli", ROOT / "scripts/score-crm-opportunities.py")
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def test_changed_input_aborts_before_any_write(self):
        class Client:
            def opportunities(self):
                return [opportunity(name="Changed title")]
            def call(self, *args, **kwargs):
                raise AssertionError("No CRM call expected after content mismatch")
        from app.services.crm_pursuit_scoring import model_hash
        plan = {"created_at": datetime.now(timezone.utc).isoformat(), "model_hash": model_hash(MODEL),
                "count": 1, "inputs": {"a": input_hash(opportunity())}, "updates": {}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "changed since preview"):
                self.cli.apply(Client(), MODEL, path, Path(directory), 1, False)

    def test_non_score_payload_is_rejected_before_any_write(self):
        class Client:
            def opportunities(self):
                return [opportunity()]
            def call(self, *args, **kwargs):
                raise AssertionError("No CRM call expected for disallowed payload")
        from app.services.crm_pursuit_scoring import model_hash
        plan = {"created_at": datetime.now(timezone.utc).isoformat(), "model_hash": model_hash(MODEL),
                "count": 1, "inputs": {"a": input_hash(opportunity())}, "updates": {"a": {"amount": 1}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "outside score fields"):
                self.cli.apply(Client(), MODEL, path, Path(directory), 1, False)

    def test_success_uncertain_write_readback_and_repeat_preserve_business_fields(self):
        cli = self.cli
        original = opportunity()
        class Client:
            def __init__(self):
                self.row = copy.deepcopy(original)
                self.puts = 0
            def opportunities(self):
                return [copy.deepcopy(self.row)]
            def call(self, method, path, **kwargs):
                if path == "/Metadata":
                    return {"entityDefs": {"Opportunity": {"fields": copy.deepcopy(cli.SCORE_FIELDS)}}}
                if method == "GET" and path == "/Opportunity/a":
                    return copy.deepcopy(self.row)
                if method == "PUT" and path == "/Opportunity/a":
                    self.puts += 1
                    self.row.update({k: v for k,v in kwargs["json"].items() if k != "_prev"})
                    raise RuntimeError("Simulated lost response after successful PUT")
                raise AssertionError((method, path))
        from app.services.crm_pursuit_scoring import model_hash
        now = datetime.now(timezone.utc)
        row = rank([original], evidence(), MODEL, TODAY)[0]
        payload = crm_values(row, MODEL, now)
        plan = {"created_at": now.isoformat(), "model_hash": model_hash(MODEL), "count": 1,
                "inputs": {"a": input_hash(original)}, "updates": {"a": payload}}
        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "plan.json"
            path.write_text(json.dumps(plan))
            cli.apply(client, MODEL, path, Path(directory), 1, False)
            self.assertEqual(1, client.puts)
            self.assertEqual(input_hash(original), input_hash(client.row))
            self.assertTrue(json.loads((Path(directory) / "apply-receipt.json").read_text())["complete"])
            cli.apply(client, MODEL, path, Path(directory), 1, False)
            self.assertEqual(1, client.puts)


if __name__ == "__main__":
    unittest.main()
