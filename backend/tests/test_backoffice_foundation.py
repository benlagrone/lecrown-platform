import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import create_privileged_token, decode_access_token
from app.models.backoffice import AuditEvent, DocumentVersion
from app.models.user import User
from app.services import auth_service, authorization_service, backoffice_service, document_service
from app.utils.helpers import new_uuid


class BackofficeFoundationTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="backoffice-", suffix=".db")
        os.close(fd)
        self.storage_dir = tempfile.TemporaryDirectory(prefix="backoffice-documents-")
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        self.storage_dir.cleanup()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _user(self, db, username: str, *, admin: bool = False) -> User:
        user = User(
            id=new_uuid(),
            username=username,
            email=f"{username}@example.test",
            hashed_password=auth_service.hash_password("TestPassword123"),
            is_active=True,
            is_admin=admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def test_first_five_sprint_foundation_creates_scoped_audited_records(self) -> None:
        with patch.object(document_service.settings, "document_storage_dir", self.storage_dir.name):
            with self.Session() as db:
                admin = self._user(db, "admin", admin=True)
                broker = self._user(db, "broker")
                agent = self._user(db, "agent")
                outsider = self._user(db, "outsider")

                brokerage = backoffice_service.create_brokerage(
                    db,
                    actor=admin,
                    legal_name="LeCrown Properties Incorporated",
                    license_number="9017127-BB",
                    designated_broker_user_id=broker.id,
                )
                backoffice_service.grant_role(
                    db,
                    actor=broker,
                    brokerage_id=brokerage.id,
                    user_id=agent.id,
                    role="agent",
                )
                profile = backoffice_service.create_agent_profile(
                    db,
                    actor=broker,
                    brokerage_id=brokerage.id,
                    user_id=agent.id,
                    license_number="TEST-AGENT",
                )
                self.assertEqual("inactive", profile.authority_status)
                profile = backoffice_service.activate_agent_profile(
                    db,
                    actor=broker,
                    brokerage_id=brokerage.id,
                    profile_id=profile.id,
                )
                representation = backoffice_service.create_representation(
                    db,
                    actor=agent,
                    brokerage_id=brokerage.id,
                    client_name="Synthetic Client",
                    representation_type="buyer",
                    responsible_agent_user_id=agent.id,
                    client_crm_reference="Lead:test-1",
                )
                transaction = backoffice_service.create_transaction(
                    db,
                    actor=agent,
                    brokerage_id=brokerage.id,
                    representation_id=representation.id,
                    transaction_type="purchase",
                    responsible_agent_user_id=agent.id,
                    property_reference="synthetic:property-1",
                )
                document, version = document_service.upload(
                    db,
                    actor=agent,
                    brokerage_id=brokerage.id,
                    transaction_id=transaction.id,
                    name="Synthetic buyer agreement",
                    media_type="application/pdf",
                    content=b"%PDF-1.7\nsynthetic fixture\n%%EOF\n",
                )

                self.assertEqual("active", profile.authority_status)
                self.assertEqual("draft", representation.status)
                self.assertEqual("draft", transaction.status)
                self.assertEqual("pending", version.scan_status)
                self.assertEqual("pending", version.render_status)
                self.assertTrue(document_service.resolve_path(version).exists())
                self.assertEqual(version.sha256, document_service.resolve_path(version).name)
                self.assertGreaterEqual(db.query(AuditEvent).count(), 6)
                self.assertTrue(
                    authorization_service.has_permission(
                        db,
                        user=agent,
                        brokerage_id=brokerage.id,
                        permission="documents.prepare",
                    )
                )
                self.assertFalse(
                    authorization_service.has_permission(
                        db,
                        user=outsider,
                        brokerage_id=brokerage.id,
                        permission="documents.prepare",
                    )
                )
                with self.assertRaises(PermissionError):
                    backoffice_service.create_representation(
                        db,
                        actor=outsider,
                        brokerage_id=brokerage.id,
                        client_name="Denied Client",
                        representation_type="buyer",
                        responsible_agent_user_id=outsider.id,
                    )

    def test_document_upload_is_content_addressed_and_rejects_non_pdf(self) -> None:
        with patch.object(document_service.settings, "document_storage_dir", self.storage_dir.name):
            with self.Session() as db:
                admin = self._user(db, "admin", admin=True)
                brokerage = backoffice_service.create_brokerage(
                    db,
                    actor=admin,
                    legal_name="Test Brokerage",
                    license_number=None,
                    designated_broker_user_id=None,
                )
                content = b"%PDF-1.7\nsame bytes\n%%EOF\n"
                _, first = document_service.upload(
                    db,
                    actor=admin,
                    brokerage_id=brokerage.id,
                    name="First",
                    media_type="application/pdf",
                    content=content,
                )
                _, second = document_service.upload(
                    db,
                    actor=admin,
                    brokerage_id=brokerage.id,
                    name="Second",
                    media_type="application/pdf",
                    content=content,
                )
                self.assertEqual(first.storage_key, second.storage_key)
                self.assertEqual(2, db.query(DocumentVersion).count())
                stored_objects = [path for path in Path(self.storage_dir.name).rglob("*") if path.is_file()]
                self.assertEqual(1, len(stored_objects))

                with self.assertRaises(ValueError):
                    document_service.upload(
                        db,
                        actor=admin,
                        brokerage_id=brokerage.id,
                        name="Not PDF",
                        media_type="application/pdf",
                        content=b"not a pdf",
                    )

    def test_privileged_token_is_short_lived_and_bound_to_user(self) -> None:
        with self.Session() as db:
            admin = self._user(db, "admin", admin=True)
            token = create_privileged_token(admin)
            payload = decode_access_token(token)
            self.assertEqual(admin.id, payload["sub"])
            self.assertEqual("privileged_action", payload["purpose"])
            self.assertIn("auth_time", payload)


if __name__ == "__main__":
    unittest.main()
