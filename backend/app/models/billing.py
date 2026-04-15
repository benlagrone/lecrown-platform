from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class BillingApp(Base):
    __tablename__ = "billing_apps"

    id = Column(String, primary_key=True)
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="active")
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    billing_email = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AccountMembership(Base):
    __tablename__ = "account_memberships"

    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, index=True)
    app_key = Column(String, nullable=False, index=True)
    external_user_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True, index=True)
    role = Column(String, nullable=False, default="member")
    status = Column(String, nullable=False, default="active", index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BillingCustomer(Base):
    __tablename__ = "billing_customers"

    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False, default="stripe", index=True)
    stripe_customer_id = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=True, index=True)
    is_default = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    app_key = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    stripe_product_id = Column(String, nullable=True, unique=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(String, primary_key=True)
    app_key = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="active", index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Price(Base):
    __tablename__ = "prices"

    id = Column(String, primary_key=True)
    product_id = Column(String, nullable=False, index=True)
    key = Column(String, nullable=False, unique=True, index=True)
    stripe_price_id = Column(String, nullable=False, unique=True, index=True)
    stripe_lookup_key = Column(String, nullable=True, unique=True, index=True)
    entitlement_key = Column(String, nullable=True, index=True)
    currency = Column(String, nullable=False, default="usd")
    unit_amount = Column(Integer, nullable=True)
    recurring_interval = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BillingSubscription(Base):
    __tablename__ = "billing_subscriptions"

    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, index=True)
    billing_customer_id = Column(String, nullable=True, index=True)
    stripe_customer_id = Column(String, nullable=True, index=True)
    stripe_subscription_id = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, index=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False)
    latest_invoice_id = Column(String, nullable=True)
    raw_payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AccountEntitlement(Base):
    __tablename__ = "account_entitlements"

    id = Column(String, primary_key=True)
    account_id = Column(String, nullable=False, index=True)
    entitlement_key = Column(String, nullable=False, index=True)
    source_subscription_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active", index=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BillingWebhookEvent(Base):
    __tablename__ = "billing_webhook_events"

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False, default="stripe", index=True)
    provider_event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="received", index=True)
    signature_verified = Column(Boolean, nullable=False, default=False)
    payload = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
