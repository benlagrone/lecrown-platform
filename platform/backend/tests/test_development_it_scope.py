import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core import database
from app.models.gov_contract import GovContractKeywordRule, GovContractOpportunity
from app.services import gov_contract_service as service
from app.services import candidate_inbox
from app.utils.helpers import new_uuid


PAVING_TITLE = ("Bid # 6000003495 - Rebid Asphalt And Concrete Delivery, Installation "
                "And Paving And Patching Services For The New Jersey Marine Terminals - Two-Year Requirements")


class DevelopmentITScopeTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)

    def candidate(self, title, source=service.SOURCE_NAME, payload=None, agency=None):
        return GovContractOpportunity(
            id=new_uuid(), source=source, source_key=new_uuid(), source_url="https://example.com/bid",
            title=title, solicitation_id="test", agency_name=agency, status_code="1", status_name="Posted",
            due_date=date.today() + timedelta(days=14), raw_payload=payload or {},
            score=15, priority_score=80, fit_bucket="high", is_match=True, is_open=True,
            matched_keywords=["asphalt"], funnel_status="discovered",
        )

    def test_non_it_never_qualifies_from_legacy_rules_buyer_or_gmail_label(self):
        with Session(self.engine) as db:
            db.add_all([GovContractKeywordRule(id=new_uuid(), phrase=p, weight=10)
                        for p in ["asphalt", "paving", "concrete", "information technology", "software"]])
            candidates = [self.candidate(title, source=source,
                agency="Information Technology Department", payload={
                    "organization": "Software development", "matched_keywords": ["software"],
                    "portal": "Software", "description": "Submit electronically using procurement software.",
                }) for source in [service.SOURCE_NAME, service.GMAIL_RFQ_SOURCE_NAME,
                                  service.FEDERAL_FORECAST_SOURCE_NAME, service.GRANTS_GOV_SOURCE_NAME]
                for title in [PAVING_TITLE, "Property management services", "Roofing and HVAC replacement",
                              "Data center construction", "Mowing and grounds maintenance", "Office paper supplies"]]
            db.add_all(candidates)
            db.commit()
            service.rescore_stored_opportunities(db)
            db.commit()
            self.assertEqual(len(candidates), len(service.list_contracts(db, limit=100, matches_only=False)))
            self.assertEqual([], service.list_contracts(db, limit=100, matches_only=True))
            for candidate in candidates:
                self.assertFalse(candidate.is_match, candidate.title)
                self.assertEqual(0, candidate.score)
                self.assertEqual(0, candidate.priority_score)
                self.assertEqual("none", candidate.fit_bucket)
                self.assertEqual([], candidate.matched_keywords)

    def test_it_and_adjacent_services_remain_relevant_including_physical_industry_software(self):
        titles = ["Artificial intelligence systems and services", "Cybersecurity assessment",
                  "Software development", "Cloud migration", "Data analytics and reporting",
                  "IT staffing and IT training", "Help desk support", "Structured cabling",
                  "Property management software implementation", "Construction project management software"]
        with Session(self.engine) as db:
            db.add_all([self.candidate(title) for title in titles])
            db.commit()
            service.rescore_stored_opportunities(db)
            db.commit()
            self.assertEqual(len(titles), len(service.list_contracts(db, limit=100, matches_only=True)))
            for candidate in db.scalars(select(GovContractOpportunity)):
                self.assertIn(service.IT_SERVICES_CATEGORY, service.serialize_opportunity(candidate).opportunity_categories)

    def test_buyer_and_stale_match_metadata_cannot_supply_it_scope(self):
        candidate = self.candidate("Office paper supplies", agency="Information Technology Office",
                                   payload={"organization": "Software", "matched_keywords": ["AI"]})
        candidate.matched_keywords = ["software"]
        self.assertEqual((0, []), service._score_opportunity(candidate, list(service.DEFAULT_MATCH_RULES)))
        self.assertNotIn(service.IT_SERVICES_CATEGORY, service._classify_opportunity(candidate)["opportunity_categories"])

    def test_gmail_does_not_force_match_or_trust_upstream_keyword_tags(self):
        with Session(self.engine) as db:
            service.list_keyword_rules(db)
            candidate = self.candidate(PAVING_TITLE, source=service.GMAIL_RFQ_SOURCE_NAME,
                                       payload={"matched_keywords": ["software", "AI"]})
            record = service.GovContractSourceRecord(
                source_key=candidate.source_key, solicitation_id=candidate.solicitation_id,
                source_url=candidate.source_url, title=candidate.title, agency_name=None, agency_number=None,
                status_code="1", status_name="Posted", due_date=candidate.due_date, due_time=None,
                posting_date=None, source_created_at=None, source_last_modified_at=None, nigp_codes=None,
                raw_payload=candidate.raw_payload,
            )
            with patch.object(service.settings, "gmail_rfq_match_score_floor", 100), \
                 patch.object(service, "fetch_gmail_rfq_feed", return_value={"count": 1}), \
                 patch.object(service, "_records_from_gmail_feed", return_value=[record]):
                self.assertEqual((0, []), service._score_gmail_opportunity(candidate, list(service.DEFAULT_MATCH_RULES)))
                run = service.refresh_gmail_contracts(db)
            self.assertEqual(1, run.total_records)
            self.assertEqual(0, run.matched_records)
            self.assertFalse(db.scalars(select(GovContractOpportunity)).one().is_match)

    def test_startup_rescores_sql_and_json_without_deleting_raw_candidates(self):
        with Session(self.engine) as db:
            candidate = self.candidate(PAVING_TITLE)
            candidate.funnel_record_id = "retained-crm-id"
            db.add(candidate)
            db.commit()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(candidate_inbox.settings, "procurement_candidate_json_path", str(Path(directory) / "inbox.json")), \
             patch.object(database, "SessionLocal", sessionmaker(bind=self.engine)):
            database._backfill_gov_contract_scores()
            snapshot = json.loads((Path(directory) / "inbox.json").read_text())
            entry = next(iter(snapshot["candidates"].values()))["candidate"]
            self.assertFalse(entry["is_match"])
            self.assertEqual(0, entry["score"])
            self.assertEqual("retained-crm-id", entry["funnel_record_id"])
            self.assertEqual(PAVING_TITLE, entry["title"])

    def test_scope_migration_is_idempotent_preserves_custom_weights_and_candidates(self):
        spec = importlib.util.spec_from_file_location("it_scope_migration",
            Path(__file__).resolve().parents[1] / "migrations/versions/20261027_0004_development_it_scope.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with Session(self.engine) as db:
            db.add_all([GovContractKeywordRule(id=new_uuid(), phrase=p, weight=w)
                        for p, w in [("asphalt", 5), ("property management", 9), ("software", 9), ("custom phrase", 3)]])
            candidate = self.candidate(PAVING_TITLE)
            candidate.funnel_record_id = "preserved-crm-record"
            db.add(candidate)
            db.commit()
        with self.engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            migration.upgrade()
        with Session(self.engine) as db:
            rules = {r.phrase: r.weight for r in db.scalars(select(GovContractKeywordRule))}
            self.assertNotIn("asphalt", rules)
            self.assertNotIn("property management", rules)
            self.assertEqual(9, rules["software"])
            self.assertIn("data analytics", rules)
            self.assertIn("custom phrase", rules)
            stored = db.scalars(select(GovContractOpportunity)).one()
            self.assertEqual(PAVING_TITLE, stored.title)
            self.assertEqual("preserved-crm-record", stored.funnel_record_id)
