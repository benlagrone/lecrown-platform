import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.config import get_settings
from app.schemas.gov_contract import GovContractOpportunityRead
from app.services.crm_pursuit_sync import write_private
from app.services.opportunity_descriptions import content_hash, description_fields, parse_bonfire_description, preserve_description, public_bonfire_url
from app.services.semantic_fit import CAPABILITIES, SemanticProjection, VERSION, build_projection, chunks, label_hash
from app.jobs.qualify_semantic_candidates import DescriptionRateLimit, browser_description


def candidate(key="target", text="Build a secure application platform with data integration and governed workflows for public services."):
    return {"id": key, "source": "test", "source_key": key, "source_url": "https://buyer.bonfirehub.com/opportunities/1",
            "title": "IT_WORK " + key, "solicitation_id": key, "description_text": text, "description_status": "available",
            "score": 0, "priority_score": 0, "fit_bucket": "none", "is_match": False, "is_open": True,
            "funnel_status": "discovered", **{name: "2026-11-04T12:00:00Z" for name in ["created_at", "updated_at", "first_seen_at", "last_seen_at"]}}


class DescriptionTest(unittest.TestCase):
    def test_complete_description_is_exposed_without_truncating_tail(self):
        text = "Detailed scope " * 2000 + "final acceptance condition"
        row = SimpleNamespace(title="Brief title", source_url="https://buyer.example", raw_payload={"description": text})
        result = description_fields(row)
        self.assertEqual(text, result["description_text"])
        self.assertEqual("available", result["description_status"])

    def test_title_repeat_is_not_a_full_description(self):
        result = description_fields(SimpleNamespace(title="Project", source_url="https://buyer.example", raw_payload={"description": "Project"}))
        self.assertEqual("", result["description_text"])
        self.assertEqual("missing", result["description_status"])

    def test_public_html_parser_does_not_use_menus_or_document_takers(self):
        html = '<div id="opportunityMetaSection">Project: Project<br>Project Description: <p>Full scope.</p></div><div>Other unrelated text</div>'
        self.assertEqual("Full scope.", parse_bonfire_description(html))
        self.assertEqual("", parse_bonfire_description("<h1>Verify you are human</h1>"))

    def test_only_exact_public_bonfire_urls_are_allowed(self):
        self.assertTrue(public_bonfire_url("https://buyer.bonfirehub.com/opportunities/123"))
        for url in ["http://buyer.bonfirehub.com/opportunities/1", "https://buyer.bonfirehub.com.evil.test/opportunities/1",
                    "https://127.0.0.1/opportunities/1", "https://buyer.bonfirehub.com/opportunities/private/secret",
                    "https://user:password@buyer.bonfirehub.com/opportunities/1", "https://buyer.bonfirehub.com/opportunities/1?next=evil"]:
            self.assertFalse(public_bonfire_url(url))

    def test_collector_recapture_preserves_description_only_for_same_source(self):
        value = {"qualification_description": {"url": "url", "text": "Scope"}}
        self.assertIn("qualification_description", preserve_description(value, {}, "url"))
        self.assertNotIn("qualification_description", preserve_description(value, {}, "changed"))

    def test_chunking_uses_all_tokens_including_tail(self):
        class Tokenizer:
            def no_truncation(self):
                pass
            def encode(self, text, add_special_tokens=False):
                return SimpleNamespace(offsets=[(i, i + 1) for i in range(len(text))])
        text = "x" * 1200 + "TAIL"
        values = chunks(text, Tokenizer())
        self.assertEqual(text, "".join(values))
        self.assertTrue(values[-1].endswith("TAIL"))
        self.assertTrue(all(len(value) <= 400 for value in values))

    def test_browser_navigation_stops_on_rate_limit_without_solving_challenges(self):
        from unittest.mock import Mock
        page = Mock()
        page.goto.return_value = SimpleNamespace(status=429, headers={"retry-after": "3600"})
        browser = Mock()
        browser.new_page.return_value = page
        with self.assertRaises(DescriptionRateLimit) as result:
            browser_description(browser, "https://buyer.bonfirehub.com/opportunities/1")
        self.assertEqual(3600, result.exception.delay)
        page.close.assert_called_once()
        page.locator.assert_not_called()


class ProjectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.setting = patch.object(get_settings(), "semantic_fit_state_dir", str(self.directory))
        self.setting.start()
        self.addCleanup(self.setting.stop)
        self.snapshot = {"candidates": {"rated": {"candidate": {"source_key": "rated"}, "fit_feedback": {"rating": "high", "version": 1}}}}

    def save(self, row, qualified=True, basis="semantic_high"):
        write_private(self.directory / "projection.json", {"version": VERSION, "label_hash": label_hash(self.snapshot),
            "records": {row["source_key"]: {"content_hash": content_hash(row), "qualified": qualified, "basis": basis,
                        "reason": "Semantic scope fit", "score": 92, "capability": "data", "examples": []}}})

    def test_semantic_high_is_qualified_and_in_it_tab_without_mutating_keywords(self):
        row = candidate()
        self.save(row)
        original = GovContractOpportunityRead.model_validate(row)
        applied = SemanticProjection(self.snapshot).apply(original, {})
        self.assertTrue(applied.qualification_match)
        self.assertEqual(["it_services"], applied.opportunity_categories)
        self.assertFalse(applied.is_match)
        self.assertEqual("semantic", applied.category_basis)
        self.assertEqual(0, original.score)

    def test_changed_description_or_ratings_invalidates_old_assessment(self):
        row = candidate()
        self.save(row)
        changed = {**row, "description_text": "Different complete scope"}
        result = SemanticProjection(self.snapshot).apply(GovContractOpportunityRead.model_validate(changed), {})
        self.assertFalse(result.qualification_match)
        self.assertEqual("semantic_pending", result.qualification_basis)
        self.snapshot["candidates"]["rated"]["fit_feedback"]["version"] = 2
        self.assertFalse(SemanticProjection(self.snapshot).current)

    def test_human_labels_remain_authoritative_when_model_missing(self):
        row = GovContractOpportunityRead.model_validate(candidate())
        projection = SemanticProjection(self.snapshot)
        self.assertTrue(projection.apply(row, {"rating": "high", "version": 1}).qualification_match)
        self.assertFalse(projection.apply(row, {"rating": "low", "version": 2}).qualification_match)
        self.assertFalse(projection.apply(row, {"rating": None, "version": 3}).qualification_match)

    def test_missing_or_corrupt_projection_fails_to_review_not_title_similarity(self):
        (self.directory / "projection.json").write_text("invalid")
        row = GovContractOpportunityRead.model_validate(candidate())
        self.assertEqual("semantic_pending", SemanticProjection(self.snapshot).apply(row, {}).qualification_basis)

    def test_low_fit_can_override_a_cached_semantic_high_and_clear_stays_a_training_change(self):
        row = candidate()
        self.save(row)
        projection = SemanticProjection(self.snapshot)
        value = projection.apply(GovContractOpportunityRead.model_validate(row), {"rating": "low", "version": 3})
        self.assertFalse(value.qualification_match)
        self.assertEqual("human_low", value.qualification_basis)
        changed = copy.deepcopy(self.snapshot)
        changed["candidates"]["rated"]["fit_feedback"]["rating"] = None
        self.assertNotEqual(label_hash(changed), label_hash(self.snapshot))

    def test_end_to_end_classifier_capability_guardrail_and_missing_description(self):
        capabilities = json.loads(CAPABILITIES.read_text())
        allowed = set(capabilities["in_scope"].values())
        class Encoder:
            def encode(self, texts):
                return np.array([[1., 0.] if text in allowed or "IT_WORK" in text else [-1., 0.] for text in texts])
        rows = [candidate(f"good-{chr(97 + i)}") for i in range(25)]
        rows += [{**candidate(f"bad-{chr(97 + i)}"), "title": f"ROAD_WORK bad-{chr(97 + i)}", "description_text": "Supply asphalt and pave a highway with heavy machinery and concrete construction."} for i in range(25)]
        snapshot = {"candidates": {row["source_key"]: {"candidate": row, "fit_feedback": {
            "rating": "high" if i < 25 else "low", "version": 1}} for i, row in enumerate(rows)}}
        rows += [candidate("unreviewed"), {**candidate("road"), "title": "ROAD_WORK road"}, candidate("missing", "")]
        projection = build_projection(rows, snapshot, Encoder())
        self.assertTrue(projection["evaluation"]["ready"])
        self.assertTrue(projection["records"]["unreviewed"]["qualified"])
        self.assertEqual("semantic_out_of_scope", projection["records"]["road"]["basis"])
        self.assertEqual("needs_description", projection["records"]["missing"]["basis"])


if __name__ == "__main__":
    unittest.main()
