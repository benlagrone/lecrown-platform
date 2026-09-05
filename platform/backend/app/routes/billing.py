from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin
from app.core.service_auth import BillingServiceCaller, require_billing_service_caller
from app.models.user import User
from app.schemas.billing import (
    AccountCreate,
    AccountEntitlementRead,
    AccountMembershipCreate,
    AccountMembershipRead,
    AccountRead,
    BillingAppCreate,
    BillingAppRead,
    BillingSubscriptionRead,
    BillingWebhookEventRead,
    CheckoutSessionCreate,
    CheckoutSessionRead,
    EntitlementCreate,
    EntitlementRead,
    PortalSessionCreate,
    PortalSessionRead,
    PriceCreate,
    PriceRead,
    ProductCreate,
    ProductRead,
)
from app.services import billing_service, stripe_service

router = APIRouter()


def _raise_billing_http_error(exc: Exception) -> None:
    if isinstance(exc, billing_service.BillingNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, billing_service.BillingConflictError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, stripe_service.StripeWebhookSignatureError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, stripe_service.StripeConfigurationError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, billing_service.BillingError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@router.get("/apps", response_model=list[BillingAppRead])
def list_billing_apps(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[dict]:
    return [billing_service.serialize_app(app) for app in billing_service.list_apps(db)]


@router.post("/apps", response_model=BillingAppRead, status_code=status.HTTP_201_CREATED)
def create_billing_app(
    payload: BillingAppCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    try:
        app = billing_service.create_or_update_app(db, payload)
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_app(app)


@router.get("/accounts", response_model=list[AccountRead])
def list_billing_accounts(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[dict]:
    return [
        billing_service.serialize_account(account)
        for account in billing_service.list_accounts(db, limit=limit)
    ]


@router.post("/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_billing_account(
    payload: AccountCreate,
    db: Session = Depends(get_db),
    caller: BillingServiceCaller = Depends(require_billing_service_caller),
) -> dict:
    try:
        billing_service.require_known_app(db, caller.app_key)
        account = billing_service.create_account(db, payload)
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_account(account)


@router.get("/accounts/{account_id}/memberships", response_model=list[AccountMembershipRead])
def list_billing_account_memberships(
    account_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[dict]:
    try:
        memberships = billing_service.list_account_memberships(db, account_id)
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return [billing_service.serialize_membership(membership) for membership in memberships]


@router.post(
    "/accounts/{account_id}/memberships",
    response_model=AccountMembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def create_billing_account_membership(
    account_id: str,
    payload: AccountMembershipCreate,
    db: Session = Depends(get_db),
    caller: BillingServiceCaller = Depends(require_billing_service_caller),
) -> dict:
    try:
        membership = billing_service.create_or_update_membership(
            db,
            account_id=account_id,
            app_key=caller.app_key,
            payload=payload,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_membership(membership)


@router.get("/entitlements", response_model=list[EntitlementRead])
def list_billing_entitlements(
    app_key: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[dict]:
    entitlements = billing_service.list_entitlements(db, app_key=app_key)
    return [
        billing_service.serialize_entitlement(entitlement)
        for entitlement in entitlements
    ]


@router.post("/entitlements", response_model=EntitlementRead, status_code=status.HTTP_201_CREATED)
def create_billing_entitlement(
    payload: EntitlementCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    try:
        entitlement = billing_service.create_or_update_entitlement(db, payload)
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_entitlement(entitlement)


@router.get("/products", response_model=list[ProductRead])
def list_billing_products(
    app_key: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[dict]:
    products = billing_service.list_products(db, app_key=app_key)
    return [billing_service.serialize_product(product) for product in products]


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_billing_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    try:
        product = billing_service.create_or_update_product(db, payload)
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_product(product)


@router.get("/prices", response_model=list[PriceRead])
def list_billing_prices(
    app_key: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> list[dict]:
    prices = billing_service.list_prices(db, app_key=app_key)
    return [billing_service.serialize_price(price) for price in prices]


@router.post("/prices", response_model=PriceRead, status_code=status.HTTP_201_CREATED)
def create_billing_price(
    payload: PriceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
) -> dict:
    try:
        price = billing_service.create_or_update_price(db, payload)
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_price(price)


@router.post("/checkout/session", response_model=CheckoutSessionRead)
def create_checkout_session(
    payload: CheckoutSessionCreate,
    db: Session = Depends(get_db),
    caller: BillingServiceCaller = Depends(require_billing_service_caller),
) -> dict:
    try:
        return billing_service.create_checkout_session(
            db,
            account_id=payload.account_id,
            price_key=payload.price_key,
            quantity=payload.quantity,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            caller_app_key=caller.app_key,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)


@router.post("/portal/session", response_model=PortalSessionRead)
def create_portal_session(
    payload: PortalSessionCreate,
    db: Session = Depends(get_db),
    caller: BillingServiceCaller = Depends(require_billing_service_caller),
) -> dict:
    try:
        return billing_service.create_portal_session(
            db,
            payload=payload,
            caller_app_key=caller.app_key,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)


@router.get("/accounts/{account_id}/entitlements", response_model=list[AccountEntitlementRead])
def get_account_entitlements(
    account_id: str,
    only_active: bool = Query(default=True),
    db: Session = Depends(get_db),
    caller: BillingServiceCaller = Depends(require_billing_service_caller),
) -> list[dict]:
    try:
        return billing_service.list_account_entitlements(
            db,
            account_id=account_id,
            app_key=caller.app_key,
            only_active=only_active,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)


@router.get("/accounts/{account_id}/subscriptions", response_model=list[BillingSubscriptionRead])
def get_account_subscriptions(
    account_id: str,
    db: Session = Depends(get_db),
    caller: BillingServiceCaller = Depends(require_billing_service_caller),
) -> list[dict]:
    try:
        subscriptions = billing_service.list_account_subscriptions(
            db,
            account_id=account_id,
            app_key=caller.app_key,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return [
        billing_service.serialize_subscription(subscription)
        for subscription in subscriptions
    ]


@router.post(
    "/webhooks/stripe",
    response_model=BillingWebhookEventRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    payload = await request.body()
    signature_header = request.headers.get("Stripe-Signature")
    try:
        webhook_event = billing_service.process_stripe_webhook(
            db,
            payload=payload,
            signature_header=signature_header,
        )
    except Exception as exc:  # noqa: BLE001
        _raise_billing_http_error(exc)
    return billing_service.serialize_webhook_event(webhook_event)
