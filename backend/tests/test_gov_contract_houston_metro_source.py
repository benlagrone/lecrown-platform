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

HOUSTON_METRO_HTML = """
<html>
  <body>
    <table title="Open Procurements Table">
      <thead>
        <tr>
          <th>Solicitation Number</th>
          <th>Title</th>
          <th>Close Date</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><a href="https://ridemetro.bonfirehub.com/opportunities/216987">IFB Doc 1961886621</a></td>
          <td>Data Center Rehab</td>
          <td>April 29, 2026 2 PM</td>
        </tr>
      </tbody>
    </table>

    <div class="tab-pane-content" data-sf-element="Recently Added">
      <table>
        <thead>
          <tr>
            <th>Project Name</th>
            <th>Procurement Method</th>
            <th>Small Business Goal</th>
            <th>Advertisement Month</th>
            <th>Due Date</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Material Testing</td>
            <td>RFQ</td>
            <td>35%</td>
            <td>March</td>
            <td>May</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="tab-pane-content" data-sf-element="Q2 2026 Forecast">
      <table>
        <thead>
          <tr>
            <th>Projects</th>
            <th>Procurement Method</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Cybersecurity - Privileged Access Management Solution</td>
            <td>DIR</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="tab-pane-content" data-sf-element="Major Construction Projects">
      <table>
        <thead>
          <tr>
            <th>Project Description</th>
            <th>Advertising Date</th>
            <th>Estimated Project Value</th>
            <th>SBE%</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Roof Replacements For BOF's</td>
            <td>Q1 2026</td>
            <td>$10-12 million</td>
            <td>TBD</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="tab-pane-content" data-sf-element="Advance Procurement Notices">
      <p><a href="https://metro.resourcespace.com/?r=18858">METRO Kashmere Bus Operating Facility Petroleum Storage Tank Replacement ></a></p>
      <p><a href="https://metro.resourcespace.com/?r=13903">CMAR Template - Draft ></a></p>
    </div>
  </body>
</html>
"""


def mock_html_response(html: str) -> Mock:
    response = Mock()
    response.raise_for_status.return_value = None
    response.text = html
    return response


class GovContractHoustonMetroSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="gov-contract-houston-metro-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fetch_houston_metro_contracts_parses_open_forecast_major_and_apn_sections(self) -> None:
        with patch(
            "app.services.gov_contract_service.requests.get",
            return_value=mock_html_response(HOUSTON_METRO_HTML),
        ):
            result = gov_contract_service.fetch_houston_metro_contracts()

        self.assertEqual(5, len(result.records))
        self.assertEqual(5, result.source_total_records)

        open_item = next(
            record for record in result.records if record.raw_payload["source_context"] == gov_contract_service.HOUSTON_METRO_OPEN_CONTEXT
        )
        self.assertEqual("IFB Doc 1961886621", open_item.solicitation_id)
        self.assertEqual("Data Center Rehab", open_item.title)
        self.assertEqual("Bonfire", open_item.raw_payload["portal"])
        self.assertEqual("https://ridemetro.bonfirehub.com/opportunities/216987", open_item.source_url)
        self.assertEqual("Open Procurement", open_item.status_name)

        forecast_item = next(
            record for record in result.records if record.raw_payload["source_context"] == gov_contract_service.HOUSTON_METRO_Q2_FORECAST_CONTEXT
        )
        self.assertEqual("DIR", forecast_item.raw_payload["procurement_method"])
        self.assertEqual("Forecast", forecast_item.status_name)

        major_item = next(
            record for record in result.records if record.raw_payload["source_context"] == gov_contract_service.HOUSTON_METRO_MAJOR_CONSTRUCTION_CONTEXT
        )
        self.assertEqual("$10-12 million", major_item.raw_payload["estimated_project_value"])
        self.assertEqual("Q1 2026", major_item.raw_payload["advertising_date"])

        apn_item = next(
            record for record in result.records if record.raw_payload["source_context"] == gov_contract_service.HOUSTON_METRO_APN_CONTEXT
        )
        self.assertEqual("Advance Procurement Notice", apn_item.status_name)
        self.assertNotIn("template", apn_item.title.casefold())
        self.assertEqual("https://metro.resourcespace.com/?r=18858", apn_item.source_url)

    def test_refresh_houston_metro_contracts_stores_records_with_context_and_tags(self) -> None:
        with self.Session() as db:
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="data center", weight=4))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="cybersecurity", weight=6))
            db.add(GovContractKeywordRule(id=new_uuid(), phrase="roofing", weight=5))
            db.commit()

            with patch(
                "app.services.gov_contract_service.requests.get",
                return_value=mock_html_response(HOUSTON_METRO_HTML),
            ):
                run = gov_contract_service.refresh_houston_metro_contracts(db)

            self.assertEqual(gov_contract_service.HOUSTON_METRO_PROCUREMENT_SOURCE_NAME, run.source)
            self.assertEqual(5, run.total_records)
            self.assertEqual(5, run.open_records)
            self.assertGreaterEqual(run.matched_records, 2)

            items = gov_contract_service.list_contracts(
                db,
                limit=10,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.HOUSTON_METRO_PROCUREMENT_SOURCE_NAME,
            )
            self.assertEqual(5, len(items))

            data_center_item = next(item for item in items if item.title == "Data Center Rehab")
            serialized_data_center_item = gov_contract_service.serialize_opportunity(data_center_item)
            self.assertEqual(gov_contract_service.HOUSTON_METRO_OPEN_CONTEXT, serialized_data_center_item.source_context)
            self.assertEqual("Open procurement", serialized_data_center_item.source_context_label)
            self.assertIn("METRO", serialized_data_center_item.auto_tags)
            self.assertIn("Bonfire", serialized_data_center_item.auto_tags)
            self.assertIn("Open procurement", serialized_data_center_item.auto_tags)
            self.assertIn("IT services", serialized_data_center_item.auto_tags)

            major_item = next(item for item in items if item.title == "Roof Replacements For BOF's")
            serialized_major_item = gov_contract_service.serialize_opportunity(major_item)
            self.assertEqual("Major construction", serialized_major_item.source_context_label)
            self.assertIn("Major construction", serialized_major_item.auto_tags)
            self.assertIn("Real estate / property", serialized_major_item.auto_tags)

            apn_item = next(
                item
                for item in items
                if item.raw_payload.get("source_context") == gov_contract_service.HOUSTON_METRO_APN_CONTEXT
            )
            self.assertTrue(apn_item.is_open)


if __name__ == "__main__":
    unittest.main()
