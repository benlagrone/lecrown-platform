import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.backoffice import Brokerage, Document, DocumentVersion, Representation, Transaction
from app.models.client_portal import ClientPortalGrant
from app.models.user import User
from app.services import auth_service, client_portal_service, keycloak_auth_service
from app.services.keycloak_auth_service import KeycloakAuthError, KeycloakIdentity
from app.utils.helpers import new_uuid


class ClientPortalTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="client-portal-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def seed_engagement(self, db):
        admin = User(
            id=new_uuid(),
            username="admin",
            email="admin@lecrownproperties.com",
            hashed_password=auth_service.hash_password("Password123"),
            is_active=True,
            is_admin=True,
        )
        brokerage = Brokerage(id=new_uuid(), legal_name="LeCrown Properties")
        representation = Representation(
            id=new_uuid(),
            brokerage_id=brokerage.id,
            client_name="External Client",
            representation_type="buyer",
            responsible_agent_user_id=admin.id,
            status="active",
        )
        db.add_all([admin, brokerage, representation])
        db.commit()
        return admin, brokerage, representation

    def test_grant_binds_verified_keycloak_subject_and_rejects_another_subject(self) -> None:
        with self.Session() as db:
            admin, _, representation = self.seed_engagement(db)
            grant = client_portal_service.create_grant(
                db,
                actor=admin,
                representation_id=representation.id,
                email="CLIENT@example.com",
            )
            identity = KeycloakIdentity(
                issuer=keycloak_auth_service.settings.keycloak_issuer,
                subject="client-subject",
                email="client@example.com",
                name="External Client",
                roles=frozenset({"lecrown-client"}),
            )
            resolved = client_portal_service.resolve_active_grants(db, identity)
            self.assertEqual([grant.id], [item.id for item in resolved])
            self.assertEqual("client-subject", resolved[0].keycloak_subject)

            other_identity = KeycloakIdentity(
                issuer=identity.issuer,
                subject="different-subject",
                email=identity.email,
                name=identity.name,
                roles=identity.roles,
            )
            with self.assertRaises(PermissionError):
                client_portal_service.resolve_active_grants(db, other_identity)

    def test_portal_records_are_representation_scoped_and_only_show_safe_documents(self) -> None:
        with self.Session() as db:
            admin, brokerage, representation = self.seed_engagement(db)
            other_representation = Representation(
                id=new_uuid(),
                brokerage_id=brokerage.id,
                client_name="Other Client",
                representation_type="seller",
                responsible_agent_user_id=admin.id,
                status="active",
            )
            transaction = Transaction(
                id=new_uuid(),
                brokerage_id=brokerage.id,
                representation_id=representation.id,
                transaction_type="purchase",
                responsible_agent_user_id=admin.id,
                status="under_contract",
            )
            other_transaction = Transaction(
                id=new_uuid(),
                brokerage_id=brokerage.id,
                representation_id=other_representation.id,
                transaction_type="sale",
                responsible_agent_user_id=admin.id,
                status="active",
            )
            shareable = Document(
                id=new_uuid(),
                brokerage_id=brokerage.id,
                transaction_id=transaction.id,
                name="Client copy.pdf",
                classification="client_shareable",
                created_by_user_id=admin.id,
            )
            confidential = Document(
                id=new_uuid(),
                brokerage_id=brokerage.id,
                transaction_id=transaction.id,
                name="Broker notes.pdf",
                classification="brokerage_confidential",
                created_by_user_id=admin.id,
            )
            db.add_all([other_representation, transaction, other_transaction, shareable, confidential])
            db.flush()
            db.add_all([
                DocumentVersion(
                    id=new_uuid(), document_id=shareable.id, version_number=1, sha256="a" * 64,
                    storage_key="sha256/aa/" + "a" * 64, media_type="application/pdf", size_bytes=100,
                    scan_status="clean", render_status="complete", uploaded_by_user_id=admin.id,
                ),
                DocumentVersion(
                    id=new_uuid(), document_id=confidential.id, version_number=1, sha256="b" * 64,
                    storage_key="sha256/bb/" + "b" * 64, media_type="application/pdf", size_bytes=100,
                    scan_status="clean", render_status="complete", uploaded_by_user_id=admin.id,
                ),
            ])
            grant = ClientPortalGrant(
                id=new_uuid(), brokerage_id=brokerage.id, representation_id=representation.id,
                email="client@example.com", keycloak_issuer=keycloak_auth_service.settings.keycloak_issuer,
                keycloak_subject="client-subject", status="active", created_by_user_id=admin.id,
            )
            db.add(grant)
            db.commit()

            representations, transactions, documents = client_portal_service.representation_records(db, [grant])
            self.assertEqual([representation.id], [item.id for item in representations])
            self.assertEqual([transaction.id], [item.id for item in transactions])
            self.assertEqual([shareable.id], [item[0].id for item in documents])

    def test_keycloak_verifier_requires_client_and_role(self) -> None:
        issuer = "https://auth.example/realms/lecrown"
        jwks_url = issuer + "/protocol/openid-connect/certs"
        fake_jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key="key"))
        base_claims = {
            "iss": issuer,
            "sub": "client-subject",
            "email": "client@example.com",
            "email_verified": True,
            "name": "Client",
            "azp": "client-portal",
            "iat": 1,
            "exp": 9999999999,
            "realm_access": {"roles": ["lecrown-client"]},
        }
        with patch.object(keycloak_auth_service.settings, "keycloak_base_url", "https://auth.example"), \
             patch.object(keycloak_auth_service.settings, "keycloak_realm", "lecrown"), \
             patch.object(keycloak_auth_service.settings, "keycloak_client_id", "client-portal"), \
             patch.object(keycloak_auth_service.settings, "keycloak_allowed_roles", ["lecrown-client"]), \
             patch.dict(keycloak_auth_service._jwks_clients, {jwks_url: fake_jwks}, clear=True), \
             patch.object(keycloak_auth_service.jwt, "decode", return_value=base_claims):
            identity = keycloak_auth_service.verify_access_token("signed-token")
            self.assertEqual("client-subject", identity.subject)

        denied_claims = {**base_claims, "realm_access": {"roles": ["offline_access"]}}
        with patch.object(keycloak_auth_service.settings, "keycloak_base_url", "https://auth.example"), \
             patch.object(keycloak_auth_service.settings, "keycloak_realm", "lecrown"), \
             patch.object(keycloak_auth_service.settings, "keycloak_client_id", "client-portal"), \
             patch.object(keycloak_auth_service.settings, "keycloak_allowed_roles", ["lecrown-client"]), \
             patch.dict(keycloak_auth_service._jwks_clients, {jwks_url: fake_jwks}, clear=True), \
             patch.object(keycloak_auth_service.jwt, "decode", return_value=denied_claims):
            with self.assertRaisesRegex(KeycloakAuthError, "client portal access"):
                keycloak_auth_service.verify_access_token("signed-token")


if __name__ == "__main__":
    unittest.main()
