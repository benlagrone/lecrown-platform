"""Include adjacent IT terminology without overwriting administrator weights."""

from alembic import op
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.gov_contract import GovContractKeywordRule
from app.services.gov_contract_service import _normalize_text
from app.utils.helpers import new_uuid

revision = "20261027_0005"
down_revision = "20261027_0004"
branch_labels = None
depends_on = None

TERMS = (
    ("managed security services", 6), ("mssp", 6), ("security operations center", 6),
    ("penetration testing", 6), ("endpoint protection", 6),
    ("identity and access management", 6), ("privileged access management", 6),
    ("mobile application", 5), ("mobile applications", 5), ("mobile app", 5),
    ("electronic content management", 5), ("enterprise content management", 5),
    ("content management system", 5), ("case management system", 5),
    ("computerized maintenance management system", 5), ("computer aided dispatch", 5),
    ("computer assisted mass appraisal", 5), ("data platform", 5), ("data platforms", 5),
    ("databases", 5), ("database administration", 5), ("network cabling", 5), ("virtualization", 5),
)


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("gov_contract_keyword_rules"):
        return
    with Session(bind=bind) as db:
        existing = {_normalize_text(rule.phrase) for rule in db.scalars(select(GovContractKeywordRule))}
        for phrase, weight in TERMS:
            if _normalize_text(phrase) not in existing:
                db.add(GovContractKeywordRule(id=new_uuid(), phrase=phrase, weight=weight))
        db.flush()


def downgrade() -> None:
    # Preserve later user tuning rather than deleting these rules on rollback.
    pass
