from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

InvoiceCompositionMode = Literal["time_entry", "custom"]


class InvoiceLineItemInput(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Optional[float] = Field(default=None, ge=0)
    unit_price: Optional[float] = Field(default=None, ge=0)
    amount: Optional[float] = Field(default=None, ge=0)


class InvoiceLineItemRead(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: float
    subtotal_included: bool = True


class InvoiceRenderRequest(BaseModel):
    company_key: str = Field(min_length=2, max_length=120)
    sender_mailbox: str = Field(min_length=3, max_length=320)
    recipient_email: str = Field(min_length=3, max_length=320)
    cc_email: Optional[str] = Field(default=None, max_length=320)
    bill_to_name: str = Field(min_length=1, max_length=240)
    bill_to_phone: Optional[str] = Field(default=None, max_length=80)
    bill_to_address: str = Field(min_length=1, max_length=1000)
    issue_date: date
    due_date: date
    memo: str = Field(min_length=1, max_length=4000)
    pay_online_label: Optional[str] = Field(default=None, max_length=160)
    pay_online_url: Optional[str] = Field(default=None, max_length=2048)
    invoice_number_override: Optional[str] = Field(default=None, max_length=120)
    composition_mode: InvoiceCompositionMode
    currency: Optional[str] = Field(default=None, min_length=3, max_length=10)
    hourly_rate: Optional[float] = Field(default=None, ge=0)
    week_1_ending: Optional[date] = None
    week_1_hours: Optional[float] = Field(default=None, ge=0)
    week_2_ending: Optional[date] = None
    week_2_hours: Optional[float] = Field(default=None, ge=0)
    custom_line_items: list[InvoiceLineItemInput] = Field(default_factory=list)


class InvoiceCompanyOptionRead(BaseModel):
    key: str
    label: str
    invoice_prefix: str
    default_composition_mode: InvoiceCompositionMode
    default_sender_mailbox: str


class InvoiceSenderMailboxRead(BaseModel):
    email: str
    label: str
    draft_enabled: bool


class InvoiceDefaultsFormRead(BaseModel):
    company_key: str
    company_name: str
    invoice_prefix: str
    default_composition_mode: InvoiceCompositionMode
    sender_mailbox: str
    recipient_email: str
    cc_email: Optional[str] = None
    bill_to_name: str
    bill_to_phone: Optional[str] = None
    bill_to_address: str
    issue_date: date
    due_date: date
    memo: str
    pay_online_label: Optional[str] = None
    pay_online_url: Optional[str] = None
    currency: str
    hourly_rate: float
    week_1_ending: date
    week_1_hours: float
    week_2_ending: date
    week_2_hours: float
    custom_line_items: list[InvoiceLineItemRead]


class InvoiceDefaultsRead(BaseModel):
    selected_company_key: str
    companies: list[InvoiceCompanyOptionRead]
    sender_mailboxes: list[InvoiceSenderMailboxRead]
    draft_creation_enabled: bool
    defaults: InvoiceDefaultsFormRead


class InvoiceDraftRead(BaseModel):
    invoice_id: str
    company_key: str
    company_name: str
    invoice_number: str
    output_filename: str
    sender_mailbox: str
    recipient_email: str
    cc_email: Optional[str] = None
    subtotal: float
    total: float
    amount_due: float
    currency: str
    gmail_draft_id: str
    download_url: str
    created_at: datetime
