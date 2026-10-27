"""Store explicitly granted invitation roles without changing existing users."""

from alembic import op
import sqlalchemy as sa

from app.models.user import UserInvite

revision = "20261027_0003"
down_revision = "20260830_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("user_invites"):
        UserInvite.__table__.create(bind=bind, checkfirst=True)
        return
    if "is_admin" not in {column["name"] for column in inspector.get_columns("user_invites")}:
        op.add_column("user_invites", sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_invites") and "is_admin" in {
        column["name"] for column in inspector.get_columns("user_invites")
    }:
        op.drop_column("user_invites", "is_admin")
