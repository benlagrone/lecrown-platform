import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


class AdminInviteMigrationTest(unittest.TestCase):
    def test_existing_invites_default_to_member_and_users_are_untouched(self):
        spec = importlib.util.spec_from_file_location("admin_invites_migration",
            Path(__file__).resolve().parents[1] / "migrations/versions/20261027_0003_admin_invitations.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection:
                connection.execute(text("CREATE TABLE users (id TEXT PRIMARY KEY, hashed_password TEXT)"))
                connection.execute(text("INSERT INTO users VALUES ('kept', 'unchanged-hash')"))
                connection.execute(text("CREATE TABLE user_invites (id TEXT PRIMARY KEY, email TEXT)"))
                connection.execute(text("INSERT INTO user_invites VALUES ('existing', 'member@example.com')"))
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()
                    migration.upgrade()
                self.assertEqual(0, connection.execute(text("SELECT is_admin FROM user_invites")).scalar())
                self.assertEqual("unchanged-hash", connection.execute(text("SELECT hashed_password FROM users")).scalar())
        finally:
            engine.dispose()

    def test_fresh_database_creates_member_default(self):
        spec = importlib.util.spec_from_file_location("admin_invites_migration_fresh",
            Path(__file__).resolve().parents[1] / "migrations/versions/20261027_0003_admin_invitations.py")
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        engine = create_engine("sqlite:///:memory:")
        try:
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                role = next(c for c in inspect(connection).get_columns("user_invites") if c["name"] == "is_admin")
                self.assertFalse(role["nullable"])
                self.assertIn("0", str(role["default"]))
        finally:
            engine.dispose()
