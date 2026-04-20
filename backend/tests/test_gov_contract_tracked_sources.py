from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.services import gov_contract_service


def mock_html_response(html: str, *, status_code: int = 200) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.raise_for_status.return_value = None
    response.text = html
    return response


class GovContractTrackedSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="gov-contract-tracked-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_refresh_tracked_procurement_sources_records_load_and_probe_statuses(self) -> None:
        austin_html = """
        <html>
          <body>
            <div class="portlet-body">
              <div class="well parent">
                <div class="td-space-left clearfix child">
                  <strong><a href="solicitation_details.cfm?sid=144136">IFQ 6200 AJC1021</a></strong>
                  <a href="solicitation_details.cfm?sid=144136">View Details</a>
                  <span>Due Date:</span>
                  <span>04/20/2030 at 4PM</span>
                  <span>Pressure Treated Lumber</span>
                  <p>Treated lumber purchase for infrastructure work.</p>
                </div>
              </div>
            </div>
          </body>
        </html>
        """
        san_antonio_html = """
        <html>
          <body>
            <table>
              <tr>
                <th>Description</th><th>Type</th><th>Department</th><th>Release</th><th>Blackout</th><th>Deadline</th>
              </tr>
              <tr>
                <td><a href="Content.aspx?id=6139&page=Default">6100019339 Replacement of Auto Glass</a></td>
                <td>Invitation for Bids</td>
                <td>BES</td>
                <td>03/25/2030</td>
                <td>N/A</td>
                <td>04/17/2030 Extended to 04/20/2030</td>
              </tr>
            </table>
          </body>
        </html>
        """
        bidnet_html = """
        <html>
          <body>
            <table>
              <tr><th>Open Solicitations</th></tr>
              <tr>
                <td>
                  <a href="/texas/solicitations/open-bids/Audit-Management-System/0000406245?purchasingGroupId=8407551&origin=2">
                    166-KS Audit Management System Texas Calendar Published 04/17/2030 Clock Closing 05/12/2030
                  </a>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """
        dallas_bidnet_html = """
        <html>
          <body>
            <table>
              <tr><th>Open Solicitations</th></tr>
              <tr>
                <td>
                  <a href="/texas/solicitations/open-bids/Beverage-Snack-and-Food-Vending-Machine-Services/0000419081?purchasingGroupId=8407551&origin=2">
                    2026-024-7109 Beverage, Snack, and Food Vending Machine Services Texas Calendar Published 04/09/2030 Clock Closing 05/21/2030
                  </a>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """
        houston_metro_html = """
        <html>
          <body>
            <h2>Open Procurements</h2>
            <table>
              <tr><th>Solicitation Number</th><th>Title</th><th>Close Date</th></tr>
              <tr>
                <td>IFB-Doc2091329922</td>
                <td>Purchase and Delivery of Engines for METRO's Transit Buses</td>
                <td>April 22, 2030 2 PM</td>
              </tr>
            </table>
          </body>
        </html>
        """
        bonfire_html = """
        <html><head><title>Portal</title></head><body>
          Working ... WARNING: This site was designed to use Javascript
        </body></html>
        """
        ionwave_html = "<html><body>Just a moment... Enable JavaScript and cookies to continue</body></html>"
        dallas_official_html = """
        <html>
          <body>
            <table>
              <tr><th>Solicitation Number</th><th>Title</th></tr>
              <tr><td>2026-016-7101</td><td>Replacement of Air Handler Units</td></tr>
            </table>
          </body>
        </html>
        """
        blank_shell_html = ""
        dart_html = """
        <html>
          <body>
            <h2>Upcoming Procurements</h2>
            <div>Upcoming Procurement Opportunities is a list of requirements expected within 30 to 60 days.</div>
          </body>
        </html>
        """
        hgac_html = """
        <html>
          <body>
            <iframe src="https://procurement.opengov.com/portal/embed/h-gac/project-list?departmentId=all&status=all"></iframe>
          </body>
        </html>
        """

        responses = {
            "https://financeonline.austintexas.gov/afo/account_services/solicitation/solicitations.cfm": mock_html_response(
                austin_html
            ),
            "https://webapp1.sanantonio.gov/BidContractOpps/Default.aspx": mock_html_response(san_antonio_html),
            "https://fortworthtexas.bonfirehub.com/portal/?tab=openOpportunities": mock_html_response(bonfire_html),
            "https://elpasotexas.ionwave.net/SourcingEvents.aspx?SourceType=1": mock_html_response(ionwave_html),
            "https://harriscountytx.bonfirehub.com/portal/?tab=openOpportunities": mock_html_response(bonfire_html),
            "https://www.bidnetdirect.com/texas/traviscounty": mock_html_response(bidnet_html),
            "https://tarrantcountytx.ionwave.net/SourcingEvents.aspx?SourceType=1": mock_html_response(ionwave_html),
            "https://collincountytx.ionwave.net/ActiveContractList.aspx": mock_html_response(ionwave_html),
            "https://www.dallascounty.org/departments/purchasing/current-business-ops.php": mock_html_response(
                dallas_official_html
            ),
            "https://www.bidnetdirect.com/texas/dallas-county/solicitations/open-bids?selectedContent=BUYER": mock_html_response(
                dallas_bidnet_html
            ),
            "https://vendors.planetbids.com/portal/39494/bo/bo-search": mock_html_response(
                blank_shell_html,
                status_code=202,
            ),
            "https://www.ridemetro.org/about/business-to-business/procurement-opportunities": mock_html_response(
                houston_metro_html
            ),
            "https://dart.org/about/doing-business/procurement#upcomingprocurements": mock_html_response(dart_html),
            "https://www.h-gac.com/procurement": mock_html_response(hgac_html),
        }

        def fake_get(url: str, *args, **kwargs) -> Mock:
            if url not in responses:
                raise AssertionError(f"Unexpected URL: {url}")
            return responses[url]

        with self.Session() as db:
            with patch("app.services.gov_contract_service.requests.get", side_effect=fake_get):
                runs = gov_contract_service.refresh_tracked_procurement_sources(db)

            statuses = {run.source: run.status for run in runs}
            self.assertEqual("completed", statuses[gov_contract_service.AUSTIN_AFO_SOURCE_NAME])
            self.assertEqual("completed", statuses[gov_contract_service.SAN_ANTONIO_BIDS_SOURCE_NAME])
            self.assertEqual("completed", statuses[gov_contract_service.TRAVIS_COUNTY_BIDNET_SOURCE_NAME])
            self.assertEqual("completed", statuses[gov_contract_service.DALLAS_COUNTY_BIDNET_SOURCE_NAME])
            self.assertEqual("completed", statuses[gov_contract_service.HOUSTON_METRO_PROCUREMENT_SOURCE_NAME])
            self.assertEqual("manual_review", statuses[gov_contract_service.FORT_WORTH_BONFIRE_SOURCE_NAME])
            self.assertEqual("blocked", statuses[gov_contract_service.EL_PASO_IONWAVE_SOURCE_NAME])
            self.assertEqual("cataloged", statuses[gov_contract_service.DALLAS_COUNTY_OFFICIAL_SOURCE_NAME])
            self.assertEqual("manual_review", statuses[gov_contract_service.CAPMETRO_PLANETBIDS_SOURCE_NAME])
            self.assertEqual("manual_review", statuses[gov_contract_service.HGAC_PROCUREMENT_SOURCE_NAME])

            austin_items = gov_contract_service.list_contracts(
                db,
                limit=20,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.AUSTIN_AFO_SOURCE_NAME,
            )
            self.assertEqual(1, len(austin_items))
            self.assertEqual("Pressure Treated Lumber", austin_items[0].title)

            metro_items = gov_contract_service.list_contracts(
                db,
                limit=20,
                matches_only=False,
                open_only=False,
                source=gov_contract_service.HOUSTON_METRO_PROCUREMENT_SOURCE_NAME,
            )
            self.assertEqual(1, len(metro_items))
            self.assertEqual("IFB-Doc2091329922", metro_items[0].solicitation_id)

            tracked_sources = gov_contract_service.list_tracked_sources(db)
            self.assertEqual(len(gov_contract_service.PROCUREMENT_SOURCE_DEFINITIONS), len(tracked_sources))
            austin_source = next(
                source for source in tracked_sources if source["source"] == gov_contract_service.AUSTIN_AFO_SOURCE_NAME
            )
            self.assertEqual("completed", austin_source["latest_run_status"])
            self.assertEqual(1, austin_source["stored_opportunity_count"])
            self.assertEqual("Weekly HTML card parser", austin_source["automation_summary"])


if __name__ == "__main__":
    unittest.main()
