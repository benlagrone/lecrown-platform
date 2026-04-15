from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models.billing  # noqa: F401
    import app.models.content  # noqa: F401
    import app.models.gov_contract  # noqa: F401
    import app.models.intake  # noqa: F401
    import app.models.invoice  # noqa: F401
    import app.models.inquiry  # noqa: F401
    import app.models.user  # noqa: F401

    inspector = inspect(engine)
    had_gov_contract_keyword_rules = inspector.has_table("gov_contract_keyword_rules")
    had_gov_contract_agency_preferences = inspector.has_table("gov_contract_agency_preferences")

    Base.metadata.create_all(bind=engine)
    should_rescore_gov_contracts = _run_lightweight_migrations()
    _seed_bootstrap_admin_user()
    if not had_gov_contract_keyword_rules:
        _seed_gov_contract_keyword_rules()
    if should_rescore_gov_contracts or not had_gov_contract_agency_preferences:
        _backfill_gov_contract_scores()


def _run_lightweight_migrations() -> bool:
    if not settings.database_url.startswith("sqlite"):
        return False

    inspector = inspect(engine)
    if inspector.has_table("users"):
        existing_user_columns = {column["name"] for column in inspector.get_columns("users")}
        user_migrations = {
            "username": "username VARCHAR",
            "is_admin": "is_admin BOOLEAN DEFAULT 0 NOT NULL",
            "updated_at": "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
        }
        with engine.begin() as connection:
            for column_name, ddl in user_migrations.items():
                if column_name not in existing_user_columns:
                    try:
                        connection.execute(text(f"ALTER TABLE users ADD COLUMN {ddl}"))
                    except OperationalError as exc:
                        if "duplicate column name" not in str(exc).lower():
                            raise
            if "username" not in existing_user_columns:
                connection.execute(
                    text(
                        "UPDATE users "
                        "SET username = substr(email, 1, instr(email, '@') - 1) "
                        "WHERE username IS NULL OR trim(username) = ''"
                    )
                )
            connection.execute(
                text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)")
            )

    if not inspector.has_table("gov_contract_opportunities"):
        return False

    existing_columns = {
        column["name"] for column in inspector.get_columns("gov_contract_opportunities")
    }
    requires_contract_rescore = False
    migrations = {
        "funnel_status": "funnel_status VARCHAR DEFAULT 'discovered' NOT NULL",
        "funnel_submission_id": "funnel_submission_id VARCHAR",
        "funnel_delivery_target": "funnel_delivery_target VARCHAR",
        "funnel_delivery_status": "funnel_delivery_status VARCHAR",
        "funnel_record_id": "funnel_record_id VARCHAR",
        "funnel_payload": "funnel_payload JSON",
        "funnel_response": "funnel_response JSON",
        "funneled_at": "funneled_at DATETIME",
        "priority_score": "priority_score INTEGER DEFAULT 0 NOT NULL",
        "score_breakdown": "score_breakdown JSON",
    }

    with engine.begin() as connection:
        for column_name, ddl in migrations.items():
            if column_name not in existing_columns:
                try:
                    connection.execute(
                        text(f"ALTER TABLE gov_contract_opportunities ADD COLUMN {ddl}")
                    )
                    if column_name in {"priority_score", "score_breakdown"}:
                        requires_contract_rescore = True
                except OperationalError as exc:
                    if "duplicate column name" not in str(exc).lower():
                        raise

        indexes = {
            "ix_gov_contract_opportunities_funnel_submission_id": "funnel_submission_id",
            "ix_gov_contract_opportunities_funnel_delivery_status": "funnel_delivery_status",
            "ix_gov_contract_opportunities_funnel_record_id": "funnel_record_id",
            "ix_gov_contract_opportunities_priority_score": "priority_score",
        }
        for index_name, column_name in indexes.items():
            connection.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON gov_contract_opportunities ({column_name})"
                )
            )
    return requires_contract_rescore


def _seed_gov_contract_keyword_rules() -> None:
    from app.models.gov_contract import GovContractKeywordRule
    from app.services.gov_contract_service import build_default_keyword_rules
    from app.utils.helpers import new_uuid

    with SessionLocal() as db:
        for phrase, weight in build_default_keyword_rules():
            db.add(
                GovContractKeywordRule(
                    id=new_uuid(),
                    phrase=phrase,
                    weight=weight,
                )
            )
        db.commit()


def _seed_bootstrap_admin_user() -> None:
    from app.services.auth_service import ensure_bootstrap_admin_user

    with SessionLocal() as db:
        ensure_bootstrap_admin_user(db)


def _backfill_gov_contract_scores() -> None:
    from app.services.gov_contract_service import rescore_stored_opportunities

    with SessionLocal() as db:
        rescore_stored_opportunities(db)
        db.commit()
