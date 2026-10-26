from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.gov_contract import GovContractOpportunity, GovContractTrackedSource
from app.services import espocrm_service as espo
from app.services import gov_contract_service as contracts
from app.services import procurement_source_catalog as catalog


def account(account_id="a1", url="https://buyer.bonfirehub.com/portal/", description=None):
    return {"id": account_id, "name": "Buyer", "website": url,
            "description": description or "[RFP source capture 2026-10-26]\nClassification: public forecast or notice page with portal response. Platform: Bonfire."}


def response(payload, status=200):
    result = Mock(status_code=status)
    result.json.return_value = payload
    return result


def project(project_id="123", visibility="1"):
    return {"ProjectID": project_id, "ProjectVisibilityID": visibility, "ReferenceID": "RFP-1",
            "ProjectName": "Construction management", "DateClose": "2030-12-31 17:00:00"}


class AccountPaginationTest(unittest.TestCase):
    def test_complete_snapshot_and_one_auth_header_per_batch(self):
        with patch.object(espo, "_headers", return_value={"X-Api-Key": "test"}) as headers, patch.object(espo, "_base_url", return_value="https://crm.test/api/v1"), patch.object(espo.requests, "get", side_effect=[
            response({"total": 3, "list": [account("a"), account("b")]}),
            response({"total": 3, "list": [account("c")]}),
        ]) as get:
            self.assertEqual(3, len(espo.list_accounts()))
        headers.assert_called_once()
        self.assertEqual(2, get.call_args.kwargs["params"]["offset"])
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_rejects_incomplete_repeated_changed_or_malformed_pages(self):
        for second in ({"total": 2, "list": []}, {"total": 2, "list": [account("a")]},
                       {"total": 3, "list": [account("b")]}, {"list": [account("b")]}, []):
            with self.subTest(second=second), patch.object(espo, "_headers", return_value={}), patch.object(espo, "_base_url", return_value="https://crm.test/api/v1"), patch.object(espo.requests, "get", side_effect=[
                response({"total": 2, "list": [account("a")]}), response(second),
            ]):
                with self.assertRaises(espo.EspoCRMError):
                    espo.list_accounts()

    def test_rejects_redirect_without_exposing_response(self):
        with patch.object(espo, "_headers", return_value={}), patch.object(espo, "_base_url", return_value="https://crm.test/api/v1"), patch.object(espo.requests, "get", return_value=response({"secret": "private"}, 302)):
            with self.assertRaisesRegex(espo.EspoCRMError, "Account read failed"):
                espo.list_accounts()


class ProcurementSourceCatalogTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.mode = patch.object(contracts.settings, "gov_contract_source_catalog", "espocrm")
        self.mode.start()

    def tearDown(self):
        self.mode.stop()
        self.db.close()
        self.engine.dispose()

    def sync(self, accounts):
        with patch.object(espo, "list_accounts", return_value=accounts):
            return catalog.sync(self.db, definitions=contracts.PROCUREMENT_SOURCE_DEFINITIONS,
                                core_sources={item.source for item in contracts.CORE_PROCUREMENT_SOURCE_DEFINITIONS})

    def test_catalog_dedup_identity_and_retirement(self):
        counts = self.sync([account(), account("a2", "https://buyer.bonfirehub.com/portal?tab=openOpportunities"),
                            account("other", "https://another.bonfirehub.com/portal")])
        self.assertEqual(1, counts["duplicate_urls"])
        row = self.db.scalar(select(GovContractTrackedSource).where(GovContractTrackedSource.source == "espocrm_a1"))
        original_id = row.id
        updated = account(url="https://newbuyer.bonfirehub.com/portal")
        updated["name"] = "Renamed Buyer"
        self.sync([updated])
        self.db.refresh(row)
        self.assertEqual(original_id, row.id)
        self.assertEqual("Renamed Buyer", row.label)
        other = self.db.scalar(select(GovContractTrackedSource).where(GovContractTrackedSource.source == "espocrm_other"))
        self.assertFalse(other.active)

    def test_only_classified_sources_and_never_reference_programs(self):
        rows = [account(), account("client", description="A normal customer"),
                account("register", description="Procurement opportunity source. Classification: registration or contract program only."),
                account("overlap", "https://other.bonfirehub.com/portal", "Procurement opportunity source. Classification: overlap with an existing upstream source.")]
        rows[2]["website"] = "https://register.bonfirehub.com/portal"
        self.sync(rows)
        actual = {row.source: row for row in self.db.scalars(select(GovContractTrackedSource)).all()}
        self.assertNotIn("espocrm_client", actual)
        self.assertEqual("reference", actual["espocrm_register"].extraction_mode)
        self.assertEqual("overlap", actual["espocrm_overlap"].extraction_mode)

    def test_legacy_source_key_preserved(self):
        self.sync([account(url="https://harriscountytx.bonfirehub.com/portal/")])
        row = self.db.scalar(select(GovContractTrackedSource))
        self.assertEqual(contracts.HARRIS_COUNTY_BONFIRE_SOURCE_NAME, row.source)
        self.assertEqual("bonfire_public_json", row.extraction_mode)

    def test_jaggaer_buyer_keys_and_unsafe_urls(self):
        self.assertNotEqual(catalog.normalized_url("https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=TAMU"),
                            catalog.normalized_url("https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=UNTS"))
        for url in ("https://buyer.bonfirehub.com.attacker.test/portal", "http://127.0.0.1/portal",
                    "https://buyer.bonfirehub.com:444/portal", "https://user:pass@buyer.bonfirehub.com/portal", "javascript:alert(1)"):
            self.assertIsNone(catalog.bonfire_origin(url))

    def test_crm_failure_preserves_snapshot_and_does_not_crawl(self):
        self.sync([account()])
        with patch.object(espo, "list_accounts", side_effect=espo.EspoCRMError("unavailable")), patch.object(contracts, "fetch_bonfire_contracts") as fetch:
            runs = contracts.refresh_tracked_procurement_sources(self.db)
        self.assertEqual(["failed"], [run.status for run in runs])
        fetch.assert_not_called()
        self.assertTrue(self.db.scalar(select(GovContractTrackedSource).where(GovContractTrackedSource.source == "espocrm_a1")).active)

    def test_empty_catalog_preserves_existing_sources(self):
        self.sync([account()])
        with self.assertRaises(espo.EspoCRMError):
            self.sync([])
        self.assertTrue(self.db.scalar(select(GovContractTrackedSource)).active)

    def test_explicit_static_mode_restores_legacy_registry_only(self):
        self.sync([account()])
        with patch.object(contracts.settings, "gov_contract_source_catalog", "static"):
            sources = contracts.list_tracked_sources(self.db)
        self.assertEqual({item.source for item in contracts.PROCUREMENT_SOURCE_DEFINITIONS},
                         {item["source"] for item in sources})

    def test_refresh_imports_and_repeats_idempotently_then_closes_missing(self):
        payload = {"success": 1, "payload": {"projects": [project(), project(), project("private", "2")]}}
        with patch.object(espo, "list_accounts", return_value=[account()]), patch.object(contracts.requests, "get", return_value=response(payload)) as get:
            for _ in range(2):
                runs = contracts.refresh_tracked_procurement_sources(self.db)
                self.assertEqual(["completed", "completed"], [run.status for run in runs])
            self.assertFalse(get.call_args.kwargs["allow_redirects"])
            rows = self.db.scalars(select(GovContractOpportunity)).all()
            self.assertEqual(1, len(rows))
            self.assertTrue(rows[0].is_open)
            self.assertIn("buyer.bonfirehub.com/opportunities/123", rows[0].source_url)
            self.assertEqual("a1", rows[0].raw_payload["crm_account_id"])
            sources = contracts.list_tracked_sources(self.db)
            self.assertEqual("Public opportunity importer", next(row for row in sources if row["source"] == "espocrm_a1")["automation_summary"])
        with patch.object(espo, "list_accounts", return_value=[account()]), patch.object(contracts.requests, "get", return_value=response({"success": 1, "payload": {"projects": {}}})):
            contracts.refresh_tracked_procurement_sources(self.db)
        self.db.refresh(rows[0])
        self.assertFalse(rows[0].is_open)

    def test_bad_portal_isolated_and_unsupported_not_reported_as_loaded(self):
        with patch.object(espo, "list_accounts", return_value=[account(), account("b", "https://buyer.ionwave.net")]), patch.object(contracts.requests, "get", return_value=response({"payload": "bad"})):
            runs = contracts.refresh_tracked_procurement_sources(self.db)
        self.assertEqual(["completed", "failed", "manual_review"], [run.status for run in runs])

    def test_rate_limit_stops_shared_platform_and_persists_cooldown(self):
        limited = response({}, 429)
        limited.headers = {"Retry-After": "3600"}
        accounts = [account(), account("b", "https://second.bonfirehub.com/portal")]
        with patch.object(espo, "list_accounts", return_value=accounts), patch.object(contracts.requests, "get", return_value=limited) as get:
            runs = contracts.refresh_tracked_procurement_sources(self.db)
            self.assertEqual(["completed", "blocked", "deferred"], [run.status for run in runs])
            self.assertEqual(1, get.call_count)
            runs = contracts.refresh_tracked_procurement_sources(self.db)
            self.assertEqual(["completed", "deferred", "deferred"], [run.status for run in runs])
            self.assertEqual(1, get.call_count)

    def test_bounded_batches_rotate_instead_of_starving_later_buyers(self):
        accounts = [account(), account("b", "https://second.bonfirehub.com/portal")]
        with patch.object(contracts.settings, "gov_contract_portal_batch_size", 1), patch.object(espo, "list_accounts", return_value=accounts), patch.object(contracts.requests, "get", return_value=response({"success": 1, "payload": {"projects": {}}})) as get:
            first = contracts.refresh_tracked_procurement_sources(self.db)
            second = contracts.refresh_tracked_procurement_sources(self.db)
            self.assertEqual("espocrm_a1", first[1].source)
            self.assertEqual("completed", first[1].status)
            self.assertEqual("espocrm_b", second[1].source)
            self.assertEqual("completed", second[1].status)
            self.assertEqual(2, get.call_count)

    def test_bonfire_redirect_is_not_followed(self):
        with patch.object(espo, "list_accounts", return_value=[account()]), patch.object(contracts.requests, "get", return_value=response({}, 302)) as get:
            runs = contracts.refresh_tracked_procurement_sources(self.db)
        self.assertEqual("failed", runs[1].status)
        self.assertIn("redirected", runs[1].error_message)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
