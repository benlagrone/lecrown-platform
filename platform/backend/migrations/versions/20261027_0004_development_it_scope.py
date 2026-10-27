"""Replace inherited property defaults with Development's IT-only business scope."""

from alembic import op
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.gov_contract import GovContractKeywordRule
from app.services.gov_contract_service import DEFAULT_MATCH_RULES, PROPERTY_OPPORTUNITY_RULES, _normalize_text
from app.utils.helpers import new_uuid

revision = "20261027_0004"
down_revision = "20261027_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("gov_contract_keyword_rules"):
        return
    excluded = {_normalize_text(phrase) for phrase, _ in PROPERTY_OPPORTUNITY_RULES}
    with Session(bind=bind) as db:
        retained = set()
        for rule in db.scalars(select(GovContractKeywordRule)).all():
            phrase = _normalize_text(rule.phrase)
            if phrase in excluded or phrase == "technical support":
                db.delete(rule)
            else:
                retained.add(phrase)
        for phrase, weight in DEFAULT_MATCH_RULES:
            if _normalize_text(phrase) not in retained:
                db.add(GovContractKeywordRule(id=new_uuid(), phrase=phrase, weight=weight))
        db.flush()


def downgrade() -> None:
    # Do not reintroduce known false-positive rules or overwrite administrator tuning.
    pass
