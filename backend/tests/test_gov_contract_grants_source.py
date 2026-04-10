from __future__ import annotations

import csv
import io
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


GRANTS_EXPORT_HEADERS = [
    "opportunity_id",
    "opportunity_number",
    "opportunity_title",
    "opportunity_status",
    "agency_code",
    "category",
    "category_explanation",
    "post_date",
    "close_date",
    "close_date_description",
    "archive_date",
    "is_cost_sharing",
    "expected_number_of_awards",
    "estimated_total_program_funding",
    "award_floor",
    "award_ceiling",
    "additional_info_url",
    "additional_info_url_description",
    "opportunity_assistance_listings",
    "funding_instruments",
    "funding_categories",
    "funding_category_description",
    "applicant_types",
    "applicant_eligibility_description",
    "agency_name",
    "top_level_agency_name",
    "agency_contact_description",
    "agency_email_address",
    "is_forecast",
    "forecasted_post_date",
    "forecasted_close_date",
    "forecasted_close_date_description",
    "forecasted_award_date",
    "forecasted_project_start_date",
    "fiscal_year",
    "created_at",
    "updated_at",
    "url",
    "summary_description",
]


def build_grants_row(
    opportunity_id: str,
    *,
    opportunity_number: str,
    title: str,
    summary_description: str,
    agency_name: str,
    top_level_agency_name: str,
    opportunity_status: str = "posted",
    close_date: str = "2030-05-11",
    archive_date: str = "",
    funding_instruments: str = "grant",
    funding_categories: str = "science_technology_and_other_research_and_development",
    applicant_types: str = "small_businesses;other",
) -> dict[str, str]:
    return {
        "opportunity_id": opportunity_id,
        "opportunity_number": opportunity_number,
        "opportunity_title": title,
        "opportunity_status": opportunity_status,
        "agency_code": "NSF",
        "category": "discretionary",
        "category_explanation": "",
        "post_date": "2026-04-08",
        "close_date": close_date,
        "close_date_description": "",
        "archive_date": archive_date,
        "is_cost_sharing": "False",
        "expected_number_of_awards": "3",
        "estimated_total_program_funding": "$1000000",
        "award_floor": "$50000",
        "award_ceiling": "$500000",
        "additional_info_url": "https://example.gov/info",
        "additional_info_url_description": "Full notice",
        "opportunity_assistance_listings": "47.076",
        "funding_instruments": funding_instruments,
        "funding_categories": funding_categories,
        "funding_category_description": "",
        "applicant_types": applicant_types,
        "applicant_eligibility_description": "See notice for full applicant rules.",
        "agency_name": agency_name,
        "top_level_agency_name": top_level_agency_name,
        "agency_contact_description": "Program team",
        "agency_email_address": "grants@example.gov",
        "is_forecast": "False",
        "forecasted_post_date": "",
        "forecasted_close_date": "",
        "forecasted_close_date_description": "",
        "forecasted_award_date": "",
        "forecasted_project_start_date": "",
        "fiscal_year": "2026",
        "created_at": "2026-04-08T10:00:00Z",
        "updated_at": "2026-04-08T12:00:00Z",
        "url": f"https://simpler.grants.gov/opportunity/{opportunity_id}",
        "summary_description": summary_description,
    }


def build_grants_csv(*rows: dict[str, str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=GRANTS_EXPORT_HEADERS)
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in GRANTS_EXPORT_HEADERS})
    return output.getvalue()


