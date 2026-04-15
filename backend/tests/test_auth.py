import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.user import User, UserInvite
from app.services import auth_service


class AuthServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.db_path = tempfile.mkstemp(prefix="auth-service-", suffix=".db")
        os.close(fd)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        Base.metadata.create_all(bind=self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_bootstrap_admin_user_seeds_once_and_authenticates_by_username_or_email(self) -> None:
        with patch.object(auth_service.settings, "admin_username", "admin"), patch.object(
            auth_service.settings,
            "admin_password",
            "InitialPass123",
        ), patch.object(auth_service.settings, "admin_email", "admin@lecrown.local"):
            with self.Session() as db:
                admin_user = auth_service.ensure_bootstrap_admin_user(db)
                second_lookup = auth_service.ensure_bootstrap_admin_user(db)

                self.assertEqual(admin_user.id, second_lookup.id)
                self.assertTrue(admin_user.is_admin)
                self.assertEqual("admin", admin_user.username)
                self.assertEqual("admin@lecrown.local", admin_user.email)
                self.assertIsNotNone(auth_service.authenticate_user(db, "admin", "InitialPass123"))
                self.assertIsNotNone(auth_service.authenticate_user(db, "admin@lecrown.local", "InitialPass123"))

                user_count = db.query(User).count()
                self.assertEqual(1, user_count)

    def test_change_user_password_replaces_previous_password(self) -> None:
        with patch.object(auth_service.settings, "admin_username", "admin"), patch.object(
            auth_service.settings,
            "admin_password",
            "InitialPass123",
        ), patch.object(auth_service.settings, "admin_email", "admin@lecrown.local"):
            with self.Session() as db:
                admin_user = auth_service.ensure_bootstrap_admin_user(db)
                auth_service.change_user_password(
                    db,
                    user=admin_user,
                    current_password="InitialPass123",
                    new_password="ChangedPass123",
                )

                self.assertIsNone(auth_service.authenticate_user(db, "admin", "InitialPass123"))
                self.assertIsNotNone(auth_service.authenticate_user(db, "admin", "ChangedPass123"))

    def test_invite_only_user_lifecycle_supports_accept_and_revoke(self) -> None:
        with patch.object(auth_service.settings, "admin_username", "admin"), patch.object(
            auth_service.settings,
            "admin_password",
            "InitialPass123",
        ), patch.object(auth_service.settings, "admin_email", "admin@lecrown.local"), patch.object(
            auth_service.settings,
            "user_invite_expire_days",
            7,
        ):
            with self.Session() as db:
                admin_user = auth_service.ensure_bootstrap_admin_user(db)

                invite, invite_code = auth_service.create_user_invite(
                    db,
                    current_user=admin_user,
                    email="member@lecrown.local",
                )
                accepted_user = auth_service.accept_user_invite(
                    db,
                    invite_code=invite_code,
                    username="member",
                    password="MemberPass123",
                )

                self.assertFalse(accepted_user.is_admin)
                self.assertEqual("member", accepted_user.username)
                self.assertEqual("member@lecrown.local", accepted_user.email)
                self.assertIsNotNone(auth_service.authenticate_user(db, "member", "MemberPass123"))
                self.assertIsNotNone(auth_service.authenticate_user(db, "member@lecrown.local", "MemberPass123"))

                stored_invite = db.get(UserInvite, invite.id)
                self.assertIsNotNone(stored_invite)
                self.assertIsNotNone(stored_invite.accepted_at)
                self.assertEqual(accepted_user.id, stored_invite.accepted_by_user_id)

                revoked_invite, revoked_code = auth_service.create_user_invite(
                    db,
                    current_user=admin_user,
                    email="second@lecrown.local",
                )
                auth_service.revoke_user_invite(db, invite_id=revoked_invite.id)

                with self.assertRaises(ValueError):
                    auth_service.accept_user_invite(
                        db,
                        invite_code=revoked_code,
                        username="second-user",
                        password="SecondPass123",
                    )


if __name__ == "__main__":
    unittest.main()
