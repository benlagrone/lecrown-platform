from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.gov_contract import GovContractKeywordRule
from app.services import gov_contract_service
from app.utils.helpers import new_uuid


def build_federal_listing_item(
    nid: str,
    *,
    title: str,
    body: str,
    department: str,
    organization: str,
    award_status: str,
    contract_type: str = "Firm Fixed Price",
    estimated_award_fy: str = "2026",
    estimated_contract_value: str = "$250K - $499K",
    naics: str = "541519 Other Computer Related Services",
    acquisition_strategy: str = "Other Than Small Business",
    period_start: str = "2026-05-11T12:00:00Z",
    period_end: str = "2027-05-10T12:00:00Z",
    updated_timestamp: int = 1775687456,
) -> dict[str, object]:
    return {
        "pid": nid,
        "nid": nid,
        "rank": {
            "updated": {
                "value": updated_timestamp,
                "render": "04/08/2026",
                "display_tooltip": False,
            }
        },
        "render": {
            "nid": nid,
            "title": title,
            "body": f"<p>{body}</p>",
            "field_result_id": department,
            "field_organization": organization,
            "field_source_listing_id": f"AG{nid}_{updated_timestamp}",
            "field_award_status": award_status,
            "field_contract_type": contract_type,
            "field_estimated_award_fy": estimated_award_fy,
            "field_estimated_contract_v_max": estimated_contract_value,
            "field_naics_code": f"<div>{naics}</div>",
            "field_acquisition_strategy": acquisition_strategy,
            "field_period_of_performance": (
                f'<time datetime="{period_start}">05/11/2026</time> - '
                f'<time datetime="{period_end}">05/10/2027</time>'
            ),
        },
        "values": {
            "nid": nid,
            "title": title,
        },
        "type": "node",
        "tid": None,
        "alias": "/forecast",
    }


def build_federal_payload(*items: dict[str, object], total: int | None = None) -> dict[str, object]:
    return {
        "alias": "forecast",
        "title": "Forecast Tool",
        "menu": {
            "secondary": {
                "export": {
                    "export": True,
                    "label": "Export CSV",
                    "service": "export",
                    "action": "E",
                }
            }
        },
        "listing": {
            "count": len(items),
            "total": total or len(items),
            "view": {
                "title": {"label": "Title"},
                "body": {"label": "Description"},
                "field_result_id": {"label": "Agency"},
                "field_organization": {"label": "Office"},
                "field_estimated_award_fy": {"label": "Estimated Award FY"},
                "field_estimated_contract_v_max": {"label": "Estimated Contract Value"},
                "field_naics_code": {"label": "NAICS"},
                "field_acquisition_strategy": {"label": "Acquisition Strategy"},
                "field_period_of_performance": {"label": "Period of Performance"},
            },
            "data": {
                str(item["nid"]): item for item in items
            },
        },
        "settings": {
            "export": {
                "limit": 3000,
                "batch_size": 500,
            }
        },
        "default": {"_format": "json"},
    }


def mock_response(payload: dict[str, object]) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class GovContractFederalSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="gov-contract-federal-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fetch_federal_forecast_batches_pages_and_builds_csv(self) -> None:
        page_one = build_federal_payload(
            build_federal_listing_item(
                "1001",
                title="Roofing replacement at federal campus",
                body="Roofing replacement services",
                department="General Services Administration",
                organization="Public Buildings Service",
                award_status="Acquisition Planning",
            ),
            build_federal_listing_item(
                "1002",
                title="Custodial support services",
                body="Custodial and janitorial work",
                department="Department of Transportation",
                organization="FHWA",
                award_status="Solicitation Issued",
            ),
            total=3,
        )
        page_two = build_federal_payload(
            build_federal_listing_item(
                "1003",
                title="Elevator modernization",
                body="Elevator controls upgrade",
                department="Department of Veterans Affairs",
                organization="Facilities",
                award_status="Market Research",
            ),
            total=3,
        )

        with patch.object(gov_contract_service.settings, "federal_contract_page_size", 2):
            with patch("app.services.gov_contract_service.requests.get") as mocked_get:
                mocked_get.side_effect = [
                    mock_response(page_one),
                    mock_response(page_two),
                ]

                result = gov_contract_service.fetch_federal_forecast_contracts()

        self.assertEqual(3, len(result.records))
        self.assertEqual(3, result.source_total_records)
        self.assertEqual(2, mocked_get.call_count)
        self.assertEqual("federal_forecast:1001", result.records[0].source_key)
        self.assertIn("_a%5Eg_nid=1001", result.records[0].source_url)
        self.assertIn("Roofing replacement at federal campus", result.csv_text)
        self.assertIn("Title,Description,Agency,Office", result.csv_text)

    def test_refresh_federal_contracts_stores_and_scores_opportunities(self) -> None:
        payload = build_federal_payload(
            build_federal_listing_item(
                "2001",
                title="Federal roofing rehabilitation",
                body="Roofing and rehabilitation package",
                department="General Services Administration",
                organization="Public Buildings Service",
                award_status="Acquisition Planning",
            ),
            build_federal_listing_item(
                "2002",
                title="Awarded software licenses",
                body="Enterprise software licenses",
                department="General Services Administration",
                organization="FAS",
                award_status="Awarded",
            ),
            total=2,
        )

        with self.Session() as db:
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="roofing", weight=5))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="rehabilitation", weight=6))
            db.commit()

            with patch("app.services.gov_contract_service.requests.get", return_value=mock_response(payload)):
                run = gov_contract_service.refresh_federal_contracts(db)

            self.assertEqual(gov_contract_service.FEDERAL_FORECAST_SOURCE_NAME, run.source)
            self.assertEqual(2, run.total_records)
            self.assertEqual(1, run.matched_records)
            self.assertEqual(1, run.open_records)

            all_items = gov_contract_service.list_contracts(
                db,
                limit=10,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.FEDERAL_FORECAST_SOURCE_NAME,
            )
            self.assertEqual(2, len(all_items))

            open_item = next(item for item in all_items if item.source_key == "federal_forecast:2001")
            closed_item = next(item for item in all_items if item.source_key == "federal_forecast:2002")

            self.assertTrue(open_item.is_open)
            self.assertTrue(open_item.is_match)
            self.assertGreater(open_item.priority_score, 0)
            self.assertEqual("General Services Administration", open_item.raw_payload["department"])

            self.assertFalse(closed_item.is_open)
            self.assertFalse(closed_item.is_match)


if __name__ == "__main__":
    unittest.main()
