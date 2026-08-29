"""Create the initial brokerage back-office foundation tables."""

from alembic import op

from app.models.backoffice import (
    AgentProfile,
    AuditEvent,
    Brokerage,
    Document,
    DocumentVersion,
    Office,
    Representation,
    RoleAssignment,
    SupervisorDelegation,
    Team,
    Transaction,
)

revision = "20260826_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    Brokerage.__table__,
    Office.__table__,
    Team.__table__,
    AgentProfile.__table__,
    RoleAssignment.__table__,
    SupervisorDelegation.__table__,
    AuditEvent.__table__,
    Representation.__table__,
    Transaction.__table__,
    Document.__table__,
    DocumentVersion.__table__,
]


def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(TABLES):
        table.drop(bind=bind, checkfirst=True)
