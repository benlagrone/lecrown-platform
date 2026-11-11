import importlib.util
import sys
import unittest
from pathlib import Path

# Load the actual schema module
spec = importlib.util.spec_from_file_location('intake_schema', 'platform/backend/app/schemas/intake.py')
intake_module = importlib.util.module_from_spec(spec)
sys.modules['intake_schema'] = intake_module
spec.loader.exec_module(intake_module)

from pydantic import ValidationError

class TestIntakeAudit(unittest.TestCase):
    def test_valid_payload(self):
        """Test that a valid payload passes validation"""
        payload = {
            "source_site": "example.invalid",
            "business_context": "Synthetic tenant",
            "metadata": {"untrusted": True},
            "lead": {
                "firstName": "Synthetic",
                "unknown_field": "untrusted"
            }
        }

        # This should pass validation
        result = intake_module.IntakeLeadCreate.model_validate(payload)
        self.assertEqual(result.source_site, "example.invalid")
        self.assertEqual(result.business_context, "Synthetic tenant")
        self.assertTrue(result.metadata["untrusted"])
        self.assertEqual(result.lead.firstName, "Synthetic")

    def test_missing_source_site(self):
        """Test that missing source_site fails validation"""
        payload = {
            "source_site": "",
            "lead": {"firstName": "Synthetic"}
        }

        # This should fail validation
        with self.assertRaises(ValidationError):
            intake_module.IntakeLeadCreate.model_validate(payload)

    def test_missing_contact_data(self):
        """Test that missing contact data fails validation"""
        payload = {
            "source_site": "example.invalid",
            "lead": {}
        }

        # This should fail validation
        with self.assertRaises(ValidationError):
            intake_module.IntakeLeadCreate.model_validate(payload)

    def test_blank_contact_fields(self):
        """Test that blank contact fields fail validation"""
        payload = {
            "source_site": "example.invalid",
            "lead": {"firstName": "   "}
        }

        # This should fail validation
        with self.assertRaises(ValidationError):
            intake_module.IntakeLeadCreate.model_validate(payload)

    def test_unknown_lead_fields(self):
        """Test that unknown lead fields are accepted"""
        payload = {
            "source_site": "example.invalid",
            "lead": {
                "firstName": "Synthetic",
                "unknown_field": "untrusted"
            }
        }

        # This should pass validation and preserve unknown fields
        result = intake_module.IntakeLeadCreate.model_validate(payload)
        self.assertEqual(result.lead.model_extra['unknown_field'], 'untrusted')

    def test_arbitrary_metadata(self):
        """Test that arbitrary metadata is accepted"""
        payload = {
            "source_site": "example.invalid",
            "metadata": {
                "untrusted": True,
                "another_value": "test",
                "nested": {"deep": "value"}
            },
            "lead": {"firstName": "Synthetic"}
        }

        # This should pass validation
        result = intake_module.IntakeLeadCreate.model_validate(payload)
        self.assertTrue(result.metadata["untrusted"])
        self.assertEqual(result.metadata["another_value"], "test")
        self.assertEqual(result.metadata["nested"]["deep"], "value")

if __name__ == '__main__':
    unittest.main()