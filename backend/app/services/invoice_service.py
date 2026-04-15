from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from email.utils import formataddr
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.invoice import GeneratedInvoice, InvoiceSequence
from app.models.user import User
from app.schemas.invoice import InvoiceRenderRequest
from app.utils.helpers import new_uuid

settings = get_settings()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "invoice_templates"
COMPOSITION_TIME_ENTRY = "time_entry"
COMPOSITION_CUSTOM = "custom"
TAX_LINE_PATTERN = re.compile(r"^\s*tax\b", re.IGNORECASE)
INVOICE_OVERRIDE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MONEY_QUANTUM = Decimal("0.01")


class InvoiceError(RuntimeError):
    pass


class InvoiceValidationError(InvoiceError):
    pass


class InvoiceNotFoundError(LookupError):
    pass


class InvoiceConfigurationError(InvoiceError):
    pass


@dataclass(frozen=True)
class MailboxProfile:
    email: str
    label: str
    refresh_token: str | None


@dataclass(frozen=True)
class InvoiceCompanyProfile:
    key: str
    label: str
    invoice_prefix: str
    template_name: str
    default_sender_mailbox: str
    default_recipient_email: str
    default_cc_email: str | None
    default_bill_to_name: str
    default_bill_to_phone: str | None
    default_bill_to_address_lines: tuple[str, ...]
    default_memo: str
    default_due_days: int
    default_composition_mode: str
    default_hourly_rate: Decimal
    default_currency: str = "USD"
    default_pay_online_label: str | None = None
    default_pay_online_url: str | None = None


@dataclass(frozen=True)
class NormalizedInvoiceLineItem:
    description: str
    quantity: Decimal | None
    unit_price: Decimal | None
    amount: Decimal
    subtotal_included: bool


@dataclass(frozen=True)
class NormalizedInvoicePayload:
    company: InvoiceCompanyProfile
    sender_mailbox: str
    recipient_email: str
    cc_email: str | None
    bill_to_name: str
    bill_to_phone: str | None
    bill_to_address: str
    issue_date: date
    due_date: date
    due_text: str
    memo: str
    pay_online_label: str | None
    pay_online_url: str | None
    invoice_number_override: str | None
    currency: str
    composition_mode: str
    line_items: list[NormalizedInvoiceLineItem]
    subtotal: Decimal
    total: Decimal
    amount_due: Decimal
    hourly_rate: Decimal | None
    week_1_ending: date | None
    week_1_hours: Decimal | None
    week_2_ending: date | None
    week_2_hours: Decimal | None


def _mailbox_profiles() -> dict[str, MailboxProfile]:
    return {
        "benjaminlagrone@gmail.com": MailboxProfile(
            email="benjaminlagrone@gmail.com",
            label="benjaminlagrone@gmail.com",
            refresh_token=_clean(settings.gmail_refresh_tokens.get("benjaminlagrone@gmail.com")),
        ),
        "benjamin@lecrownproperties.com": MailboxProfile(
            email="benjamin@lecrownproperties.com",
            label="benjamin@lecrownproperties.com",
            refresh_token=_clean(
                settings.gmail_refresh_tokens.get("benjamin@lecrownproperties.com")
            ),
        ),
    }


