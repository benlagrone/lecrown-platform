from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.intake import IntakeLeadSubmission
from app.schemas.intake import IntakeLeadCreate
from app.services import intake_service


class IntakeServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_lead_source = intake_service.settings.espocrm_lead_source
        self.original_allowed_extra_fields = list(intake_service.settings.espocrm_allowed_extra_fields)

    def tearDown(self) -> None:
        intake_service.settings.espocrm_lead_source = self.original_lead_source
        intake_service.settings.espocrm_allowed_extra_fields = self.original_allowed_extra_fields

    def test_build_delivery_payload_maps_context_into_description_for_espo_lead(self) -> None:
        intake_service.settings.espocrm_lead_source = "Web Site"
        intake_service.settings.espocrm_allowed_extra_fields = []

        payload = IntakeLeadCreate(
            source_site="simpler.grants.gov",
            source_type="government_contract",
            form_provider="grants_gov",
            form_name="grant_opportunity",
            external_entry_id="ED-GRANT-26-035",
            page_url="https://simpler.grants.gov/opportunity/example",
            business_context="LeCrown Development",
            product_context="Government Contract",
            lead={
                "firstName": "Government",
                "lastName": "ED-GRANT-26-035",
                "description": "Grant opportunity details",
                "source": "Grants.gov Opportunities",
                "businessUnit": "LeCrown Development",
                "productType": "Government Contract",
            },
        )

        delivery_payload = intake_service._build_delivery_payload(payload)

        self.assertEqual("Government", delivery_payload["firstName"])
        self.assertEqual("ED-GRANT-26-035", delivery_payload["lastName"])
        self.assertEqual("Web Site", delivery_payload["source"])
        self.assertNotIn("businessUnit", delivery_payload)
        self.assertNotIn("productType", delivery_payload)
        self.assertIn("Lead source: Grants.gov Opportunities", delivery_payload["description"])
        self.assertIn("Business context: LeCrown Development", delivery_payload["description"])
        self.assertIn("Product context: Government Contract", delivery_payload["description"])
        self.assertIn("Source site: simpler.grants.gov", delivery_payload["description"])

    def test_build_delivery_payload_keeps_configured_custom_fields(self) -> None:
        intake_service.settings.espocrm_allowed_extra_fields = ["businessUnit"]

        payload = IntakeLeadCreate(
            source_site="example.com",
            business_context="LeCrown Development",
            lead={
                "lastName": "Website Lead",
                "businessUnit": "LeCrown Development",
                "productType": "Government Contract",
            },
        )

        delivery_payload = intake_service._build_delivery_payload(payload)

        self.assertEqual("LeCrown Development", delivery_payload["businessUnit"])
        self.assertNotIn("productType", delivery_payload)

    def test_retry_rebuilds_stored_delivery_payload_before_sending(self) -> None:
        intake_service.settings.espocrm_lead_source = "Web Site"
        intake_service.settings.espocrm_allowed_extra_fields = []
        engine = create_engine("sqlite:///:memory:", future=True)
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=engine)

        raw_payload = {
            "source_site": "simpler.grants.gov",
            "source_type": "government_contract",
            "business_context": "LeCrown Development",
            "product_context": "Government Contract",
            "lead": {
                "firstName": "Government",
                "lastName": "ED-GRANT-26-035",
                "source": "Grants.gov Opportunities",
                "businessUnit": "LeCrown Development",
                "productType": "Government Contract",
            },
        }
        stale_delivery_payload = {
            "firstName": "Government",
            "lastName": "ED-GRANT-26-035",
            "source": "Grants.gov Opportunities",
            "businessUnit": "LeCrown Development",
            "productType": "Government Contract",
        }

        with Session() as db:
            submission = IntakeLeadSubmission(
                id="submission-1",
                source_site="simpler.grants.gov",
                source_type="government_contract",
                status="delivery_failed",
                delivery_target="espocrm",
                delivery_status="failed",
                raw_payload=raw_payload,
                normalized_payload={},
                delivery_payload=stale_delivery_payload,
            )
            db.add(submission)
            db.commit()

            with patch("app.services.intake_service.espocrm_service.create_lead", return_value={"id": "lead-1"}) as mock_create:
                retried = intake_service.retry_lead_submission(db, "submission-1")

            sent_payload = mock_create.call_args.args[0]
            self.assertEqual("delivered", retried.delivery_status)
            self.assertEqual("lead-1", retried.delivery_record_id)
            self.assertEqual("Web Site", sent_payload["source"])
            self.assertNotIn("businessUnit", sent_payload)
            self.assertNotIn("productType", sent_payload)
            self.assertEqual(sent_payload, retried.delivery_payload)

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
