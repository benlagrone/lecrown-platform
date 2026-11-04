import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.jobs.score_crm_opportunities import healthy
from app.models.gov_contract import GovContractImportRun, GovContractOpportunity, GovContractTrackedSource
from app.services.crm_pursuit_automation import catalog_evidence, synchronize
from app.services.crm_pursuit_scoring import assessment, input_hash
from app.services.crm_pursuit_sync import MODEL_PATH, SCORE_FIELDS, retry_seconds, write_private

MODEL = json.loads(MODEL_PATH.read_text())
NOW = datetime(2026, 11, 4, 18, tzinfo=timezone.utc)


def record(key="a", name="Requirements Database Management System"):
    return {"id": key, "name": name, "stage": "Prospecting", "amount": None,
            "description": "Source URL: https://buyer.bonfirehub.com/opportunities/1\nDue Date: 2026-11-18"}


def live(records):
    return {r["id"]: {"status": "listed_open", "checked_at": NOW.isoformat(),
                       "project": {"DateClose": "2026-11-18"}} for r in records}


class FakeClient:
    def __init__(self):
        self.rows = {"a": record()}
        self.puts = []
        self.uncertain = False
        self.mutate = False

    def opportunities(self):
        return copy.deepcopy(list(self.rows.values()))

    def call(self, method, path, **kwargs):
        if path == "/Metadata":
            return {"entityDefs": {"Opportunity": {"fields": SCORE_FIELDS}}}
        key = path.rsplit("/", 1)[-1]
        if method == "GET":
            if self.mutate:
                self.rows[key]["amount"] = 100
            return copy.deepcopy(self.rows[key])
        if method == "PUT":
            payload = kwargs["json"]
            assert set(payload) == set(SCORE_FIELDS) | {"_prev"}
            self.puts.append(copy.deepcopy(payload))
            self.rows[key].update({k: v for k, v in payload.items() if k != "_prev"})
            if self.uncertain:
                raise RuntimeError("Response lost after server applied write")
            return copy.deepcopy(self.rows[key])
        raise AssertionError((method, path))


class AutomationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.client = FakeClient()
        self.addCleanup(self.temp.cleanup)

    def sync(self, now=NOW, loader=live):
        return synchronize(self.client, MODEL, self.directory, loader, now)

    def test_new_record_is_scored_and_unchanged_polls_are_zero_writes(self):
        original = input_hash(self.client.rows["a"])
        self.assertEqual(1, self.sync()["written"])
        timestamp = self.client.rows["a"]["cPursuitAssessedAt"]
        self.assertEqual(0, self.sync(NOW + timedelta(minutes=1))["written"])
        self.assertEqual(timestamp, self.client.rows["a"]["cPursuitAssessedAt"])
        self.assertEqual(original, input_hash(self.client.rows["a"]))
        self.client.rows["b"] = record("b", "AI Innovation Challenge")
        self.assertEqual(2, self.sync(NOW + timedelta(minutes=2))["count"])
        self.assertEqual({1, 2}, {r["cPursuitRank"] for r in self.client.rows.values()})

    def test_details_changes_trigger_new_assessment_without_owner_cost_guesses(self):
        self.sync()
        self.client.rows["a"]["description"] += "\nStatus: Subcontract opportunity"
        self.assertEqual(1, self.sync(NOW + timedelta(minutes=1))["written"])
        self.assertEqual("Sub - qualify", self.client.rows["a"]["cPursuitStatus"])
        self.assertIsNone(self.client.rows["a"]["amount"])

    def test_deadline_extension_and_daily_expiry_rerank_without_crm_edit(self):
        self.sync()
        def tomorrow(records):
            value = live(records)
            value["a"]["project"]["DateClose"] = "2026-11-05"
            return value
        self.assertEqual(1, self.sync(loader=tomorrow)["written"])
        def expired(records):
            value = tomorrow(records)
            value["a"]["checked_at"] = "2026-11-06T18:00:00+00:00"
            return value
        self.sync(NOW + timedelta(days=2), expired)
        self.assertEqual("Hold - deadline review", self.client.rows["a"]["cPursuitStatus"])

    def test_new_snapshot_same_scope_and_deadline_does_not_loop(self):
        self.sync()
        def refreshed(records):
            value = live(records)
            value["a"]["checked_at"] = (NOW + timedelta(minutes=15)).isoformat()
            return value
        self.assertEqual(0, self.sync(NOW + timedelta(minutes=15), refreshed)["written"])

    def test_restart_uncertain_write_and_deleted_opportunity_are_reconciled(self):
        self.client.uncertain = True
        self.sync()
        self.assertEqual(0, self.sync()["written"])
        self.client.rows.clear()
        self.assertEqual(0, self.sync()["count"])

    def test_inflight_business_edit_aborts_before_writing(self):
        self.client.mutate = True
        with self.assertRaisesRegex(ValueError, "changed during scoring"):
            self.sync()
        self.assertEqual([], self.client.puts)

    def test_manual_score_drift_repaired_but_other_content_preserved(self):
        self.sync()
        self.client.rows["a"]["cPursuitRank"] = 40
        self.assertEqual(1, self.sync()["written"])
        self.assertEqual(1, self.client.rows["a"]["cPursuitRank"])

    def test_collection_in_progress_reuses_only_unchanged_source_urls(self):
        self.sync()
        self.assertEqual(0, self.sync(loader=lambda records: None)["written"])
        self.client.rows["a"]["description"] = "Source URL: https://buyer.bonfirehub.com/opportunities/2"
        self.sync(loader=lambda records: None)
        self.assertEqual("Prime - source review", self.client.rows["a"]["cPursuitStatus"])

    def test_unknown_and_invalid_date_do_not_prevent_other_records_being_assessed(self):
        self.client.rows["b"] = record("b", "Unreviewed new service")
        self.client.rows["b"]["description"] = "Due Date: 2026-99-99"
        self.assertEqual(1, self.sync()["review_required"])
        self.assertIsNone(self.client.rows["b"]["cWinLikelihoodScore"])
        self.assertEqual(2, len(self.client.puts))

    def test_description_scope_can_match_existing_profile(self):
        value = record(name="Technology modernization")
        value["description"] += "\nScope: Implement electronic content management."
        self.assertEqual("ecm", assessment(value, {}, MODEL, NOW.date())["profile"])

    def test_health_and_private_atomic_state(self):
        self.assertFalse(healthy(self.directory, NOW))
        write_private(self.directory / "health.json", {"status": "ok", "checked_at": NOW.isoformat()})
        self.assertTrue(healthy(self.directory, NOW))
        self.assertFalse(healthy(self.directory, NOW + timedelta(minutes=5)))
        self.assertEqual(0o600, (self.directory / "health.json").stat().st_mode & 0o777)
        self.assertEqual(3600, retry_seconds("3600"))
        self.assertEqual(900, retry_seconds("invalid"))


class CachedEvidenceTest(unittest.TestCase):
    def test_complete_snapshot_matches_source_and_missing_project_not_listed_open(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(GovContractTrackedSource(id="s", source="buyer", label="Buyer", listing_url="https://buyer.bonfirehub.com/portal",
                   platform_name="Bonfire", jurisdiction_type="local", extraction_mode="bonfire_public_json"))
            db.add(GovContractImportRun(id="run", source="buyer", status="completed", window_start=NOW.date(),
                   window_end=NOW.date(), completed_at=NOW.replace(tzinfo=None)))
            db.add(GovContractOpportunity(id="p", source="buyer", source_key="buyer:1", source_url="https://buyer.bonfirehub.com/opportunities/1",
                   title="Project", solicitation_id="RFP1", is_open=True, due_date=date(2026, 11, 18), last_seen_at=NOW.replace(tzinfo=None)))
            db.commit()
            value = catalog_evidence([record()], db)["a"]
            self.assertEqual("listed_open", value["status"])
            self.assertEqual("2026-11-18", value["project"]["DateClose"])
            project = db.get(GovContractOpportunity, "p")
            project.is_open = False
            db.commit()
            self.assertEqual("listed_open", catalog_evidence([record()], db)["a"]["status"])
            project.last_seen_at -= timedelta(days=1)
            db.commit()
            self.assertEqual("not_in_open_list", catalog_evidence([record()], db)["a"]["status"])
            missing = record()
            missing["description"] = "Source URL: https://buyer.bonfirehub.com/opportunities/2"
            self.assertEqual("not_in_open_list", catalog_evidence([missing], db)["a"]["status"])
            missing["description"] = "Source URL: https://buyer.bonfirehub.com/opportunities/private/not-public"
            self.assertEqual({}, catalog_evidence([missing], db))
            db.query(GovContractImportRun).delete()
            db.commit()
            self.assertEqual({}, catalog_evidence([record()], db))
        engine.dispose()
