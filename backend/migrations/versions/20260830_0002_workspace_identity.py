"""Add Google Workspace identity linkage to users."""

from alembic import op
import sqlalchemy as sa

from app.models.user import User

revision = "20260830_0002"
down_revision = "20260826_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        User.__table__.create(bind=bind, checkfirst=True)
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "google_subject" not in columns:
        op.add_column("users", sa.Column("google_subject", sa.String(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_google_subject" not in indexes:
        op.create_index(
            "ix_users_google_subject",
            "users",
            ["google_subject"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("users"):
        return
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    if "ix_users_google_subject" in indexes:
        op.drop_index("ix_users_google_subject", table_name="users")
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "google_subject" in columns:
        op.drop_column("users", "google_subject")
