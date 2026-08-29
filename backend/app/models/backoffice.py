from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class Brokerage(Base):
    __tablename__ = "brokerages"

    id = Column(String, primary_key=True)
    legal_name = Column(String, nullable=False)
    license_number = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    designated_broker_user_id = Column(String, nullable=True, index=True)
    policy_version = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Office(Base):
    __tablename__ = "brokerage_offices"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    jurisdiction = Column(String, nullable=False, default="TX")
    status = Column(String, nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Team(Base):
    __tablename__ = "brokerage_teams"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    office_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="active", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentProfile(Base):
    __tablename__ = "agent_profiles"
    __table_args__ = (UniqueConstraint("brokerage_id", "user_id", name="uq_agent_brokerage_user"),)

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    office_id = Column(String, nullable=True, index=True)
    team_id = Column(String, nullable=True, index=True)
    license_number = Column(String, nullable=True, index=True)
    sponsorship_status = Column(String, nullable=False, default="pending", index=True)
    authority_status = Column(String, nullable=False, default="inactive", index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RoleAssignment(Base):
    __tablename__ = "brokerage_role_assignments"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False, index=True)
    scope_type = Column(String, nullable=False, default="brokerage")
    scope_id = Column(String, nullable=True, index=True)
    granted_by_user_id = Column(String, nullable=False, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupervisorDelegation(Base):
    __tablename__ = "supervisor_delegations"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    supervisor_user_id = Column(String, nullable=False, index=True)
    agent_user_id = Column(String, nullable=True, index=True)
    team_id = Column(String, nullable=True, index=True)
    evidence_document_id = Column(String, nullable=True, index=True)
    starts_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=True, index=True)
    actor_user_id = Column(String, nullable=True, index=True)
    actor_type = Column(String, nullable=False, default="user")
    action = Column(String, nullable=False, index=True)
    resource_type = Column(String, nullable=False, index=True)
    resource_id = Column(String, nullable=False, index=True)
    previous_state = Column(String, nullable=True)
    next_state = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    request_id = Column(String, nullable=True, index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class Representation(Base):
    __tablename__ = "representations"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    client_name = Column(String, nullable=False)
    client_crm_reference = Column(String, nullable=True, index=True)
    representation_type = Column(String, nullable=False, index=True)
    responsible_agent_user_id = Column(String, nullable=False, index=True)
    supervising_user_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="draft", index=True)
    effective_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Transaction(Base):
    __tablename__ = "real_estate_transactions"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    representation_id = Column(String, nullable=False, index=True)
    property_reference = Column(String, nullable=True, index=True)
    transaction_type = Column(String, nullable=False, index=True)
    responsible_agent_user_id = Column(String, nullable=False, index=True)
    supervising_user_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="draft", index=True)
    confidentiality = Column(String, nullable=False, default="brokerage_confidential")
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    transaction_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    classification = Column(String, nullable=False, default="brokerage_confidential", index=True)
    retention_policy = Column(String, nullable=False, default="pending_review")
    legal_hold = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_document_version"),)

    id = Column(String, primary_key=True)
    document_id = Column(String, nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    sha256 = Column(String, nullable=False, index=True)
    storage_key = Column(String, nullable=False)
    media_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    scan_status = Column(String, nullable=False, default="pending", index=True)
    render_status = Column(String, nullable=False, default="pending", index=True)
    uploaded_by_user_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