def _company_profiles() -> dict[str, InvoiceCompanyProfile]:
    return {
        "lecrown_development": InvoiceCompanyProfile(
            key="lecrown_development",
            label="LeCrown Development Corp",
            invoice_prefix="LCB",
            template_name="lecrown_development_corp.json",
            default_sender_mailbox="benjaminlagrone@gmail.com",
            default_recipient_email="vendors@revolutiontechnologies.com",
            default_cc_email=None,
            default_bill_to_name="Revolution Technologies",
            default_bill_to_phone="+1 321-409-4949",
            default_bill_to_address_lines=(
                "1000 Revolution Technologies",
                "Melbourne, FL 32901",
                "United States",
            ),
            default_memo="For work performed by Benjamin LaGrone through LeCrown Development Corp.",
            default_due_days=14,
            default_composition_mode=COMPOSITION_TIME_ENTRY,
            default_hourly_rate=Decimal("155.00"),
        ),
        "lecrown_properties": InvoiceCompanyProfile(
            key="lecrown_properties",
            label="LeCrown Properties Corp",
            invoice_prefix="LCP",
            template_name="lecrown_properties_corp.json",
            default_sender_mailbox="benjamin@lecrownproperties.com",
            default_recipient_email="kensington.obh@gmail.com",
            default_cc_email="edm.kpg@gmail.com",
            default_bill_to_name="Kensington Property Group",
            default_bill_to_phone=None,
            default_bill_to_address_lines=(),
            default_memo="For work performed by Benjamin LaGrone through LeCrown Properties Corp.",
            default_due_days=7,
            default_composition_mode=COMPOSITION_CUSTOM,
            default_hourly_rate=Decimal("155.00"),
        ),
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_required(value: Any, label: str) -> str:
    text = _clean(value)
    if text is None:
        raise InvoiceValidationError(f"{label} is required")
    return text


def _require_supported_mailbox(email: str) -> MailboxProfile:
    mailbox = _mailbox_profiles().get(email)
    if mailbox is None:
        raise InvoiceValidationError("Sender mailbox is not allowed")
    return mailbox


def _require_company(company_key: str) -> InvoiceCompanyProfile:
    company = _company_profiles().get(company_key)
    if company is None:
        raise InvoiceValidationError(f"Unknown company key '{company_key}'")
    return company


def _ensure_draft_mailbox_ready(mailbox: MailboxProfile) -> None:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise InvoiceConfigurationError("Google OAuth credentials are not configured for Gmail drafts")
    if not mailbox.refresh_token:
        raise InvoiceConfigurationError(
            f"Gmail refresh token is not configured for mailbox '{mailbox.email}'"
        )


def _is_draft_enabled(mailbox: MailboxProfile) -> bool:
    return bool(
        settings.google_oauth_client_id
        and settings.google_oauth_client_secret
        and mailbox.refresh_token
    )


def list_company_options() -> list[dict[str, Any]]:
    return [
        {
            "key": company.key,
            "label": company.label,
            "invoice_prefix": company.invoice_prefix,
            "default_composition_mode": company.default_composition_mode,
            "default_sender_mailbox": company.default_sender_mailbox,
        }
        for company in _company_profiles().values()
    ]


def list_sender_mailboxes() -> list[dict[str, Any]]:
    return [
        {
            "email": mailbox.email,
            "label": mailbox.label,
            "draft_enabled": _is_draft_enabled(mailbox),
        }
        for mailbox in _mailbox_profiles().values()
    ]


def get_invoice_defaults(company_key: str | None = None) -> dict[str, Any]:
    company = _require_company(company_key or "lecrown_development")
    today = date.today()
    week_2_ending = _most_recent_sunday(today)
    week_1_ending = week_2_ending - timedelta(days=7)
    due_date = today + timedelta(days=company.default_due_days)

    defaults = {
        "company_key": company.key,
        "company_name": company.label,
        "invoice_prefix": company.invoice_prefix,
        "default_composition_mode": company.default_composition_mode,
        "sender_mailbox": company.default_sender_mailbox,
        "recipient_email": company.default_recipient_email,
        "cc_email": company.default_cc_email,
        "bill_to_name": company.default_bill_to_name,
        "bill_to_phone": company.default_bill_to_phone,
        "bill_to_address": "\n".join(company.default_bill_to_address_lines),
        "issue_date": today,
        "due_date": due_date,
        "memo": company.default_memo,
        "pay_online_label": company.default_pay_online_label,
        "pay_online_url": company.default_pay_online_url,
        "currency": company.default_currency,
        "hourly_rate": _decimal_to_float(company.default_hourly_rate),
        "week_1_ending": week_1_ending,
        "week_1_hours": 40.0,
        "week_2_ending": week_2_ending,
        "week_2_hours": 40.0,
        "custom_line_items": [
            {
                "description": "",
                "quantity": None,
                "unit_price": None,
                "amount": 0.0,
                "subtotal_included": True,
            }
        ],
    }
    return {
        "selected_company_key": company.key,
        "companies": list_company_options(),
        "sender_mailboxes": list_sender_mailboxes(),
        "draft_creation_enabled": any(
            mailbox["draft_enabled"] for mailbox in list_sender_mailboxes()
        ),
        "defaults": defaults,
    }


def create_rendered_invoice(
    db: Session,
    *,
    payload: InvoiceRenderRequest,
    created_by: User,
) -> GeneratedInvoice:
    normalized = _normalize_payload(payload)
    return _create_invoice_record(db, normalized=normalized, created_by=created_by, create_draft=False)


def create_invoice_draft(
    db: Session,
    *,
    payload: InvoiceRenderRequest,
    created_by: User,
) -> GeneratedInvoice:
    normalized = _normalize_payload(payload)
    return _create_invoice_record(db, normalized=normalized, created_by=created_by, create_draft=True)


def get_generated_invoice(db: Session, invoice_id: str) -> GeneratedInvoice:
    invoice = db.get(GeneratedInvoice, invoice_id)
    if invoice is None:
        raise InvoiceNotFoundError("Generated invoice was not found")
    return invoice


def get_download_path(invoice: GeneratedInvoice) -> Path:
    output_dir = settings.invoice_output_path.resolve()
    path = Path(invoice.output_path).resolve()
    if not _path_within_directory(path, output_dir):
        raise InvoiceConfigurationError("Stored invoice file is outside the configured output directory")
    if not path.exists():
        raise InvoiceNotFoundError("Generated invoice file is no longer available")
    return path


def serialize_draft_response(invoice: GeneratedInvoice) -> dict[str, Any]:
    return {
        "invoice_id": invoice.id,
        "company_key": invoice.company_key,
        "company_name": invoice.company_name,
        "invoice_number": invoice.invoice_number,
        "output_filename": invoice.output_filename,
        "sender_mailbox": invoice.sender_mailbox,
        "recipient_email": invoice.recipient_email,
        "cc_email": invoice.cc_email,
        "subtotal": _cents_to_float(invoice.subtotal_cents),
        "total": _cents_to_float(invoice.total_cents),
        "amount_due": _cents_to_float(invoice.amount_due_cents),
        "currency": invoice.currency,
        "gmail_draft_id": invoice.gmail_draft_id,
        "created_at": invoice.created_at,
    }


def _normalize_payload(payload: InvoiceRenderRequest) -> NormalizedInvoicePayload:
    company = _require_company(payload.company_key)
    sender_mailbox = _require_supported_mailbox(payload.sender_mailbox).email
    recipient_email = _clean_required(payload.recipient_email, "Recipient email")
    cc_email = _clean(payload.cc_email)
    bill_to_name = _clean_required(payload.bill_to_name, "Bill-to name")
    bill_to_phone = _clean(payload.bill_to_phone)
    bill_to_address = _clean_required(payload.bill_to_address, "Bill-to address")
    memo = _clean_required(payload.memo, "Memo")
    pay_online_label = _clean(payload.pay_online_label)
    pay_online_url = _clean(payload.pay_online_url)
    invoice_number_override = _clean(payload.invoice_number_override)
    currency = _clean(payload.currency or company.default_currency) or company.default_currency
    currency = currency.upper()

    if payload.due_date < payload.issue_date:
        raise InvoiceValidationError("Due date must be on or after the issue date")

    if invoice_number_override and not INVOICE_OVERRIDE_PATTERN.fullmatch(invoice_number_override):
        raise InvoiceValidationError(
            "Invoice number override may only contain letters, numbers, periods, underscores, and hyphens"
        )

    if pay_online_label and not pay_online_url:
        raise InvoiceValidationError("Pay online URL is required when a pay online label is provided")

    if pay_online_url and not re.match(r"^https?://", pay_online_url, re.IGNORECASE):
        raise InvoiceValidationError("Pay online URL must start with http:// or https://")

    if pay_online_url and not pay_online_label:
        pay_online_label = "Pay online"

    if payload.composition_mode == COMPOSITION_TIME_ENTRY:
        line_items, subtotal, total, amount_due, hourly_rate, week_1_hours, week_2_hours = _normalize_time_entry(
            payload
        )
        week_1_ending = payload.week_1_ending
        week_2_ending = payload.week_2_ending
    elif payload.composition_mode == COMPOSITION_CUSTOM:
        line_items, subtotal, total, amount_due = _normalize_custom_items(payload)
        hourly_rate = None
        week_1_ending = None
        week_1_hours = None
        week_2_ending = None
        week_2_hours = None
    else:
        raise InvoiceValidationError("Unsupported invoice composition mode")

    return NormalizedInvoicePayload(
        company=company,
        sender_mailbox=sender_mailbox,
        recipient_email=recipient_email,
        cc_email=cc_email,
        bill_to_name=bill_to_name,
        bill_to_phone=bill_to_phone,
        bill_to_address=bill_to_address,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        due_text=f"Due {_display_date(payload.due_date)}",
        memo=memo,
        pay_online_label=pay_online_label,
        pay_online_url=pay_online_url,
        invoice_number_override=invoice_number_override,
        currency=currency,
        composition_mode=payload.composition_mode,
        line_items=line_items,
        subtotal=subtotal,
        total=total,
        amount_due=amount_due,
        hourly_rate=hourly_rate,
        week_1_ending=week_1_ending,
        week_1_hours=week_1_hours,
        week_2_ending=week_2_ending,
        week_2_hours=week_2_hours,
    )


def _normalize_time_entry(
    payload: InvoiceRenderRequest,
) -> tuple[
    list[NormalizedInvoiceLineItem],
    Decimal,
    Decimal,
    Decimal,
    Decimal,
    Decimal,
    Decimal,
]:
    if payload.hourly_rate is None:
        raise InvoiceValidationError("Hourly rate is required in time-entry mode")
    if payload.week_1_ending is None or payload.week_2_ending is None:
        raise InvoiceValidationError("Both week ending dates are required in time-entry mode")
    if payload.week_1_hours is None or payload.week_2_hours is None:
        raise InvoiceValidationError("Both week hour values are required in time-entry mode")
    if payload.week_2_ending <= payload.week_1_ending:
        raise InvoiceValidationError("Week 2 ending must be after Week 1 ending")

    hourly_rate = _to_money_decimal(payload.hourly_rate, "Hourly rate")
    week_1_hours = _to_money_decimal(payload.week_1_hours, "Week 1 hours")
    week_2_hours = _to_money_decimal(payload.week_2_hours, "Week 2 hours")
    week_1_amount = _money_round(hourly_rate * week_1_hours)
    week_2_amount = _money_round(hourly_rate * week_2_hours)
    total = _money_round(week_1_amount + week_2_amount)
    line_items = [
        NormalizedInvoiceLineItem(
            description=f"Week ending {_short_date(payload.week_1_ending)} (hours)",
            quantity=week_1_hours,
            unit_price=hourly_rate,
            amount=week_1_amount,
            subtotal_included=True,
        ),
        NormalizedInvoiceLineItem(
            description=f"Week ending {_short_date(payload.week_2_ending)} (hours)",
            quantity=week_2_hours,
            unit_price=hourly_rate,
            amount=week_2_amount,
            subtotal_included=True,
        ),
    ]
    return line_items, total, total, total, hourly_rate, week_1_hours, week_2_hours


def _normalize_custom_items(
    payload: InvoiceRenderRequest,
) -> tuple[list[NormalizedInvoiceLineItem], Decimal, Decimal, Decimal]:
    if not payload.custom_line_items:
        raise InvoiceValidationError("At least one custom line item is required in custom mode")

    items: list[NormalizedInvoiceLineItem] = []
    subtotal = Decimal("0.00")
    total = Decimal("0.00")

    for index, item in enumerate(payload.custom_line_items, start=1):
        description = _clean(item.description)
        if description is None:
            raise InvoiceValidationError(f"Custom line item {index} must include a description")

        quantity = _to_money_decimal(item.quantity, None) if item.quantity is not None else None
        unit_price = (
            _to_money_decimal(item.unit_price, None) if item.unit_price is not None else None
        )
        explicit_amount = (
            _to_money_decimal(item.amount, None) if item.amount is not None else None
        )

        if quantity is not None or unit_price is not None:
            if quantity is None or unit_price is None:
                raise InvoiceValidationError(
                    f"Custom line item {index} must include both quantity and unit price when either is provided"
                )
            computed_amount = _money_round(quantity * unit_price)
            if explicit_amount is not None and computed_amount != explicit_amount:
                raise InvoiceValidationError(
                    f"Custom line item {index} amount must equal quantity multiplied by unit price"
                )
            amount = computed_amount
        elif explicit_amount is not None:
            amount = explicit_amount
        else:
            raise InvoiceValidationError(
                f"Custom line item {index} must include an amount or a quantity and unit price"
            )

        subtotal_included = TAX_LINE_PATTERN.search(description) is None
        items.append(
            NormalizedInvoiceLineItem(
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                amount=amount,
                subtotal_included=subtotal_included,
            )
        )
        total = _money_round(total + amount)
        if subtotal_included:
            subtotal = _money_round(subtotal + amount)

    return items, subtotal, total, total


def _create_invoice_record(
    db: Session,
    *,
    normalized: NormalizedInvoicePayload,
    created_by: User,
    create_draft: bool,
) -> GeneratedInvoice:
    mailbox = _require_supported_mailbox(normalized.sender_mailbox)
    if create_draft:
        _ensure_draft_mailbox_ready(mailbox)

    invoice_number = _reserve_invoice_number(
        db,
        company=normalized.company,
        issue_year=normalized.issue_date.year,
        invoice_number_override=normalized.invoice_number_override,
    )
    output_filename = f"Invoice-{invoice_number}.pdf"
    pdf_payload = _build_pdf_payload(normalized, invoice_number)
    pdf_bytes = _build_invoice_pdf_bytes(pdf_payload)
    output_path = _output_path_for_invoice(normalized.company.key, normalized.issue_date.year, output_filename)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)

    try:
        invoice = GeneratedInvoice(
            id=new_uuid(),
            created_by_user_id=created_by.id,
            company_key=normalized.company.key,
            company_name=normalized.company.label,
            invoice_number=invoice_number,
            invoice_number_override=normalized.invoice_number_override,
            sender_mailbox=normalized.sender_mailbox,
            recipient_email=normalized.recipient_email,
            cc_email=normalized.cc_email,
            bill_to_name=normalized.bill_to_name,
            bill_to_phone=normalized.bill_to_phone,
            bill_to_address=normalized.bill_to_address,
            issue_date=normalized.issue_date,
            due_date=normalized.due_date,
            due_text=normalized.due_text,
            memo=normalized.memo,
            pay_online_label=normalized.pay_online_label,
            pay_online_url=normalized.pay_online_url,
            currency=normalized.currency,
            composition_mode=normalized.composition_mode,
            subtotal_cents=_money_to_cents(normalized.subtotal),
            total_cents=_money_to_cents(normalized.total),
            amount_due_cents=_money_to_cents(normalized.amount_due),
            line_items_json=_serialize_line_items(normalized.line_items),
            request_payload_json=_serialize_request_payload(normalized, invoice_number),
            output_filename=output_filename,
            output_path=str(output_path),
            status="rendered",
        )
        db.add(invoice)
        db.flush()

        if create_draft:
            draft_metadata = _create_gmail_draft(
                mailbox=mailbox,
                normalized=normalized,
                invoice_number=invoice_number,
                output_filename=output_filename,
                pdf_bytes=pdf_bytes,
            )
            invoice.gmail_draft_id = draft_metadata["draft_id"]
            invoice.gmail_message_id = draft_metadata.get("message_id")
            invoice.status = "draft_created"

        db.commit()
        db.refresh(invoice)
        return invoice
    except Exception:
        db.rollback()
        if output_path.exists():
            output_path.unlink()
        raise


