import os
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.gov_contract import GovContractKeywordRule, GovContractOpportunity
from app.services.gov_contract_service import (
    SOURCE_NAME,
    create_agency_preference,
    delete_agency_preference,
    list_agency_preferences,
    list_keyword_rules,
    list_contracts,
    rescore_stored_opportunities,
)
from app.utils.helpers import new_uuid


class GovContractScoringTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="gov-contract-scoring-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_agency_affinity_rescores_and_min_priority_filters_view(self) -> None:
        with self.Session() as db:
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="roofing", weight=5))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="rehabilitation", weight=6))
            db.add(
                GovContractOpportunity(
                    id=new_uuid(),
                    source=SOURCE_NAME,
                    source_key="sol-high",
                    source_url="https://example.com/high",
                    title="Dormitory roofing rehabilitation project",
                    solicitation_id="SOL-HIGH",
                    agency_name="Texas A&M University System - 710",
                    agency_number="710",
                    status_code="1",
                    status_name="Posted",
                    due_date=date.today() + timedelta(days=14),
                    posting_date=date.today(),
                    nigp_codes="construction; roofing",
                    score=0,
                    priority_score=0,
                    fit_bucket="none",
                    is_match=False,
                    is_open=True,
                    matched_keywords=[],
                    score_breakdown={},
                    raw_payload={},
                    funnel_status="discovered",
                    first_seen_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
            )
            db.add(
                GovContractOpportunity(
                    id=new_uuid(),
                    source=SOURCE_NAME,
                    source_key="sol-low",
                    source_url="https://example.com/low",
                    title="Office paper supplies purchase",
                    solicitation_id="SOL-LOW",
                    agency_name="Generic State Purchasing Office",
                    status_code="1",
                    status_name="Posted",
                    due_date=date.today() + timedelta(days=7),
                    posting_date=date.today(),
                    nigp_codes="office supplies",
                    score=0,
                    priority_score=0,
                    fit_bucket="none",
                    is_match=False,
                    is_open=True,
                    matched_keywords=[],
                    score_breakdown={},
                    raw_payload={},
                    funnel_status="discovered",
                    first_seen_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

            rescore_stored_opportunities(db)
            db.commit()

            all_items = list_contracts(db, limit=10, matches_only=False, open_only=False)
            self.assertEqual(2, len(all_items))
            high = next(item for item in all_items if item.source_key == "sol-high")
            low = next(item for item in all_items if item.source_key == "sol-low")
            self.assertEqual(5, high.score_breakdown["agency_affinity"])
            self.assertGreater(high.priority_score, low.priority_score)

            preference = create_agency_preference(db, agency_name="Texas A&M University System", weight=9)
            rescored_items = list_contracts(db, limit=10, matches_only=False, open_only=False)
            high = next(item for item in rescored_items if item.source_key == "sol-high")
            low = next(item for item in rescored_items if item.source_key == "sol-low")
            self.assertEqual(9, high.score_breakdown["agency_affinity"])
            self.assertIn(
                "Texas A&M University System",
                high.score_breakdown["matched_agency_preferences"],
            )
            self.assertEqual(3, low.score_breakdown["agency_affinity"])

            filtered_items = list_contracts(
                db,
                limit=10,
                matches_only=False,
                open_only=False,
                min_priority_score=high.priority_score,
            )
            self.assertEqual(["sol-high"], [item.source_key for item in filtered_items])

            delete_agency_preference(db, preference.id)
            self.assertEqual([], list_agency_preferences(db))
            restored_items = list_contracts(db, limit=10, matches_only=False, open_only=False)
            restored_high = next(item for item in restored_items if item.source_key == "sol-high")
            self.assertEqual(5, restored_high.score_breakdown["agency_affinity"])

    def test_list_keyword_rules_seeds_default_it_keywords(self) -> None:
        with self.Session() as db:
            rules = list_keyword_rules(db)

            self.assertGreater(len(rules), 0)

            phrases = {rule.phrase for rule in rules}
            self.assertIn("information technology", phrases)
            self.assertIn("cybersecurity", phrases)
            self.assertIn("software development", phrases)
            self.assertIn("cloud services", phrases)

            persisted_rules = list_keyword_rules(db)
            self.assertEqual(len(rules), len(persisted_rules))

    def test_short_keyword_matches_whole_term_not_substring(self) -> None:
        with self.Session() as db:
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="AI", weight=5))
            db.add(
                GovContractOpportunity(
                    id=new_uuid(),
                    source=SOURCE_NAME,
                    source_key="ai-match",
                    source_url="https://example.com/ai",
                    title="AI camera analytics support",
                    solicitation_id="AI-MATCH",
                    agency_name="City of Austin",
                    status_code="1",
                    status_name="Posted",
                    due_date=date.today() + timedelta(days=10),
                    posting_date=date.today(),
                    nigp_codes="technology",
                    score=0,
                    priority_score=0,
                    fit_bucket="none",
                    is_match=False,
                    is_open=True,
                    matched_keywords=[],
                    score_breakdown={},
                    raw_payload={},
                    funnel_status="discovered",
                    first_seen_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
            )
            db.add(
                GovContractOpportunity(
                    id=new_uuid(),
                    source=SOURCE_NAME,
                    source_key="grounds-only",
                    source_url="https://example.com/mowing",
                    title="Mowing and grounds maintenance",
                    solicitation_id="GROUNDS-ONLY",
                    agency_name="City of Austin",
                    status_code="1",
                    status_name="Posted",
                    due_date=date.today() + timedelta(days=10),
                    posting_date=date.today(),
                    nigp_codes="grounds maintenance",
                    score=0,
                    priority_score=0,
                    fit_bucket="none",
                    is_match=False,
                    is_open=True,
                    matched_keywords=[],
                    score_breakdown={},
                    raw_payload={},
                    funnel_status="discovered",
                    first_seen_at=datetime.now(timezone.utc),
                    last_seen_at=datetime.now(timezone.utc),
                )
            )
            db.commit()

            rescore_stored_opportunities(db)
            db.commit()

            items = list_contracts(db, limit=10, matches_only=False, open_only=False)
            ai_match = next(item for item in items if item.source_key == "ai-match")
            grounds_only = next(item for item in items if item.source_key == "grounds-only")

            self.assertIn("AI", ai_match.matched_keywords)
            self.assertTrue(ai_match.is_match)
            self.assertEqual([], grounds_only.matched_keywords)
            self.assertFalse(grounds_only.is_match)


if __name__ == "__main__":
    unittest.main()
