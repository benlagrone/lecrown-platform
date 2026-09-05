from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.billing import (
    Account,
    AccountEntitlement,
    AccountMembership,
    BillingApp,
    BillingCustomer,
    BillingSubscription,
    BillingWebhookEvent,
    Entitlement,
    Price,
    Product,
)
from app.schemas.billing import (
    AccountCreate,
    AccountMembershipCreate,
    BillingAppCreate,
    EntitlementCreate,
    PortalSessionCreate,
    PriceCreate,
    ProductCreate,
)
from app.services import stripe_service
from app.utils.helpers import new_uuid

ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing", "past_due"}


class BillingError(RuntimeError):
    pass


class BillingNotFoundError(LookupError):
    pass


class BillingConflictError(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    return dict(metadata or {})


def _timestamp_to_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _subscription_grants_access(status: str | None) -> bool:
    return (status or "").strip().lower() in ACTIVE_SUBSCRIPTION_STATUSES


def _get_app_by_key(db: Session, app_key: str) -> BillingApp | None:
    cleaned_app_key = _clean(app_key)
    if cleaned_app_key is None:
        return None
    return db.scalars(select(BillingApp).where(BillingApp.key == cleaned_app_key)).first()


def require_known_app(db: Session, app_key: str) -> BillingApp:
    app = _get_app_by_key(db, app_key)
    if app is None:
        raise BillingNotFoundError(f"Billing app '{app_key}' was not found")
    if app.status != "active":
        raise BillingConflictError(f"Billing app '{app_key}' is not active")
    return app


def _get_account(db: Session, account_id: str) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise BillingNotFoundError("Account not found")
    return account


def _get_product_by_key(db: Session, product_key: str) -> Product:
    product = db.scalars(select(Product).where(Product.key == product_key)).first()
    if product is None:
        raise BillingNotFoundError(f"Product '{product_key}' was not found")
    return product


def _get_price_by_key(db: Session, price_key: str) -> Price:
    price = db.scalars(select(Price).where(Price.key == price_key)).first()
    if price is None:
        raise BillingNotFoundError(f"Price '{price_key}' was not found")
    return price


def _get_entitlement_by_key(db: Session, entitlement_key: str) -> Entitlement | None:
    cleaned_entitlement_key = _clean(entitlement_key)
    if cleaned_entitlement_key is None:
        return None
    return db.scalars(select(Entitlement).where(Entitlement.key == cleaned_entitlement_key)).first()


def serialize_app(app: BillingApp) -> dict[str, Any]:
    return {
        "id": app.id,
        "key": app.key,
        "name": app.name,
        "base_url": app.base_url,
        "status": app.status,
        "metadata": _normalize_metadata(app.metadata_json),
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


def serialize_account(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "name": account.name,
        "billing_email": account.billing_email,
        "status": account.status,
        "metadata": _normalize_metadata(account.metadata_json),
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def serialize_membership(membership: AccountMembership) -> dict[str, Any]:
    return {
        "id": membership.id,
        "account_id": membership.account_id,
        "app_key": membership.app_key,
        "external_user_id": membership.external_user_id,
        "email": membership.email,
        "role": membership.role,
        "status": membership.status,
        "metadata": _normalize_metadata(membership.metadata_json),
        "created_at": membership.created_at,
        "updated_at": membership.updated_at,
    }


def serialize_entitlement(entitlement: Entitlement) -> dict[str, Any]:
    return {
        "id": entitlement.id,
        "app_key": entitlement.app_key,
        "key": entitlement.key,
        "name": entitlement.name,
        "description": entitlement.description,
        "status": entitlement.status,
        "metadata": _normalize_metadata(entitlement.metadata_json),
        "created_at": entitlement.created_at,
        "updated_at": entitlement.updated_at,
    }


def serialize_product(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "app_key": product.app_key,
        "key": product.key,
        "name": product.name,
        "description": product.description,
        "stripe_product_id": product.stripe_product_id,
        "status": product.status,
        "metadata": _normalize_metadata(product.metadata_json),
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def serialize_price(price: Price) -> dict[str, Any]:
    return {
        "id": price.id,
        "product_id": price.product_id,
        "key": price.key,
        "stripe_price_id": price.stripe_price_id,
        "stripe_lookup_key": price.stripe_lookup_key,
        "entitlement_key": price.entitlement_key,
        "currency": price.currency,
        "unit_amount": price.unit_amount,
        "recurring_interval": price.recurring_interval,
        "active": price.active,
        "metadata": _normalize_metadata(price.metadata_json),
        "created_at": price.created_at,
        "updated_at": price.updated_at,
    }


def serialize_subscription(subscription: BillingSubscription) -> dict[str, Any]:
    return {
        "id": subscription.id,
        "account_id": subscription.account_id,
        "stripe_customer_id": subscription.stripe_customer_id,
        "stripe_subscription_id": subscription.stripe_subscription_id,
        "status": subscription.status,
        "current_period_start": subscription.current_period_start,
        "current_period_end": subscription.current_period_end,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "latest_invoice_id": subscription.latest_invoice_id,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
    }


def serialize_webhook_event(event: BillingWebhookEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "provider": event.provider,
        "provider_event_id": event.provider_event_id,
        "event_type": event.event_type,
        "status": event.status,
        "signature_verified": event.signature_verified,
        "error_message": event.error_message,
        "processed_at": event.processed_at,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }


def list_apps(db: Session) -> list[BillingApp]:
    return list(db.scalars(select(BillingApp).order_by(BillingApp.key.asc())).all())


def create_or_update_app(db: Session, payload: BillingAppCreate) -> BillingApp:
    app = _get_app_by_key(db, payload.key)
    if app is None:
        app = BillingApp(
            id=new_uuid(),
            key=payload.key.strip(),
            name=payload.name.strip(),
            base_url=_clean(payload.base_url),
            status=payload.status.strip(),
            metadata_json=_normalize_metadata(payload.metadata),
        )
    else:
        app.name = payload.name.strip()
        app.base_url = _clean(payload.base_url)
        app.status = payload.status.strip()
        app.metadata_json = _normalize_metadata(payload.metadata)
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


def list_accounts(db: Session, *, limit: int = 100) -> list[Account]:
    statement = select(Account).order_by(desc(Account.created_at)).limit(limit)
    return list(db.scalars(statement).all())


def create_account(db: Session, payload: AccountCreate) -> Account:
    account = Account(
        id=new_uuid(),
        name=payload.name.strip(),
        billing_email=_clean(payload.billing_email),
        status="active",
        metadata_json=_normalize_metadata(payload.metadata),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_account_memberships(db: Session, account_id: str) -> list[AccountMembership]:
    _get_account(db, account_id)
    statement = (
        select(AccountMembership)
        .where(AccountMembership.account_id == account_id)
        .order_by(AccountMembership.created_at.asc())
    )
    return list(db.scalars(statement).all())


def create_or_update_membership(
    db: Session,
    *,
    account_id: str,
    app_key: str,
    payload: AccountMembershipCreate,
) -> AccountMembership:
    _get_account(db, account_id)
    membership = db.scalars(
        select(AccountMembership).where(
            AccountMembership.account_id == account_id,
            AccountMembership.app_key == app_key,
            AccountMembership.external_user_id == payload.external_user_id.strip(),
        )
    ).first()
    if membership is None:
        membership = AccountMembership(
            id=new_uuid(),
            account_id=account_id,
            app_key=app_key,
            external_user_id=payload.external_user_id.strip(),
            email=_clean(payload.email),
            role=payload.role.strip(),
            status=payload.status.strip(),
            metadata_json=_normalize_metadata(payload.metadata),
        )
    else:
        membership.email = _clean(payload.email)
        membership.role = payload.role.strip()
        membership.status = payload.status.strip()
        membership.metadata_json = _normalize_metadata(payload.metadata)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def list_entitlements(db: Session, *, app_key: str | None = None) -> list[Entitlement]:
    statement = select(Entitlement)
    if app_key:
        statement = statement.where(Entitlement.app_key == app_key)
    statement = statement.order_by(Entitlement.app_key.asc(), Entitlement.key.asc())
    return list(db.scalars(statement).all())


def create_or_update_entitlement(db: Session, payload: EntitlementCreate) -> Entitlement:
    require_known_app(db, payload.app_key)
    entitlement = _get_entitlement_by_key(db, payload.key)
    if entitlement is None:
        entitlement = Entitlement(
            id=new_uuid(),
            app_key=payload.app_key.strip(),
            key=payload.key.strip(),
            name=payload.name.strip(),
            description=_clean(payload.description),
            status=payload.status.strip(),
            metadata_json=_normalize_metadata(payload.metadata),
        )
    else:
        entitlement.app_key = payload.app_key.strip()
        entitlement.name = payload.name.strip()
        entitlement.description = _clean(payload.description)
        entitlement.status = payload.status.strip()
        entitlement.metadata_json = _normalize_metadata(payload.metadata)
    db.add(entitlement)
    db.commit()
    db.refresh(entitlement)
    return entitlement


def list_products(db: Session, *, app_key: str | None = None) -> list[Product]:
    statement = select(Product)
    if app_key:
        statement = statement.where(Product.app_key == app_key)
    statement = statement.order_by(Product.app_key.asc(), Product.key.asc())
    return list(db.scalars(statement).all())


def create_or_update_product(db: Session, payload: ProductCreate) -> Product:
    require_known_app(db, payload.app_key)
    product = db.scalars(select(Product).where(Product.key == payload.key)).first()
    if product is None:
        product = Product(
            id=new_uuid(),
            app_key=payload.app_key.strip(),
            key=payload.key.strip(),
            name=payload.name.strip(),
            description=_clean(payload.description),
            stripe_product_id=_clean(payload.stripe_product_id),
            status=payload.status.strip(),
            metadata_json=_normalize_metadata(payload.metadata),
        )
    else:
        product.app_key = payload.app_key.strip()
        product.name = payload.name.strip()
        product.description = _clean(payload.description)
        product.stripe_product_id = _clean(payload.stripe_product_id)
        product.status = payload.status.strip()
        product.metadata_json = _normalize_metadata(payload.metadata)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def list_prices(db: Session, *, app_key: str | None = None) -> list[Price]:
    statement = select(Price)
    if app_key:
        product_ids = [
            product.id
            for product in db.scalars(select(Product).where(Product.app_key == app_key)).all()
        ]
        if not product_ids:
            return []
        statement = statement.where(Price.product_id.in_(product_ids))
    statement = statement.order_by(Price.created_at.desc())
    return list(db.scalars(statement).all())


def create_or_update_price(db: Session, payload: PriceCreate) -> Price:
    product = _get_product_by_key(db, payload.product_key)
    if payload.entitlement_key:
        entitlement = _get_entitlement_by_key(db, payload.entitlement_key)
        if entitlement is None:
            raise BillingNotFoundError(f"Entitlement '{payload.entitlement_key}' was not found")
        if entitlement.app_key != product.app_key:
            raise BillingConflictError("Price entitlement must belong to the same app as the product")

    price = db.scalars(select(Price).where(Price.key == payload.key)).first()
    if price is None:
        price = Price(
            id=new_uuid(),
            product_id=product.id,
            key=payload.key.strip(),
            stripe_price_id=payload.stripe_price_id.strip(),
            stripe_lookup_key=_clean(payload.stripe_lookup_key),
            entitlement_key=_clean(payload.entitlement_key),
            currency=payload.currency.strip().lower(),
            unit_amount=payload.unit_amount,
            recurring_interval=_clean(payload.recurring_interval),
            active=payload.active,
            metadata_json=_normalize_metadata(payload.metadata),
        )
    else:
        price.product_id = product.id
        price.stripe_price_id = payload.stripe_price_id.strip()
        price.stripe_lookup_key = _clean(payload.stripe_lookup_key)
        price.entitlement_key = _clean(payload.entitlement_key)
        price.currency = payload.currency.strip().lower()
        price.unit_amount = payload.unit_amount
        price.recurring_interval = _clean(payload.recurring_interval)
        price.active = payload.active
        price.metadata_json = _normalize_metadata(payload.metadata)
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


def _ensure_customer_record(
    db: Session,
    *,
    account: Account,
    stripe_customer_id: str,
    email: str | None,
) -> BillingCustomer:
    customer = db.scalars(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
    ).first()
    if customer is None:
        customer = BillingCustomer(
            id=new_uuid(),
            account_id=account.id,
            provider="stripe",
            stripe_customer_id=stripe_customer_id,
            email=email,
            is_default=True,
        )
    else:
        customer.account_id = account.id
        customer.email = email or customer.email
        customer.is_default = True
    db.add(customer)
    db.flush()
    return customer


def _get_or_create_default_customer(db: Session, *, account: Account) -> BillingCustomer:
    customer = db.scalars(
        select(BillingCustomer)
        .where(
            BillingCustomer.account_id == account.id,
            BillingCustomer.provider == "stripe",
            BillingCustomer.is_default.is_(True),
        )
        .order_by(BillingCustomer.created_at.asc())
    ).first()
    if customer is not None:
        stripe_service.modify_customer(
            customer.stripe_customer_id,
            email=account.billing_email,
            name=account.name,
            metadata={"account_id": account.id},
        )
        customer.email = account.billing_email or customer.email
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer

    created_customer = stripe_service.create_customer(
        email=account.billing_email,
        name=account.name,
        metadata={"account_id": account.id},
    )
    customer = BillingCustomer(
        id=new_uuid(),
        account_id=account.id,
        provider="stripe",
        stripe_customer_id=str(created_customer["id"]),
        email=account.billing_email,
        is_default=True,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def create_checkout_session(
    db: Session,
    *,
    account_id: str,
    price_key: str,
    quantity: int,
    success_url: str,
    cancel_url: str,
    caller_app_key: str,
) -> dict[str, Any]:
    require_known_app(db, caller_app_key)
    account = _get_account(db, account_id)
    price = _get_price_by_key(db, price_key)
    if not price.active:
        raise BillingConflictError(f"Price '{price_key}' is not active")
    product = db.get(Product, price.product_id)
    if product is None:
        raise BillingNotFoundError("Product not found for price")
    if product.app_key != caller_app_key:
        raise BillingConflictError("Requested price does not belong to the calling app")

    customer = _get_or_create_default_customer(db, account=account)
    metadata = {
        "account_id": account.id,
        "app_key": caller_app_key,
        "price_key": price.key,
    }
    session = stripe_service.create_checkout_session(
        customer_id=customer.stripe_customer_id,
        stripe_price_id=price.stripe_price_id,
        quantity=quantity,
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=account.id,
        metadata=metadata,
    )
    return {
        "session_id": str(session["id"]),
        "url": str(session["url"]),
        "account_id": account.id,
        "stripe_customer_id": customer.stripe_customer_id,
    }


def create_portal_session(
    db: Session,
    *,
    payload: PortalSessionCreate,
    caller_app_key: str,
) -> dict[str, Any]:
    require_known_app(db, caller_app_key)
    account = _get_account(db, payload.account_id)
    customer = _get_or_create_default_customer(db, account=account)
    session = stripe_service.create_portal_session(
        customer_id=customer.stripe_customer_id,
        return_url=payload.return_url,
    )
    return {
        "url": str(session["url"]),
        "account_id": account.id,
        "stripe_customer_id": customer.stripe_customer_id,
    }


def _subscription_entitlement_keys(db: Session, subscription: BillingSubscription) -> set[str]:
    raw_payload = subscription.raw_payload or {}
    items = ((raw_payload.get("items") or {}).get("data") or [])
    stripe_price_ids: list[str] = []
    for item in items:
        price = item.get("price") if isinstance(item, dict) else None
        price_id = None
        if isinstance(price, dict):
            price_id = _clean(price.get("id"))
        elif price is not None:
            price_id = _clean(price)
        if price_id:
            stripe_price_ids.append(price_id)

    if not stripe_price_ids:
        return set()

    prices = db.scalars(select(Price).where(Price.stripe_price_id.in_(stripe_price_ids))).all()
    return {
        price.entitlement_key
        for price in prices
        if price.entitlement_key and price.active
    }


def _subscription_matches_app(db: Session, subscription: BillingSubscription, app_key: str) -> bool:
    raw_payload = subscription.raw_payload or {}
    items = ((raw_payload.get("items") or {}).get("data") or [])
    stripe_price_ids: list[str] = []
    for item in items:
        price = item.get("price") if isinstance(item, dict) else None
        if isinstance(price, dict):
            price_id = _clean(price.get("id"))
        else:
            price_id = _clean(price)
        if price_id:
            stripe_price_ids.append(price_id)
    if not stripe_price_ids:
        return False
    matched_prices = db.scalars(select(Price).where(Price.stripe_price_id.in_(stripe_price_ids))).all()
    product_ids = {price.product_id for price in matched_prices}
    if not product_ids:
        return False
    matched_products = db.scalars(
        select(Product).where(Product.id.in_(product_ids), Product.app_key == app_key)
    ).all()
    return bool(matched_products)


def _sync_account_entitlements(db: Session, account_id: str) -> None:
    subscriptions = db.scalars(
        select(BillingSubscription).where(BillingSubscription.account_id == account_id)
    ).all()
    granted_by_key: dict[str, BillingSubscription] = {}
    for subscription in subscriptions:
        if not _subscription_grants_access(subscription.status):
            continue
        for entitlement_key in _subscription_entitlement_keys(db, subscription):
            granted_by_key.setdefault(entitlement_key, subscription)

    existing_rows = db.scalars(
        select(AccountEntitlement).where(AccountEntitlement.account_id == account_id)
    ).all()
    existing_by_key = {row.entitlement_key: row for row in existing_rows}
    now = _utc_now()

    for entitlement_key, source_subscription in granted_by_key.items():
        row = existing_by_key.get(entitlement_key)
        if row is None:
            row = AccountEntitlement(
                id=new_uuid(),
                account_id=account_id,
                entitlement_key=entitlement_key,
                source_subscription_id=source_subscription.id,
                status="active",
                starts_at=source_subscription.current_period_start or now,
                ends_at=None,
                metadata_json={},
            )
        else:
            row.source_subscription_id = source_subscription.id
            row.status = "active"
            row.starts_at = row.starts_at or source_subscription.current_period_start or now
            row.ends_at = None
        db.add(row)

    for entitlement_key, row in existing_by_key.items():
        if entitlement_key in granted_by_key or row.status == "inactive":
            continue
        row.status = "inactive"
        row.ends_at = row.ends_at or now
        db.add(row)


def _sync_subscription_from_payload(
    db: Session,
    subscription_payload: dict[str, Any],
    *,
    account_id_hint: str | None = None,
) -> BillingSubscription:
    stripe_subscription_id = _clean(subscription_payload.get("id"))
    if stripe_subscription_id is None:
        raise BillingError("Stripe subscription payload is missing an id")

    metadata = subscription_payload.get("metadata") or {}
    stripe_customer_id = _clean(subscription_payload.get("customer"))
    account_id = _clean(metadata.get("account_id")) or _clean(account_id_hint)

    billing_customer = None
    if stripe_customer_id:
        billing_customer = db.scalars(
            select(BillingCustomer).where(BillingCustomer.stripe_customer_id == stripe_customer_id)
        ).first()
        if billing_customer is not None and account_id is None:
            account_id = billing_customer.account_id

    if account_id is None:
        raise BillingError("Stripe subscription payload is missing account context")

    account = _get_account(db, account_id)
    if billing_customer is None and stripe_customer_id:
        billing_customer = _ensure_customer_record(
            db,
            account=account,
            stripe_customer_id=stripe_customer_id,
            email=account.billing_email,
        )

    subscription = db.scalars(
        select(BillingSubscription).where(
            BillingSubscription.stripe_subscription_id == stripe_subscription_id
        )
    ).first()
    if subscription is None:
        subscription = BillingSubscription(
            id=new_uuid(),
            account_id=account.id,
            billing_customer_id=billing_customer.id if billing_customer else None,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            status=_clean(subscription_payload.get("status")) or "incomplete",
            current_period_start=_timestamp_to_utc(subscription_payload.get("current_period_start")),
            current_period_end=_timestamp_to_utc(subscription_payload.get("current_period_end")),
            cancel_at_period_end=bool(subscription_payload.get("cancel_at_period_end")),
            latest_invoice_id=_clean(subscription_payload.get("latest_invoice")),
            raw_payload=subscription_payload,
        )
    else:
        subscription.account_id = account.id
        subscription.billing_customer_id = billing_customer.id if billing_customer else None
        subscription.stripe_customer_id = stripe_customer_id
        subscription.status = _clean(subscription_payload.get("status")) or subscription.status
        subscription.current_period_start = _timestamp_to_utc(
            subscription_payload.get("current_period_start")
        )
        subscription.current_period_end = _timestamp_to_utc(
            subscription_payload.get("current_period_end")
        )
        subscription.cancel_at_period_end = bool(subscription_payload.get("cancel_at_period_end"))
        subscription.latest_invoice_id = _clean(subscription_payload.get("latest_invoice"))
        subscription.raw_payload = subscription_payload

    db.add(subscription)
    db.flush()
    _sync_account_entitlements(db, account.id)
    return subscription


def list_account_entitlements(
    db: Session,
    *,
    account_id: str,
    app_key: str,
    only_active: bool = True,
) -> list[dict[str, Any]]:
    _get_account(db, account_id)
    entitlement_rows = db.scalars(
        select(AccountEntitlement).where(AccountEntitlement.account_id == account_id)
    ).all()
    if only_active:
        entitlement_rows = [row for row in entitlement_rows if row.status == "active"]
    if not entitlement_rows:
        return []

    entitlement_keys = [row.entitlement_key for row in entitlement_rows]
    entitlements = {
        entitlement.key: entitlement
        for entitlement in db.scalars(
            select(Entitlement).where(
                Entitlement.key.in_(entitlement_keys),
                Entitlement.app_key == app_key,
            )
        ).all()
    }

    results: list[dict[str, Any]] = []
    for row in entitlement_rows:
        entitlement = entitlements.get(row.entitlement_key)
        if entitlement is None:
            continue
        results.append(
            {
                "account_id": row.account_id,
                "app_key": entitlement.app_key,
                "key": entitlement.key,
                "name": entitlement.name,
                "description": entitlement.description,
                "status": row.status,
                "source_subscription_id": row.source_subscription_id,
                "starts_at": row.starts_at,
                "ends_at": row.ends_at,
                "metadata": _normalize_metadata(row.metadata_json),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
    return results


def list_account_subscriptions(
    db: Session,
    *,
    account_id: str,
    app_key: str,
) -> list[BillingSubscription]:
    _get_account(db, account_id)
    subscriptions = db.scalars(
        select(BillingSubscription)
        .where(BillingSubscription.account_id == account_id)
        .order_by(desc(BillingSubscription.created_at))
    ).all()
    return [
        subscription
        for subscription in subscriptions
        if _subscription_matches_app(db, subscription, app_key)
    ]


def _handle_checkout_completed(db: Session, event_object: dict[str, Any]) -> None:
    account_id = _clean((event_object.get("metadata") or {}).get("account_id")) or _clean(
        event_object.get("client_reference_id")
    )
    stripe_customer_id = _clean(event_object.get("customer"))
    if account_id is None or stripe_customer_id is None:
        return
    account = _get_account(db, account_id)
    customer_email = _clean(((event_object.get("customer_details") or {}).get("email")))
    _ensure_customer_record(
        db,
        account=account,
        stripe_customer_id=stripe_customer_id,
        email=customer_email or account.billing_email,
    )


def process_stripe_webhook(
    db: Session,
    *,
    payload: bytes,
    signature_header: str | None,
) -> BillingWebhookEvent:
    event = stripe_service.construct_webhook_event(payload, signature_header)
    provider_event_id = _clean(event.get("id"))
    event_type = _clean(event.get("type"))
    if provider_event_id is None or event_type is None:
        raise BillingError("Stripe webhook payload is missing event metadata")

    webhook_event = db.scalars(
        select(BillingWebhookEvent).where(BillingWebhookEvent.provider_event_id == provider_event_id)
    ).first()
    if webhook_event is None:
        webhook_event = BillingWebhookEvent(
            id=new_uuid(),
            provider="stripe",
            provider_event_id=provider_event_id,
            event_type=event_type,
            status="received",
            signature_verified=True,
            payload=event,
        )
        db.add(webhook_event)
        db.flush()
    elif webhook_event.status == "processed":
        return webhook_event
    else:
        webhook_event.event_type = event_type
        webhook_event.signature_verified = True
        webhook_event.payload = event
        webhook_event.error_message = None

    try:
        event_object = ((event.get("data") or {}).get("object")) or {}
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, event_object)
            webhook_event.status = "processed"
        elif event_type.startswith("customer.subscription."):
            account_id_hint = _clean((event_object.get("metadata") or {}).get("account_id"))
            _sync_subscription_from_payload(
                db,
                event_object,
                account_id_hint=account_id_hint,
            )
            webhook_event.status = "processed"
        else:
            webhook_event.status = "ignored"
        webhook_event.processed_at = _utc_now()
        db.add(webhook_event)
        db.commit()
        db.refresh(webhook_event)
        return webhook_event
    except Exception as exc:  # noqa: BLE001
        webhook_event.status = "failed"
        webhook_event.error_message = str(exc)
        webhook_event.processed_at = _utc_now()
        db.add(webhook_event)
        db.commit()
        raise