def _reserve_invoice_number(
    db: Session,
    *,
    company: InvoiceCompanyProfile,
    issue_year: int,
    invoice_number_override: str | None,
) -> str:
    if invoice_number_override:
        existing = db.scalars(
            select(GeneratedInvoice).where(GeneratedInvoice.invoice_number == invoice_number_override)
        ).first()
        if existing is not None:
            raise InvoiceValidationError(
                f"Invoice number '{invoice_number_override}' has already been used"
            )
        return invoice_number_override

    sequence = db.scalars(
        select(InvoiceSequence).where(
            InvoiceSequence.company_key == company.key,
            InvoiceSequence.invoice_year == issue_year,
        )
    ).first()
    if sequence is None:
        sequence = InvoiceSequence(
            id=new_uuid(),
            company_key=company.key,
            invoice_year=issue_year,
            last_sequence=0,
        )
        db.add(sequence)
        db.flush()

    while True:
        sequence.last_sequence += 1
        candidate = f"{company.invoice_prefix}-{issue_year}-{sequence.last_sequence:04d}"
        exists = db.scalars(
            select(GeneratedInvoice).where(GeneratedInvoice.invoice_number == candidate)
        ).first()
        if exists is None:
            return candidate


def _build_pdf_payload(normalized: NormalizedInvoicePayload, invoice_number: str) -> dict[str, Any]:
    template = _load_template(normalized.company.template_name)
    return _merge_dicts(
        template,
        {
            "company_name": normalized.company.label,
            "invoice_number": invoice_number,
            "issue_date": _short_date(normalized.issue_date),
            "due_text": normalized.due_text,
            "to": {
                "name": normalized.bill_to_name,
                "address_lines": _split_lines(normalized.bill_to_address),
                "phone": normalized.bill_to_phone,
                "email": normalized.recipient_email,
            },
            "memo": normalized.memo,
            "pay_online_label": normalized.pay_online_label or "",
            "pay_online_url": normalized.pay_online_url or "",
            "currency": normalized.currency,
            "line_items": [
                {
                    "description": item.description,
                    "qty": _decimal_to_float(item.quantity) if item.quantity is not None else None,
                    "unit_price": (
                        _decimal_to_float(item.unit_price) if item.unit_price is not None else None
                    ),
                    "amount": _decimal_to_float(item.amount),
                }
                for item in normalized.line_items
            ],
            "subtotal": _decimal_to_float(normalized.subtotal),
            "total": _decimal_to_float(normalized.total),
            "amount_due": _decimal_to_float(normalized.amount_due),
        },
    )


