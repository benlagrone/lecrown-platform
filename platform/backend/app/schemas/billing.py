from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BillingAppCreate(BaseModel):
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    base_url: Optional[str] = None
    status: str = Field(default="active", min_length=1, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BillingAppRead(BaseModel):
    id: str
    key: str
    name: str
    base_url: Optional[str] = None
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    billing_email: Optional[str] = Field(default=None, max_length=320)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountRead(BaseModel):
    id: str
    name: str
    billing_email: Optional[str] = None
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AccountMembershipCreate(BaseModel):
    external_user_id: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    role: str = Field(default="member", min_length=1, max_length=60)
    status: str = Field(default="active", min_length=1, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AccountMembershipRead(BaseModel):
    id: str
    account_id: str
    app_key: str
    external_user_id: str
    email: Optional[str] = None
    role: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EntitlementCreate(BaseModel):
    app_key: str = Field(min_length=2, max_length=120)
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    status: str = Field(default="active", min_length=1, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EntitlementRead(BaseModel):
    id: str
    app_key: str
    key: str
    name: str
    description: Optional[str] = None
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    app_key: str = Field(min_length=2, max_length=120)
    key: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    stripe_product_id: Optional[str] = None
    status: str = Field(default="active", min_length=1, max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductRead(BaseModel):
    id: str
    app_key: str
    key: str
    name: str
    description: Optional[str] = None
    stripe_product_id: Optional[str] = None
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PriceCreate(BaseModel):
    product_key: str = Field(min_length=2, max_length=120)
    key: str = Field(min_length=2, max_length=120)
    stripe_price_id: str = Field(min_length=2, max_length=120)
    stripe_lookup_key: Optional[str] = None
    entitlement_key: Optional[str] = None
    currency: str = Field(default="usd", min_length=3, max_length=10)
    unit_amount: Optional[int] = Field(default=None, ge=0)
    recurring_interval: Optional[str] = Field(default=None, max_length=30)
    active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PriceRead(BaseModel):
    id: str
    product_id: str
    key: str
    stripe_price_id: str
    stripe_lookup_key: Optional[str] = None
    entitlement_key: Optional[str] = None
    currency: str
    unit_amount: Optional[int] = None
    recurring_interval: Optional[str] = None
    active: bool
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class CheckoutSessionCreate(BaseModel):
    account_id: str = Field(min_length=2, max_length=120)
    price_key: str = Field(min_length=2, max_length=120)
    success_url: str = Field(min_length=8, max_length=2048)
    cancel_url: str = Field(min_length=8, max_length=2048)
    quantity: int = Field(default=1, ge=1, le=9999)


class CheckoutSessionRead(BaseModel):
    session_id: str
    url: str
    account_id: str
    stripe_customer_id: str


class PortalSessionCreate(BaseModel):
    account_id: str = Field(min_length=2, max_length=120)
    return_url: str = Field(min_length=8, max_length=2048)


class PortalSessionRead(BaseModel):
    url: str
    account_id: str
    stripe_customer_id: str


class AccountEntitlementRead(BaseModel):
    account_id: str
    app_key: str
    key: str
    name: str
    description: Optional[str] = None
    status: str
    source_subscription_id: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class BillingSubscriptionRead(BaseModel):
    id: str
    account_id: str
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    latest_invoice_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BillingWebhookEventRead(BaseModel):
    id: str
    provider: str
    provider_event_id: str
    event_type: str
    status: str
    signature_verified: bool
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
