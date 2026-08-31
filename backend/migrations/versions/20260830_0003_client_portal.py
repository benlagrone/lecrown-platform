"""Add representation-scoped Keycloak client portal grants."""

from alembic import op
import sqlalchemy as sa

revision = "20260830_0003"
down_revision = "20260830_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_portal_grants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("brokerage_id", sa.String(), nullable=False),
        sa.Column("representation_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("keycloak_issuer", sa.String(), nullable=False),
        sa.Column("keycloak_subject", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_by_user_id", sa.String(), nullable=False),
        sa.Column("revoked_by_user_id", sa.String(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "keycloak_issuer",
            "email",
            "representation_id",
            name="uq_client_portal_grant_email_representation",
        ),
        sa.UniqueConstraint(
            "keycloak_issuer",
            "keycloak_subject",
            "representation_id",
            name="uq_client_portal_grant_subject_representation",
        ),
    )
    op.create_index("ix_client_portal_grants_brokerage_id", "client_portal_grants", ["brokerage_id"])
    op.create_index("ix_client_portal_grants_representation_id", "client_portal_grants", ["representation_id"])
    op.create_index("ix_client_portal_grants_email", "client_portal_grants", ["email"])
    op.create_index("ix_client_portal_grants_keycloak_subject", "client_portal_grants", ["keycloak_subject"])
    op.create_index("ix_client_portal_grants_status", "client_portal_grants", ["status"])
    op.create_index("ix_client_portal_grants_created_by_user_id", "client_portal_grants", ["created_by_user_id"])
    op.create_index("ix_client_portal_grants_revoked_by_user_id", "client_portal_grants", ["revoked_by_user_id"])


def downgrade() -> None:
    op.drop_table("client_portal_grants")
