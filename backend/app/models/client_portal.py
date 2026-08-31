from sqlalchemy import Column, DateTime, String, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class ClientPortalGrant(Base):
    __tablename__ = "client_portal_grants"
    __table_args__ = (
        UniqueConstraint(
            "keycloak_issuer",
            "email",
            "representation_id",
            name="uq_client_portal_grant_email_representation",
        ),
        UniqueConstraint(
            "keycloak_issuer",
            "keycloak_subject",
            "representation_id",
            name="uq_client_portal_grant_subject_representation",
        ),
    )

    id = Column(String, primary_key=True)
    brokerage_id = Column(String, nullable=False, index=True)
    representation_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    keycloak_issuer = Column(String, nullable=False)
    keycloak_subject = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    created_by_user_id = Column(String, nullable=False, index=True)
    revoked_by_user_id = Column(String, nullable=True, index=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_authenticated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
