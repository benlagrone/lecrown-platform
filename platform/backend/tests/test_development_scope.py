import unittest

from fastapi import HTTPException

from app.core.database import Base
from app.core.tenant import ensure_valid_tenant
from app.main import app
from app.services.invoice_service import get_invoice_defaults, InvoiceValidationError


class DevelopmentScopeTests(unittest.TestCase):
    def test_development_routes_remain_and_brokerage_routes_are_absent(self):
        paths = app.openapi()["paths"]
        for path in ("/content/create", "/contracts/list", "/intake/lead", "/invoice/render", "/billing/checkout/session", "/auth/login"):
            self.assertIn(path, paths)
        for prefix in ("/backoffice", "/client-portal", "/documents", "/inquiry"):
            self.assertFalse(any(path.startswith(prefix) for path in paths), prefix)

    def test_properties_tenant_is_rejected(self):
        self.assertEqual("development", ensure_valid_tenant("development"))
        with self.assertRaises(HTTPException) as error:
            ensure_valid_tenant("properties")
        self.assertEqual(422, error.exception.status_code)

    def test_properties_invoice_profile_is_rejected(self):
        self.assertEqual("lecrown_development", get_invoice_defaults("lecrown_development")["defaults"]["company_key"])
        with self.assertRaises(InvoiceValidationError):
            get_invoice_defaults("lecrown_properties")

    def test_registered_models_exclude_brokerage_records(self):
        for table in ("brokerages", "representations", "transactions", "documents", "client_portal_grants", "inquiries"):
            self.assertNotIn(table, Base.metadata.tables)


if __name__ == "__main__":
    unittest.main()
