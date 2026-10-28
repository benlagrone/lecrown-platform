from __future__ import annotations

import inspect
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.security import get_current_admin
from app.models.gov_contract import GovContractOpportunity
from app.routes import gov_contract as routes
from app.schemas.gov_contract import GovContractFitFeedbackRequest
from app.services import candidate_inbox as inbox, espocrm_service, gov_contract_service as service
from app.services.fit_feedback import FeedbackRanker


class FitFeedbackTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "candidates.json"
        self.setting = patch.object(inbox.settings, "procurement_candidate_json_path", str(self.path))
        self.setting.start()
        self.addCleanup(self.setting.stop)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.db = Session(self.engine)
        self.addCleanup(self.db.close)
        self.add("example", "Cloud software integration", priority=40)
        self.add("similar", "Cloud software integration migration", priority=40)
        self.add("road", "Asphalt paving installation", priority=0, is_match=False, is_open=False)

    def add(self, key, title, priority=40, is_match=True, is_open=True):
        row = GovContractOpportunity(id=key, source="test", source_key=key,
            source_url=f"https://buyer.example/{key}", title=title, solicitation_id=key,
            priority_score=priority, score=6 if is_match else 0, is_match=is_match,
            is_open=is_open, fit_bucket="high" if is_match else "none")
        self.db.add(row)
        self.db.commit()
        inbox.capture([service.serialize_opportunity(row).model_dump(mode="json")])
        return row

    def rate(self, key="example", rating="high", version=0):
        return inbox.set_fit_feedback(key, rating=rating, reviewed_by="admin-1", expected_version=version)

    def candidate(self, key):
        return service.serialize_opportunity(self.db.get(GovContractOpportunity, key))

    def test_label_change_clear_history_and_no_op_are_durable(self):
        self.assertEqual(1, self.rate()["version"])
        self.assertEqual(1, self.rate(version=1)["version"])
        self.assertEqual(2, self.rate(rating="low", version=1)["version"])
        self.assertEqual(3, self.rate(rating=None, version=2)["version"])
        saved = inbox.snapshot()["candidates"][inbox.candidate_id("example")]
        self.assertEqual(["high", "low", None], [item["rating"] for item in saved["fit_feedback_history"]])
        self.assertEqual("admin-1", saved["fit_feedback"]["reviewed_by"])
        reloaded = FeedbackRanker.load().apply(self.candidate("example"))
        self.assertEqual(3, reloaded.fit_feedback_version)
        self.assertIsNone(reloaded.fit_feedback_rating)
        self.assertIsNotNone(reloaded.fit_feedback_at)

    def test_concurrent_sessions_cannot_overwrite_a_rating(self):
        def attempt(rating):
            try:
                return self.rate(rating=rating)["rating"]
            except inbox.FitFeedbackConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["high", "low"]))
        self.assertEqual(1, results.count("conflict"))
        self.assertEqual(1, FeedbackRanker.load().apply(self.candidate("example")).fit_feedback_version)

    def test_recapture_preserves_feedback_history_and_promotion_receipt(self):
        self.rate()
        with inbox._locked() as (path, data):
            data["candidates"][inbox.candidate_id("example")]["promotion"] = {"status": "promoted", "crm_record_id": "crm-1"}
            inbox._save(path, data)
        changed = self.candidate("example").model_dump(mode="json")
        changed["title"] = "Updated cloud software integration"
        inbox.capture([changed])
        saved = inbox.snapshot()["candidates"][inbox.candidate_id("example")]
        self.assertEqual("high", saved["fit_feedback"]["rating"])
        self.assertEqual(1, len(saved["fit_feedback_history"]))
        self.assertEqual("crm-1", saved["promotion"]["crm_record_id"])

    def test_corrupt_inbox_is_not_replaced(self):
        self.path.write_text("not json", encoding="utf-8")
        with self.assertRaises(inbox.CandidateInboxError):
            self.rate()
        self.assertEqual("not json", self.path.read_text(encoding="utf-8"))

    def test_failed_write_preserves_previous_rating(self):
        self.rate()
        with patch.object(inbox.os, "replace", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.rate(rating="low", version=1)
        self.assertEqual("high", FeedbackRanker.load().apply(self.candidate("example")).fit_feedback_rating)

    def test_positive_negative_and_cleared_examples_adjust_similar_it_titles(self):
        target = self.candidate("similar")
        self.assertIn("it_services", target.opportunity_categories)
        self.rate()
        learned = FeedbackRanker.load().apply(target)
        self.assertGreater(learned.review_priority_score, target.priority_score)
        self.assertLessEqual(learned.feedback_adjustment, 20)
        self.assertEqual("example", learned.feedback_examples[0].source_key)
        self.assertEqual(target.score, learned.score)
        self.assertEqual(target.is_match, learned.is_match)
        self.rate(rating="low", version=1)
        learned_low = FeedbackRanker.load().apply(target)
        self.assertLess(learned_low.review_priority_score, target.priority_score)
        self.assertFalse(learned_low.qualification_match)
        self.assertEqual("learned_low", learned_low.qualification_basis)
        self.rate(rating=None, version=2)
        self.assertEqual(target.priority_score, FeedbackRanker.load().apply(target).review_priority_score)

    def test_non_it_records_cannot_gain_automatic_priority_from_learning(self):
        self.rate("road")
        self.add("another-road", "Asphalt paving installation project", priority=0, is_match=False)
        target = FeedbackRanker.load().apply(self.candidate("another-road"))
        self.assertEqual(0, target.feedback_adjustment)
        self.assertEqual(0, target.review_priority_score)
        self.assertFalse(target.is_match)
        self.assertEqual([], target.feedback_examples)
        self.assertFalse(target.qualification_match)

    def test_high_and_low_override_qualified_filter_without_changing_keyword_evidence(self):
        self.rate(rating="low")
        result = service.search_contracts(self.db, matches_only=True, open_only=False)
        self.assertEqual([], result["items"])
        self.assertEqual(0, result["qualified_count"])
        self.assertTrue(self.db.get(GovContractOpportunity, "example").is_match)
        self.assertEqual(3, service.search_contracts(self.db, matches_only=False, open_only=False)["total"])
        self.rate(rating="high", version=1)
        result = service.search_contracts(self.db, matches_only=True, open_only=False)
        self.assertEqual({"example", "similar"}, {item.id for item in result["items"]})
        self.assertEqual(2, result["category_counts"]["it_services"])

    def test_high_feedback_teaches_missing_terminology_and_clear_removes_example(self):
        self.add("novel", "Identity governance lifecycle", priority=0, is_match=False)
        self.add("novel-similar", "Identity governance lifecycle consulting", priority=0, is_match=False)
        self.rate("novel")
        target = FeedbackRanker.load().apply(self.candidate("novel-similar"))
        self.assertTrue(target.qualification_match)
        self.assertEqual("learned_high", target.qualification_basis)
        self.assertFalse(target.is_match)
        self.assertEqual(["other"], target.opportunity_categories)
        result = service.search_contracts(self.db, matches_only=True, open_only=False)
        self.assertIn("novel-similar", {item.id for item in result["items"]})
        self.rate("novel", rating=None, version=1)
        target = FeedbackRanker.load().apply(self.candidate("novel-similar"))
        self.assertFalse(target.qualification_match)
        self.assertEqual([], target.feedback_examples)

    def test_weak_or_conflicting_examples_do_not_change_qualification(self):
        self.rate(rating="low")
        self.add("weak", "Cloud software integration migration analytics reporting dashboard")
        weak = FeedbackRanker.load().apply(self.candidate("weak"))
        self.assertTrue(weak.qualification_match)
        self.assertEqual("keyword", weak.qualification_basis)
        self.assertLess(weak.feedback_adjustment, 0)
        self.add("opposite", "Cloud software integration")
        self.rate("opposite")
        conflict = FeedbackRanker.load().apply(self.candidate("similar"))
        self.assertTrue(conflict.qualification_match)
        self.assertEqual("keyword", conflict.qualification_basis)

    def test_review_priority_filter_and_pagination_use_learned_results(self):
        self.add("novel", "Identity governance lifecycle", priority=0, is_match=False)
        self.rate("novel")
        result = service.search_contracts(self.db, matches_only=True, open_only=False, min_priority_score=100)
        self.assertEqual(["novel"], [item.id for item in result["items"]])
        self.assertEqual(3, result["qualified_count"])
        first = service.search_contracts(self.db, matches_only=True, open_only=False, limit=1)
        second = service.search_contracts(self.db, matches_only=True, open_only=False, limit=1, offset=1)
        self.assertEqual(3, first["total"])
        self.assertEqual(first["category_counts"], second["category_counts"])
        self.assertNotEqual(first["items"][0].id, second["items"][0].id)

    def test_physical_override_is_explicit_only_and_does_not_train_other_roads(self):
        self.rate("road")
        high = FeedbackRanker.load().apply(self.candidate("road"))
        self.assertTrue(high.qualification_match)
        self.assertEqual("human_high", high.qualification_basis)
        self.assertNotIn("it_services", high.opportunity_categories)
        self.assertNotIn("road", {item.id for item in service.search_contracts(
            self.db, matches_only=True, open_only=True)["items"]})
        self.assertIn("road", {item.id for item in service.search_contracts(
            self.db, matches_only=True, open_only=False)["items"]})

    def test_generic_bid_terms_do_not_train_unrelated_candidates(self):
        self.add("generic-example", "County RFP professional software services")
        self.add("generic-target", "County RFP professional cybersecurity services")
        self.rate("generic-example")
        self.assertEqual([], FeedbackRanker.load().apply(self.candidate("generic-target")).feedback_examples)

    def test_human_ratings_have_priority_and_do_not_train_themselves(self):
        self.rate()
        high = FeedbackRanker.load().apply(self.candidate("example"))
        self.assertEqual(100, high.review_priority_score)
        self.assertEqual([], high.feedback_examples)
        self.rate(rating="low", version=1)
        self.assertEqual(0, FeedbackRanker.load().apply(self.candidate("example")).review_priority_score)

    def test_all_leads_and_human_filters_include_closed_nonmatches(self):
        self.rate("road", "low")
        result = service.search_contracts(self.db, matches_only=False, open_only=False, limit=1)
        self.assertEqual(3, result["total"])
        self.assertEqual({"all": 3, "high": 0, "low": 1, "unreviewed": 2}, result["fit_feedback_counts"])
        low = service.search_contracts(self.db, matches_only=False, open_only=False, fit_feedback="low")
        self.assertEqual(["road"], [item.id for item in low["items"]])
        self.assertFalse(low["items"][0].is_open)
        unreviewed = service.search_contracts(self.db, matches_only=False, open_only=False, fit_feedback="unreviewed", offset=1, limit=1)
        self.assertEqual(2, unreviewed["total"])
        self.assertEqual(1, len(unreviewed["items"]))

    def test_rating_route_never_calls_crm_and_returns_conflict(self):
        admin = SimpleNamespace(id="admin-1")
        payload = GovContractFitFeedbackRequest(rating="high", expected_version=0)
        with patch.object(espocrm_service, "create_opportunity") as opportunity, patch.object(espocrm_service, "create_lead") as lead:
            result = routes.rate_candidate("example", payload, self.db, admin)
            self.assertEqual("high", result["rating"])
            with self.assertRaises(HTTPException) as conflict:
                routes.rate_candidate("example", payload, self.db, admin)
            self.assertEqual(409, conflict.exception.status_code)
            opportunity.assert_not_called()
            lead.assert_not_called()

    def test_rating_route_fails_for_missing_candidate_or_storage(self):
        payload = GovContractFitFeedbackRequest(rating="low", expected_version=0)
        admin = SimpleNamespace(id="admin-1")
        with self.assertRaises(HTTPException) as missing:
            routes.rate_candidate("missing", payload, self.db, admin)
        self.assertEqual(404, missing.exception.status_code)
        with patch.object(inbox.settings, "procurement_candidate_json_path", ""):
            with self.assertRaises(HTTPException) as unavailable:
                routes.rate_candidate("example", payload, self.db, admin)
        self.assertEqual(503, unavailable.exception.status_code)
        with patch.object(inbox, "set_fit_feedback", side_effect=OSError("disk error")):
            with self.assertRaises(HTTPException) as failed:
                routes.rate_candidate("example", payload, self.db, admin)
        self.assertEqual(503, failed.exception.status_code)

    def test_only_admins_can_rate_and_invalid_payloads_are_rejected(self):
        dependency = inspect.signature(routes.rate_candidate).parameters["admin"].default
        self.assertIs(get_current_admin, dependency.dependency)
        with self.assertRaises(HTTPException) as forbidden:
            get_current_admin(SimpleNamespace(is_admin=False))
        self.assertEqual(403, forbidden.exception.status_code)
        for value in ({}, {"rating": "medium", "expected_version": 0}, {"rating": "low", "expected_version": -1}):
            with self.assertRaises(ValidationError):
                GovContractFitFeedbackRequest(**value)


if __name__ == "__main__":
    unittest.main()
