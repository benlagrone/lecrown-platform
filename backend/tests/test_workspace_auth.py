import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.security import authenticate_access_token, create_access_token
from app.models.user import User
from app.services import auth_service, workspace_auth_service
from app.services.workspace_auth_service import WorkspaceAuthError, WorkspaceIdentity
from app.utils.helpers import new_uuid


class WorkspaceAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="workspace-auth-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_google_workspace_login_creates_member_and_configured_admin(self) -> None:
        identities = [
            WorkspaceIdentity("google-member", "member@lecrownproperties.com", "lecrownproperties.com"),
            WorkspaceIdentity("google-admin", "benjamin@lecrownproperties.com", "lecrownproperties.com"),
        ]
        with patch.object(
            workspace_auth_service,
            "verify_google_credential",
            side_effect=identities,
        ), patch.object(
            workspace_auth_service.settings,
            "workspace_admin_emails",
            ["benjamin@lecrownproperties.com"],
        ):
            with self.Session() as db:
                member = workspace_auth_service.authenticate_workspace_user(
                    db,
                    credential="member-credential",
                )
                admin = workspace_auth_service.authenticate_workspace_user(
                    db,
                    credential="admin-credential",
                )

                self.assertFalse(member.is_admin)
                self.assertTrue(admin.is_admin)
                self.assertEqual("google-member", member.google_subject)
                self.assertEqual("benjamin@lecrownproperties.com", admin.email)

    def test_workspace_login_links_existing_user_by_verified_email(self) -> None:
        with self.Session() as db:
            existing = User(
                id=new_uuid(),
                username="benjamin",
                email="benjamin@lecrownproperties.com",
                hashed_password=auth_service.hash_password("ExistingPassword123"),
                is_active=True,
                is_admin=True,
            )
            db.add(existing)
            db.commit()

            with patch.object(
                workspace_auth_service,
                "verify_google_credential",
                return_value=WorkspaceIdentity(
                    "google-benjamin",
                    "benjamin@lecrownproperties.com",
                    "lecrownproperties.com",
                ),
            ):
                linked = workspace_auth_service.authenticate_workspace_user(
                    db,
                    credential="workspace-credential",
                )

            self.assertEqual(existing.id, linked.id)
            self.assertEqual("google-benjamin", linked.google_subject)
            self.assertTrue(linked.is_admin)

    def test_verifier_rejects_non_workspace_and_nonce_mismatch(self) -> None:
        with patch.object(
            workspace_auth_service.settings,
            "google_login_client_id",
            "client.apps.googleusercontent.com",
        ), patch.object(
            workspace_auth_service.settings,
            "workspace_allowed_domains",
            ["lecrownproperties.com"],
        ), patch.object(
            workspace_auth_service.id_token,
            "verify_oauth2_token",
            return_value={
                "sub": "outside-user",
                "email": "outside@gmail.com",
                "email_verified": True,
                "hd": "gmail.com",
                "nonce": "expected-nonce",
            },
        ):
            with self.assertRaisesRegex(WorkspaceAuthError, "LeCrown Properties"):
                workspace_auth_service.verify_google_credential(
                    "outside-credential",
                    nonce="expected-nonce",
                )

        with patch.object(
            workspace_auth_service.settings,
            "google_login_client_id",
            "client.apps.googleusercontent.com",
        ), patch.object(
            workspace_auth_service.settings,
            "workspace_allowed_domains",
            ["lecrownproperties.com"],
        ), patch.object(
            workspace_auth_service.id_token,
            "verify_oauth2_token",
            return_value={
                "sub": "workspace-user",
                "email": "member@lecrownproperties.com",
                "email_verified": True,
                "hd": "lecrownproperties.com",
                "nonce": "wrong-nonce",
            },
        ):
            with self.assertRaisesRegex(WorkspaceAuthError, "nonce"):
                workspace_auth_service.verify_google_credential(
                    "workspace-credential",
                    nonce="expected-nonce",
                )

    def test_workspace_mode_rejects_legacy_tokens(self) -> None:
        with self.Session() as db:
            user = User(
                id=new_uuid(),
                username="member",
                email="member@lecrownproperties.com",
                google_subject="google-member",
                hashed_password=auth_service.hash_password("ExistingPassword123"),
                is_active=True,
                is_admin=False,
            )
            db.add(user)
            db.commit()

            legacy_token = create_access_token(user)
            workspace_token = create_access_token(user, auth_source="google_workspace")
            with patch.object(
                workspace_auth_service.settings,
                "workspace_auth_required",
                True,
            ), patch.object(
                workspace_auth_service.settings,
                "workspace_allowed_domains",
                ["lecrownproperties.com"],
            ):
                with self.assertRaises(HTTPException):
                    authenticate_access_token(db, legacy_token)
                authenticated = authenticate_access_token(db, workspace_token)
                self.assertEqual(user.id, authenticated.id)


if __name__ == "__main__":
    unittest.main()