def _serialize_line_items(items: list[NormalizedInvoiceLineItem]) -> list[dict[str, Any]]:
    return [
        {
            "description": item.description,
            "quantity": _decimal_to_float(item.quantity) if item.quantity is not None else None,
            "unit_price": _decimal_to_float(item.unit_price) if item.unit_price is not None else None,
            "amount": _decimal_to_float(item.amount),
            "subtotal_included": item.subtotal_included,
        }
        for item in items
    ]


def _serialize_request_payload(
    normalized: NormalizedInvoicePayload,
    invoice_number: str,
) -> dict[str, Any]:
    return {
        "invoice_number": invoice_number,
        "company_key": normalized.company.key,
        "company_name": normalized.company.label,
        "sender_mailbox": normalized.sender_mailbox,
        "recipient_email": normalized.recipient_email,
        "cc_email": normalized.cc_email,
        "bill_to_name": normalized.bill_to_name,
        "bill_to_phone": normalized.bill_to_phone,
        "bill_to_address": normalized.bill_to_address,
        "issue_date": normalized.issue_date.isoformat(),
        "due_date": normalized.due_date.isoformat(),
        "due_text": normalized.due_text,
        "memo": normalized.memo,
        "pay_online_label": normalized.pay_online_label,
        "pay_online_url": normalized.pay_online_url,
        "currency": normalized.currency,
        "composition_mode": normalized.composition_mode,
        "hourly_rate": _decimal_to_float(normalized.hourly_rate)
        if normalized.hourly_rate is not None
        else None,
        "week_1_ending": normalized.week_1_ending.isoformat()
        if normalized.week_1_ending is not None
        else None,
        "week_1_hours": _decimal_to_float(normalized.week_1_hours)
        if normalized.week_1_hours is not None
        else None,
        "week_2_ending": normalized.week_2_ending.isoformat()
        if normalized.week_2_ending is not None
        else None,
        "week_2_hours": _decimal_to_float(normalized.week_2_hours)
        if normalized.week_2_hours is not None
        else None,
        "line_items": _serialize_line_items(normalized.line_items),
        "subtotal": _decimal_to_float(normalized.subtotal),
        "total": _decimal_to_float(normalized.total),
        "amount_due": _decimal_to_float(normalized.amount_due),
    }


