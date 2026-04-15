import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.invoice import GeneratedInvoice, InvoiceSequence
from app.models.user import User
from app.schemas.invoice import InvoiceRenderRequest
from app.services import invoice_service


class _MockResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


class InvoiceServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="invoice-service-", suffix=".db")
        os.close(fd)
        self.output_dir = tempfile.mkdtemp(prefix="invoice-output-")
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)
        self.user = User(
            id="user_admin_1",
            username="admin",
            email="admin@example.com",
            hashed_password="not-used",
            is_active=True,
            is_admin=True,
        )
        self._settings_backup = {
            "invoice_output_dir": invoice_service.settings.invoice_output_dir,
            "google_oauth_client_id": invoice_service.settings.google_oauth_client_id,
            "google_oauth_client_secret": invoice_service.settings.google_oauth_client_secret,
            "gmail_refresh_token_benjaminlagrone_gmail_com": invoice_service.settings.gmail_refresh_token_benjaminlagrone_gmail_com,
            "gmail_refresh_token_benjamin_lecrownproperties_com": invoice_service.settings.gmail_refresh_token_benjamin_lecrownproperties_com,
        }
        invoice_service.settings.invoice_output_dir = self.output_dir
        invoice_service.settings.google_oauth_client_id = ""
        invoice_service.settings.google_oauth_client_secret = ""
        invoice_service.settings.gmail_refresh_token_benjaminlagrone_gmail_com = ""
        invoice_service.settings.gmail_refresh_token_benjamin_lecrownproperties_com = ""

    def tearDown(self) -> None:
        self.engine.dispose()
        for key, value in self._settings_backup.items():
            setattr(invoice_service.settings, key, value)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        if os.path.isdir(self.output_dir):
            for root, dirs, files in os.walk(self.output_dir, topdown=False):
                for name in files:
                    os.remove(Path(root) / name)
                for name in dirs:
                    os.rmdir(Path(root) / name)
            os.rmdir(self.output_dir)

    def test_company_defaults_follow_spec(self) -> None:
        development_defaults = invoice_service.get_invoice_defaults("lecrown_development")
        properties_defaults = invoice_service.get_invoice_defaults("lecrown_properties")

        self.assertEqual(
            "time_entry",
            development_defaults["defaults"]["default_composition_mode"],
        )
        self.assertEqual(
            "benjaminlagrone@gmail.com",
            development_defaults["defaults"]["sender_mailbox"],
        )
        self.assertEqual(
            "vendors@revolutiontechnologies.com",
            development_defaults["defaults"]["recipient_email"],
        )
        self.assertEqual(
            "custom",
            properties_defaults["defaults"]["default_composition_mode"],
        )
        self.assertEqual(
            "benjamin@lecrownproperties.com",
            properties_defaults["defaults"]["sender_mailbox"],
        )
        self.assertEqual(
            "edm.kpg@gmail.com",
            properties_defaults["defaults"]["cc_email"],
        )

    def test_render_invoice_persists_pdf_and_sequence(self) -> None:
        payload = InvoiceRenderRequest(
            company_key="lecrown_development",
            sender_mailbox="benjaminlagrone@gmail.com",
            recipient_email="vendors@revolutiontechnologies.com",
            cc_email=None,
            bill_to_name="Revolution Technologies",
            bill_to_phone="+1 321-409-4949",
            bill_to_address="1000 Revolution Technologies\nMelbourne, FL 32901\nUnited States",
            issue_date="2026-04-14",
            due_date="2026-04-28",
            memo="For work performed by Benjamin LaGrone through LeCrown Development Corp.",
            composition_mode="time_entry",
            hourly_rate=155,
            week_1_ending="2026-04-05",
            week_1_hours=40,
            week_2_ending="2026-04-12",
            week_2_hours=40,
        )

        with self.Session() as db:
            invoice = invoice_service.create_rendered_invoice(db, payload=payload, created_by=self.user)
            output_path = invoice_service.get_download_path(invoice)
            sequence = db.query(InvoiceSequence).filter_by(
                company_key="lecrown_development",
                invoice_year=2026,
            ).one()

        self.assertEqual("LCB-2026-0001", invoice.invoice_number)
        self.assertEqual("rendered", invoice.status)
        self.assertEqual(1240000, invoice.total_cents)
        self.assertTrue(output_path.exists())
        self.assertEqual(b"%PDF", output_path.read_bytes()[:4])
        self.assertEqual(1, sequence.last_sequence)

    def test_create_invoice_draft_records_gmail_metadata(self) -> None:
        invoice_service.settings.google_oauth_client_id = "client-id"
        invoice_service.settings.google_oauth_client_secret = "client-secret"
        invoice_service.settings.gmail_refresh_token_benjamin_lecrownproperties_com = "refresh-token"

        payload = InvoiceRenderRequest(
            company_key="lecrown_properties",
            sender_mailbox="benjamin@lecrownproperties.com",
            recipient_email="kensington.obh@gmail.com",
            cc_email="edm.kpg@gmail.com",
            bill_to_name="Blue Commerce",
            bill_to_phone=None,
            bill_to_address="12518 Boheme Drive\nHouston, TX 77024",
            issue_date="2026-04-14",
            due_date="2026-04-21",
            memo="Repair work completed for Blue Commerce.",
            composition_mode="custom",
            custom_line_items=[
                {
                    "description": "Repair work",
                    "amount": 500,
                },
                {
                    "description": "Tax",
                    "amount": 41.25,
                },
            ],
        )

        with patch.object(
            invoice_service.requests,
            "post",
            side_effect=[
                _MockResponse({"access_token": "access-token"}),
                _MockResponse({"id": "draft_123", "message": {"id": "msg_123"}}),
            ],
        ):
            with self.Session() as db:
                invoice = invoice_service.create_invoice_draft(db, payload=payload, created_by=self.user)
                stored = db.query(GeneratedInvoice).filter_by(id=invoice.id).one()

        self.assertEqual("draft_created", invoice.status)
        self.assertEqual("draft_123", invoice.gmail_draft_id)
        self.assertEqual(50000, invoice.subtotal_cents)
        self.assertEqual(54125, invoice.total_cents)
        self.assertEqual("msg_123", stored.gmail_message_id)


if __name__ == "__main__":
    unittest.main()
