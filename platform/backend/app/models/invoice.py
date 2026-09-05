from sqlalchemy import Column, Date, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.core.database import Base


class InvoiceSequence(Base):
    __tablename__ = "invoice_sequences"
    __table_args__ = (UniqueConstraint("company_key", "invoice_year", name="uq_invoice_sequences_company_year"),)

    id = Column(String, primary_key=True)
    company_key = Column(String, nullable=False, index=True)
    invoice_year = Column(Integer, nullable=False, index=True)
    last_sequence = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GeneratedInvoice(Base):
    __tablename__ = "generated_invoices"

    id = Column(String, primary_key=True)
    created_by_user_id = Column(String, nullable=True, index=True)
    company_key = Column(String, nullable=False, index=True)
    company_name = Column(String, nullable=False)
    invoice_number = Column(String, nullable=False, unique=True, index=True)
    invoice_number_override = Column(String, nullable=True)
    sender_mailbox = Column(String, nullable=False, index=True)
    recipient_email = Column(String, nullable=False)
    cc_email = Column(String, nullable=True)
    bill_to_name = Column(String, nullable=False)
    bill_to_phone = Column(String, nullable=True)
    bill_to_address = Column(Text, nullable=False)
    issue_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=False, index=True)
    due_text = Column(String, nullable=False)
    memo = Column(Text, nullable=False)
    pay_online_label = Column(String, nullable=True)
    pay_online_url = Column(String, nullable=True)
    currency = Column(String, nullable=False, default="USD")
    composition_mode = Column(String, nullable=False, index=True)
    subtotal_cents = Column(Integer, nullable=False)
    total_cents = Column(Integer, nullable=False)
    amount_due_cents = Column(Integer, nullable=False)
    line_items_json = Column(JSON, nullable=False, default=list)
    request_payload_json = Column(JSON, nullable=False, default=dict)
    output_filename = Column(String, nullable=False)
    output_path = Column(String, nullable=False)
    gmail_draft_id = Column(String, nullable=True, index=True)
    gmail_message_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="rendered", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