def _create_gmail_draft(
    *,
    mailbox: MailboxProfile,
    normalized: NormalizedInvoicePayload,
    invoice_number: str,
    output_filename: str,
    pdf_bytes: bytes,
) -> dict[str, Any]:
    access_token = _fetch_gmail_access_token(mailbox)
    subject = f"New invoice from {normalized.company.label} #{invoice_number}"
    plain_body = _build_plain_email_body(normalized, invoice_number)
    html_body = _build_html_email_body(normalized, invoice_number)

    message = EmailMessage()
    message["To"] = normalized.recipient_email
    if normalized.cc_email:
        message["Cc"] = normalized.cc_email
    message["From"] = formataddr((normalized.company.label, mailbox.email))
    message["Subject"] = subject
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=output_filename,
    )

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    try:
        response = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"message": {"raw": raw_message}},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise InvoiceError("Failed to create the Gmail draft") from exc

    if not response.ok:
        raise InvoiceError(
            f"Gmail draft creation failed with {response.status_code}: {response.text[:200]}"
        )

    payload = response.json()
    message_payload = payload.get("message") or {}
    draft_id = _clean(payload.get("id"))
    if draft_id is None:
        raise InvoiceError("Gmail draft creation did not return a draft id")
    return {
        "draft_id": draft_id,
        "message_id": _clean(message_payload.get("id")),
    }