def mock_csv_response(csv_text: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.text = csv_text
    return response


class GovContractGrantsSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="gov-contract-grants-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fetch_grants_contracts_builds_records_from_csv_export(self) -> None:
        csv_text = build_grants_csv(
            build_grants_row(
                "grant-1001",
                opportunity_number="GRANT-1001",
                title="Small business roofing resilience grant",
                summary_description="Roofing resilience and facility rehabilitation funding for small businesses.",
                agency_name="U.S. National Science Foundation",
                top_level_agency_name="U.S. National Science Foundation",
            ),
            build_grants_row(
                "grant-1002",
                opportunity_number="GRANT-1002",
                title="Janitorial workforce innovation grant",
                summary_description="Custodial workforce innovation support.",
                agency_name="Department of Labor",
                top_level_agency_name="Department of Labor",
            ),
        )

        with patch("app.services.gov_contract_service.requests.get", return_value=mock_csv_response(csv_text)):
            result = gov_contract_service.fetch_grants_contracts()

        self.assertEqual(2, len(result.records))
        self.assertEqual(2, result.source_total_records)
        self.assertEqual("grants_gov:grant-1001", result.records[0].source_key)
        self.assertEqual("GRANT-1001", result.records[0].solicitation_id)
        self.assertIn("Small business roofing resilience grant", result.csv_text)
        self.assertIn("Funding Instruments: grant", result.records[0].nigp_codes or "")

    def test_refresh_grants_contracts_stores_and_scores_opportunities(self) -> None:
        csv_text = build_grants_csv(
            build_grants_row(
                "grant-2001",
                opportunity_number="GRANT-2001",
                title="Property rehabilitation pilot grant",
                summary_description="Property rehabilitation, roofing, and facility maintenance funding.",
                agency_name="Department of Housing and Urban Development",
                top_level_agency_name="Department of Housing and Urban Development",
                close_date="2030-06-01",
            ),
            build_grants_row(
                "grant-2002",
                opportunity_number="GRANT-2002",
                title="Archived biomedical research award",
                summary_description="Biomedical research only.",
                agency_name="National Institutes of Health",
                top_level_agency_name="Department of Health and Human Services",
                close_date="2024-01-01",
                archive_date="2024-01-02",
            ),
        )

        with self.Session() as db:
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="property rehabilitation", weight=8))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="roofing", weight=5))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="facility maintenance", weight=6))
            db.commit()

            with patch("app.services.gov_contract_service.requests.get", return_value=mock_csv_response(csv_text)):
                run = gov_contract_service.refresh_grants_contracts(db)

            self.assertEqual(gov_contract_service.GRANTS_GOV_SOURCE_NAME, run.source)
            self.assertEqual(2, run.total_records)
            self.assertEqual(1, run.matched_records)
            self.assertEqual(1, run.open_records)

            all_items = gov_contract_service.list_contracts(
                db,
                limit=10,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.GRANTS_GOV_SOURCE_NAME,
            )
            self.assertEqual(2, len(all_items))

            open_item = next(item for item in all_items if item.source_key == "grants_gov:grant-2001")
            closed_item = next(item for item in all_items if item.source_key == "grants_gov:grant-2002")

            self.assertTrue(open_item.is_open)
            self.assertTrue(open_item.is_match)
            self.assertGreater(open_item.priority_score, 0)
            self.assertEqual(
                "Department of Housing and Urban Development",
                open_item.raw_payload["top_level_agency_name"],
            )

            self.assertFalse(closed_item.is_open)
            self.assertFalse(closed_item.is_match)

    def test_serialized_grants_opportunity_uses_summary_for_it_category_and_auto_tags(self) -> None:
        csv_text = build_grants_csv(
            build_grants_row(
                "grant-3001",
                opportunity_number="GRANT-3001",
                title="Small business modernization accelerator",
                summary_description=(
                    "Cybersecurity modernization, cloud services migration, and help desk support "
                    "for small businesses."
                ),
                agency_name="Department of Commerce",
                top_level_agency_name="Department of Commerce",
                close_date="2030-07-01",
            )
        )

        with self.Session() as db:
            with patch("app.services.gov_contract_service.requests.get", return_value=mock_csv_response(csv_text)):
                gov_contract_service.refresh_grants_contracts(db)

            all_items = gov_contract_service.list_contracts(
                db,
                limit=10,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.GRANTS_GOV_SOURCE_NAME,
            )
            self.assertEqual(1, len(all_items))

            serialized_item = gov_contract_service.serialize_opportunity(all_items[0])
            self.assertEqual(["it_services"], serialized_item.opportunity_categories)
            self.assertIn("Grant", serialized_item.auto_tags)
            self.assertIn("IT services", serialized_item.auto_tags)
            self.assertIn("Cybersecurity", serialized_item.auto_tags)
            self.assertIn("Cloud services", serialized_item.auto_tags)


if __name__ == "__main__":
    unittest.main()
