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


def build_sba_page(*rows: str, next_href: str | None = None) -> str:
    next_link = (
        f'<a class="usa-pagination__link usa-pagination__next-page" href="{next_href}" aria-label="Next page">Next</a>'
        if next_href
        else ""
    )
    return f"""
    <html>
      <body>
        <table>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
        <nav class="usa-pagination">
          {next_link}
        </nav>
      </body>
    </html>
    """


def build_sba_row(
    *,
    href: str,
    solicitation_id: str,
    business_name: str,
    description: str,
    closing_date: str,
    performance_start_date: str,
    place_of_performance: str,
    naics: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
) -> str:
    return f"""
    <tr>
      <td class="views-field views-field-title views-align-left views-field-field-subnet-business-name views-field-body">
        <span class="subnet_title"><a href="{href}" hreflang="en">{solicitation_id}</a></span><br />
        <span class="subnet_business_name">{business_name}</span><br />
        <p>{description}</p>
      </td>
      <td>{closing_date}</td>
      <td>{performance_start_date}</td>
      <td>{place_of_performance}</td>
      <td>{naics}</td>
      <td>
        <div><a href="mailto:{contact_email}">{contact_name}</a></div>
        <div><a href="tel:{contact_phone.replace('-', '')}">{contact_phone}</a></div>
      </td>
    </tr>
    """


def mock_html_response(html: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.text = html
    return response


class GovContractSbaSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="gov-contract-sba-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fetch_sba_subnet_contracts_walks_paginated_pages(self) -> None:
        page_one = build_sba_page(
            build_sba_row(
                href="/opportunity/subnet-1001",
                solicitation_id="SUBNET-1001",
                business_name="Prime Builder One",
                description="Roofing rehabilitation subcontract package.",
                closing_date="4/20/2030",
                performance_start_date="8/20/2030",
                place_of_performance="Texas",
                naics="236220: Commercial and Institutional Building Construction",
                contact_name="Alex Prime",
                contact_email="alex@example.com",
                contact_phone="410-555-0101",
            ),
            next_href="?page=1",
        )
        page_two = build_sba_page(
            build_sba_row(
                href="/opportunity/subnet-1002",
                solicitation_id="SUBNET-1002",
                business_name="Prime Builder Two",
                description="Electrical and HVAC subcontracting opportunity.",
                closing_date="4/25/2030",
                performance_start_date="9/01/2030",
                place_of_performance="Louisiana",
                naics="238210: Electrical Contractors and Other Wiring Installation Contractors",
                contact_name="Jordan Prime",
                contact_email="jordan@example.com",
                contact_phone="410-555-0102",
            ),
        )

        def fake_get(url: str, timeout: int) -> Mock:
            if url.endswith("subcontracting-opportunities"):
                return mock_html_response(page_one)
            if url.endswith("?page=1"):
                return mock_html_response(page_two)
            raise AssertionError(f"Unexpected URL: {url}")

        with patch("app.services.gov_contract_service.requests.get", side_effect=fake_get):
            result = gov_contract_service.fetch_sba_subnet_contracts()

        self.assertEqual(2, len(result.records))
        self.assertEqual(2, result.source_total_records)
        self.assertIn("solicitation_id,business_name,description", result.csv_text)
        self.assertEqual("SBA SUBNet", gov_contract_service.SOURCE_LABELS[gov_contract_service.SBA_SUBNET_SOURCE_NAME])
        self.assertEqual(
            "https://www.sba.gov/opportunity/subnet-1001",
            result.records[0].source_url,
        )

    def test_refresh_sba_subnet_contracts_stores_and_scores_opportunities(self) -> None:
        page = build_sba_page(
            build_sba_row(
                href="/opportunity/subnet-2001",
                solicitation_id="SUBNET-2001",
                business_name="Prime Builder Three",
                description="Property rehabilitation and roofing subcontract package.",
                closing_date="4/20/2030",
                performance_start_date="8/20/2030",
                place_of_performance="Georgia",
                naics="236220: Commercial and Institutional Building Construction",
                contact_name="Taylor Prime",
                contact_email="taylor@example.com",
                contact_phone="410-555-0103",
            ),
            build_sba_row(
                href="/opportunity/subnet-2002",
                solicitation_id="SUBNET-2002",
                business_name="Prime Builder Four",
                description="Biomedical lab specialty work.",
                closing_date="4/01/2024",
                performance_start_date="5/01/2024",
                place_of_performance="Maryland",
                naics="541715: Research and Development in the Physical, Engineering, and Life Sciences",
                contact_name="Morgan Prime",
                contact_email="morgan@example.com",
                contact_phone="410-555-0104",
            ),
        )

        with self.Session() as db:
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="property rehabilitation", weight=8))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="roofing", weight=5))
            db.commit()

            with patch("app.services.gov_contract_service.requests.get", return_value=mock_html_response(page)):
                run = gov_contract_service.refresh_sba_subnet_contracts(db)

            self.assertEqual(gov_contract_service.SBA_SUBNET_SOURCE_NAME, run.source)
            self.assertEqual(2, run.total_records)
            self.assertEqual(1, run.matched_records)
            self.assertEqual(1, run.open_records)

            all_items = gov_contract_service.list_contracts(
                db,
                limit=10,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.SBA_SUBNET_SOURCE_NAME,
            )
            self.assertEqual(2, len(all_items))

            open_item = next(item for item in all_items if item.solicitation_id == "SUBNET-2001")
            closed_item = next(item for item in all_items if item.solicitation_id == "SUBNET-2002")

            self.assertTrue(open_item.is_open)
            self.assertTrue(open_item.is_match)
            self.assertEqual("Prime Builder Three", open_item.agency_name)
            self.assertEqual("Taylor Prime", open_item.raw_payload["contact_name"])

            self.assertFalse(closed_item.is_open)
            self.assertFalse(closed_item.is_match)


if __name__ == "__main__":
    unittest.main()