def _fetch_gmail_access_token(mailbox: MailboxProfile) -> str:
    if mailbox.refresh_token is None:
        raise InvoiceConfigurationError(
            f"Gmail refresh token is not configured for mailbox '{mailbox.email}'"
        )
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": mailbox.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise InvoiceError("Failed to refresh the Gmail access token") from exc

    if not response.ok:
        raise InvoiceConfigurationError(
            f"Google OAuth token refresh failed for '{mailbox.email}' with {response.status_code}: {response.text[:200]}"
        )

    payload = response.json()
    access_token = _clean(payload.get("access_token"))
    if access_token is None:
        raise InvoiceConfigurationError(
            f"Google OAuth token refresh for '{mailbox.email}' did not return an access token"
        )
    return access_token


def _build_plain_email_body(normalized: NormalizedInvoicePayload, invoice_number: str) -> str:
    lines = [
        "Hello,",
        "",
        f"Attached is invoice {invoice_number} from {normalized.company.label}.",
        "",
        f"Description: {normalized.memo}",
        f"Invoice total: {_format_money(normalized.total, normalized.currency)}",
        f"Due date: {_display_date(normalized.due_date)}",
    ]
    if normalized.pay_online_url:
        lines.append(f"{normalized.pay_online_label}: {normalized.pay_online_url}")
    lines.extend(["", "Thank you,", "Benjamin LaGrone", normalized.company.label])
    return "\n".join(lines)


def _build_html_email_body(normalized: NormalizedInvoicePayload, invoice_number: str) -> str:
    pay_online_line = ""
    if normalized.pay_online_url:
        pay_online_line = (
            f'<br /><strong>{_escape_html(normalized.pay_online_label)}:</strong> '
            f'<a href="{_escape_html(normalized.pay_online_url)}">{_escape_html(normalized.pay_online_url)}</a>'
        )
    return "".join(
        [
            "<p>Hello,</p>",
            (
                "<p>Attached is invoice "
                f"<strong>{_escape_html(invoice_number)}</strong> from "
                f"{_escape_html(normalized.company.label)}.</p>"
            ),
            f"<p><strong>Description:</strong> {_escape_html(normalized.memo)}</p>",
            (
                "<p><strong>Invoice total:</strong> "
                f"{_escape_html(_format_money(normalized.total, normalized.currency))}<br />"
                f"<strong>Due date:</strong> {_escape_html(_display_date(normalized.due_date))}"
                f"{pay_online_line}</p>"
            ),
            (
                "<p>Thank you,<br />Benjamin LaGrone<br />"
                f"{_escape_html(normalized.company.label)}</p>"
            ),
        ]
    )


def _output_path_for_invoice(company_key: str, issue_year: int, output_filename: str) -> Path:
    return settings.invoice_output_path / company_key / str(issue_year) / output_filename


def _path_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
        return True
    except ValueError:
        return False


def _most_recent_sunday(current_date: date) -> date:
    return current_date - timedelta(days=(current_date.weekday() + 1) % 7)


def _to_money_decimal(value: Any, label: str | None) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001
        if label:
            raise InvoiceValidationError(f"{label} must be a number") from exc
        raise InvoiceValidationError("Amount must be a number") from exc
    if decimal_value < 0:
        if label:
            raise InvoiceValidationError(f"{label} must be non-negative")
        raise InvoiceValidationError("Amount must be non-negative")
    return _money_round(decimal_value)


