from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class IntakeLeadSubmission(Base):
    __tablename__ = "intake_lead_submissions"

    id = Column(String, primary_key=True)
    source_site = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)
    form_provider = Column(String, nullable=True)
    form_id = Column(String, nullable=True)
    form_name = Column(String, nullable=True)
    external_entry_id = Column(String, nullable=True)
    page_url = Column(String, nullable=True)
    campaign = Column(String, nullable=True)
    business_context = Column(String, nullable=True, index=True)
    product_context = Column(String, nullable=True)
    contact_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    lead_source = Column(String, nullable=True)
    message = Column(Text, nullable=True)

    status = Column(String, nullable=False, default="received")
    delivery_target = Column(String, nullable=False, default="espocrm")
    delivery_status = Column(String, nullable=False, default="pending")
    delivery_record_id = Column(String, nullable=True)

    raw_payload = Column(JSON, nullable=False, default=dict)
    normalized_payload = Column(JSON, nullable=False, default=dict)
    delivery_payload = Column(JSON, nullable=True)
    delivery_response = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
