from sqlalchemy import Boolean, Column, Date, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


def default_matched_keywords() -> list[str]:
    return []


def default_request_payload() -> dict:
    return {}


def default_raw_payload() -> dict:
    return {}


def default_score_breakdown() -> dict:
    return {}


class GovContractOpportunity(Base):
    __tablename__ = "gov_contract_opportunities"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False, index=True)
    source_key = Column(String, nullable=False, unique=True, index=True)
    source_url = Column(String, nullable=False)
    title = Column(String, nullable=False, index=True)
    solicitation_id = Column(String, nullable=False, index=True)
    agency_name = Column(String, nullable=True, index=True)
    agency_number = Column(String, nullable=True, index=True)
    status_code = Column(String, nullable=True)
    status_name = Column(String, nullable=True, index=True)
    due_date = Column(Date, nullable=True, index=True)
    due_time = Column(String, nullable=True)
    posting_date = Column(Date, nullable=True, index=True)
    source_created_at = Column(DateTime(timezone=False), nullable=True)
    source_last_modified_at = Column(DateTime(timezone=False), nullable=True)
    nigp_codes = Column(Text, nullable=True)
    score = Column(Integer, nullable=False, default=0, index=True)
    priority_score = Column(Integer, nullable=False, default=0, index=True)
    fit_bucket = Column(String, nullable=False, default="none", index=True)
    is_match = Column(Boolean, nullable=False, default=False, index=True)
    is_open = Column(Boolean, nullable=False, default=False, index=True)
    matched_keywords = Column(JSON, nullable=False, default=default_matched_keywords)
    score_breakdown = Column(JSON, nullable=False, default=default_score_breakdown)
    raw_payload = Column(JSON, nullable=False, default=default_raw_payload)
    funnel_status = Column(String, nullable=False, default="discovered", index=True)
    funnel_submission_id = Column(String, nullable=True, index=True)
    funnel_delivery_target = Column(String, nullable=True)
    funnel_delivery_status = Column(String, nullable=True, index=True)
    funnel_record_id = Column(String, nullable=True, index=True)
    funnel_payload = Column(JSON, nullable=True)
    funnel_response = Column(JSON, nullable=True)
    funneled_at = Column(DateTime(timezone=True), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GovContractKeywordRule(Base):
    __tablename__ = "gov_contract_keyword_rules"

    id = Column(String, primary_key=True)
    phrase = Column(String, nullable=False, unique=True, index=True)
    weight = Column(Integer, nullable=False, default=3, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GovContractAgencyPreference(Base):
    __tablename__ = "gov_contract_agency_preferences"

    id = Column(String, primary_key=True)
    agency_name = Column(String, nullable=False, unique=True, index=True)
    weight = Column(Integer, nullable=False, default=5, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class GovContractImportRun(Base):
    __tablename__ = "gov_contract_import_runs"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="running", index=True)
    window_start = Column(Date, nullable=False, index=True)
    window_end = Column(Date, nullable=False, index=True)
    source_total_records = Column(Integer, nullable=False, default=0)
    total_records = Column(Integer, nullable=False, default=0)
    matched_records = Column(Integer, nullable=False, default=0)
    open_records = Column(Integer, nullable=False, default=0)
    csv_bytes = Column(Integer, nullable=False, default=0)
    request_payload = Column(JSON, nullable=False, default=default_request_payload)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