def _money_round(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _money_to_cents(value: Decimal) -> int:
    return int((_money_round(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _cents_to_float(value: int) -> float:
    return float(Decimal(value) / Decimal("100"))


def _decimal_to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _display_date(value: date) -> str:
    return f"{value.strftime('%B')} {value.day}, {value.year}"


def _short_date(value: date) -> str:
    return f"{value.month}/{value.day}/{value.year}"


def _format_money(amount: Decimal, currency: str) -> str:
    rounded = _money_round(amount)
    symbol = "$" if currency.upper() == "USD" else ""
    return f"{symbol}{rounded:,.2f} {currency.upper()}".strip()


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _escape_html(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


@lru_cache
def _load_template(template_name: str) -> dict[str, Any]:
    template_path = TEMPLATE_DIR / template_name
    return json.loads(template_path.read_text())


def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged


def _money(value: object, currency: str) -> str:
    amount = Decimal(str(value or "0")).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    symbol = "$" if currency.upper() == "USD" else ""
    return f"{symbol}{amount:,.2f} {currency.upper()}".strip()


def _lines_for_party(party: dict[str, Any]) -> list[str]:
    lines = []
    name = str(party.get("name", "")).strip()
    if name:
        lines.append(name)
    for line in party.get("address_lines", []) or []:
        text = str(line).strip()
        if text:
            lines.append(text)
    for field in ("phone", "email"):
        text = str(party.get(field, "")).strip()
        if text:
            lines.append(text)
    return lines


def _build_styles(accent_hex: str) -> dict[str, Any]:
    accent = colors.HexColor(accent_hex)
    ink = colors.HexColor("#20303f")
    muted = colors.HexColor("#66727f")
    soft = colors.HexColor("#f7fafc")
    accent_soft = colors.HexColor("#eef4f8")
    line = colors.HexColor("#d8e0e8")

    base_styles = getSampleStyleSheet()
    return {
        "accent": accent,
        "ink": ink,
        "muted": muted,
        "soft": soft,
        "accent_soft": accent_soft,
        "line": line,
        "body": ParagraphStyle(
            "InvoiceBody",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=ink,
            spaceAfter=0,
        ),
        "small_label": ParagraphStyle(
            "InvoiceSmallLabel",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=muted,
            spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "InvoiceTitle",
            parent=base_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=accent,
            spaceAfter=0,
        ),
        "invoice_number": ParagraphStyle(
            "InvoiceNumber",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=muted,
            spaceAfter=0,
        ),
        "section_head": ParagraphStyle(
            "InvoiceSectionHead",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=ink,
            spaceAfter=0,
        ),
        "company_banner": ParagraphStyle(
            "InvoiceCompanyBanner",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=1,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "amount_label": ParagraphStyle(
            "InvoiceAmountLabel",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_RIGHT,
            textColor=muted,
            spaceAfter=0,
        ),
        "amount_value": ParagraphStyle(
            "InvoiceAmountValue",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_RIGHT,
            textColor=accent,
            spaceAfter=0,
        ),
        "amount_note": ParagraphStyle(
            "InvoiceAmountNote",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            alignment=TA_RIGHT,
            textColor=ink,
            spaceAfter=0,
        ),
        "footer": ParagraphStyle(
            "InvoiceFooter",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            textColor=muted,
            spaceAfter=0,
        ),
        "right": ParagraphStyle(
            "InvoiceRight",
            parent=base_styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=12,
            alignment=TA_RIGHT,
            textColor=ink,
            spaceAfter=0,
        ),
        "right_bold": ParagraphStyle(
            "InvoiceRightBold",
            parent=base_styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            alignment=TA_RIGHT,
            textColor=ink,
            spaceAfter=0,
        ),
    }


def _party_block(title: str, lines: list[str], styles: dict[str, Any], background_color: Any) -> Table:
    rows = [[Paragraph(title, styles["small_label"])]]
    for index, line in enumerate(lines):
        style = styles["section_head"] if index == 0 else styles["body"]
        rows.append([Paragraph(line, style)])
    table = Table(rows, colWidths=[2.75 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background_color),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _meta_table(data: dict[str, Any], styles: dict[str, Any]) -> Table:
    rows = [
        [Paragraph("Invoice number", styles["small_label"]), Paragraph(data["invoice_number"], styles["right"])],
        [Paragraph("Issue date", styles["small_label"]), Paragraph(data["issue_date"], styles["right"])],
        [Paragraph("Due", styles["small_label"]), Paragraph(data["due_text"], styles["right"])],
    ]
    table = Table(rows, colWidths=[1.7 * inch, 4.9 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, styles["line"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, styles["line"]),
                ("BACKGROUND", (0, 0), (0, -1), styles["soft"]),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _line_items_table(data: dict[str, Any], styles: dict[str, Any]) -> Table:
    items = data.get("line_items", [])
    has_qty = any(item.get("qty") is not None for item in items)
    has_unit_price = any(item.get("unit_price") is not None for item in items)

    if has_qty or has_unit_price:
        rows = [
            [
                Paragraph("Description", styles["small_label"]),
                Paragraph("Qty", styles["small_label"]),
                Paragraph("Unit price", styles["small_label"]),
                Paragraph("Amount", styles["small_label"]),
            ]
        ]
        for item in items:
            rows.append(
                [
                    Paragraph(str(item.get("description", "")), styles["body"]),
                    Paragraph(
                        "" if item.get("qty") is None else str(item.get("qty")),
                        styles["right"],
                    ),
                    Paragraph(
                        ""
                        if item.get("unit_price") is None
                        else _money(item.get("unit_price"), data["currency"]),
                        styles["right"],
                    ),
                    Paragraph(_money(item.get("amount", 0), data["currency"]), styles["right"]),
                ]
            )
        widths = [3.4 * inch, 0.7 * inch, 1.0 * inch, 1.1 * inch]
    else:
        rows = [
            [
                Paragraph("Description", styles["small_label"]),
                Paragraph("Amount", styles["small_label"]),
            ]
        ]
        for item in items:
            rows.append(
                [
                    Paragraph(str(item.get("description", "")), styles["body"]),
                    Paragraph(_money(item.get("amount", 0), data["currency"]), styles["right"]),
                ]
            )
        widths = [4.8 * inch, 1.4 * inch]

    table = Table(rows, colWidths=widths)
    table_style = [
        ("BOX", (0, 0), (-1, -1), 1, styles["line"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, styles["line"]),
        ("BACKGROUND", (0, 0), (-1, 0), styles["accent"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for row_index in range(1, len(rows)):
        if row_index % 2 == 0:
            table_style.append(
                ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#fbfdff"))
            )
    table.setStyle(TableStyle(table_style))
    return table


def _totals_table(data: dict[str, Any], styles: dict[str, Any]) -> Table:
    subtotal = data.get("subtotal", data.get("amount_due", 0))
    total = data.get("total", data.get("amount_due", subtotal))
    amount_due = data.get("amount_due", total)
    rows = [
        [Paragraph("Subtotal", styles["right"]), Paragraph(_money(subtotal, data["currency"]), styles["right"])],
        [Paragraph("Total", styles["right_bold"]), Paragraph(_money(total, data["currency"]), styles["right_bold"])],
        [
            Paragraph(
                "Amount due",
                ParagraphStyle("DueLabel", parent=styles["right_bold"], textColor=colors.white),
            ),
            Paragraph(
                _money(amount_due, data["currency"]),
                ParagraphStyle("DueValue", parent=styles["right_bold"], textColor=colors.white),
            ),
        ],
    ]
    table = Table(rows, colWidths=[4.8 * inch, 1.4 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 2), (-1, 2), styles["accent"]),
            ]
        )
    )
    return table


def _memo_table(data: dict[str, Any], styles: dict[str, Any]) -> Table:
    rows = [
        [Paragraph(str(data.get("memo_title", "Memo")), styles["small_label"])],
        [Paragraph(str(data.get("memo", "")).replace("\n", "<br/>"), styles["body"])],
    ]
    table = Table(rows, colWidths=[6.2 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1, styles["line"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _build_invoice_pdf_bytes(data: dict[str, Any]) -> bytes:
    styles = _build_styles(data.get("accent_color", "#1f4b6e"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        topMargin=0.45 * inch,
        bottomMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
    )

    amount_due = _money(data.get("amount_due", data.get("total", 0)), data["currency"])
    from_lines = _lines_for_party(data.get("from", {}))
    to_lines = _lines_for_party(data.get("to", {}))

    story = []
    banner = Table(
        [[Paragraph(data.get("company_name", ""), styles["company_banner"])]],
        colWidths=[7.1 * inch],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), styles["accent"]),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
                ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(banner)
    story.append(Spacer(1, 0.22 * inch))

    header_left = [
        Paragraph(str(data.get("invoice_title", "INVOICE")), styles["title"]),
        Spacer(1, 0.05 * inch),
        Paragraph(f'Invoice number: {data.get("invoice_number", "")}', styles["invoice_number"]),
        Spacer(1, 0.05 * inch),
        Paragraph(str(data.get("company_name", "")), styles["section_head"]),
    ]
    for line in from_lines[1:]:
        header_left.append(Paragraph(line, styles["body"]))

    amount_card = [
        Paragraph("Amount due", styles["amount_label"]),
        Paragraph(amount_due, styles["amount_value"]),
        Paragraph(str(data.get("due_text", "")), styles["amount_note"]),
    ]
    pay_online_label = str(data.get("pay_online_label", "")).strip()
    pay_online_url = str(data.get("pay_online_url", "")).strip()
    if pay_online_url:
        label = pay_online_label or "Pay online"
        amount_card.append(
            Paragraph(
                f'<link href="{pay_online_url}">{label}</link>',
                ParagraphStyle(
                    "PayOnline",
                    parent=styles["amount_note"],
                    textColor=styles["accent"],
                    fontName="Helvetica-Bold",
                ),
            )
        )

    header = Table([[header_left, amount_card]], colWidths=[4.7 * inch, 2.4 * inch])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("BACKGROUND", (1, 0), (1, 0), styles["accent_soft"]),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 18),
                ("LEFTPADDING", (1, 0), (1, 0), 16),
                ("RIGHTPADDING", (1, 0), (1, 0), 16),
                ("TOPPADDING", (1, 0), (1, 0), 18),
                ("BOTTOMPADDING", (1, 0), (1, 0), 18),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 0.18 * inch))

    parties = Table(
        [[
            _party_block("From", from_lines, styles, styles["soft"]),
            _party_block("Bill to", to_lines, styles, styles["soft"]),
        ]],
        colWidths=[3.45 * inch, 3.45 * inch],
    )
    parties.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(parties)
    story.append(Spacer(1, 0.18 * inch))

    story.append(_meta_table(data, styles))
    story.append(Spacer(1, 0.18 * inch))
    story.append(_memo_table(data, styles))
    story.append(Spacer(1, 0.18 * inch))
    story.append(_line_items_table(data, styles))
    story.append(Spacer(1, 0.12 * inch))
    story.append(_totals_table(data, styles))

    footer_note = str(data.get("footer_note", "")).strip()
    if footer_note:
        story.append(Spacer(1, 0.18 * inch))
        story.append(Paragraph(footer_note, styles["footer"]))

    doc.build(story)
    return buffer.getvalue()
