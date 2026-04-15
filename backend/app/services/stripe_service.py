from __future__ import annotations

from typing import Any

from app.config import get_settings

settings = get_settings()

try:
    import stripe
except ImportError:  # pragma: no cover - exercised indirectly when SDK is installed
    stripe = None


class StripeConfigurationError(RuntimeError):
    pass


class StripeWebhookSignatureError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.stripe_secret_key.strip())


def webhook_is_configured() -> bool:
    return is_configured() and bool(settings.stripe_webhook_secret.strip())


def _require_stripe() -> Any:
    if stripe is None:
        raise StripeConfigurationError("stripe SDK is not installed")
    if not settings.stripe_secret_key.strip():
        raise StripeConfigurationError("Stripe secret key is not configured")

    stripe.api_key = settings.stripe_secret_key
    stripe.api_version = settings.stripe_api_version
    return stripe


def create_customer(
    *,
    email: str | None,
    name: str | None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    stripe_module = _require_stripe()
    customer = stripe_module.Customer.create(
        email=email or None,
        name=name or None,
        metadata=metadata or {},
    )
    return customer.to_dict_recursive()


def modify_customer(
    customer_id: str,
    *,
    email: str | None,
    name: str | None,
    metadata: dict[str, str] | None = None,
) -> dict[str, Any]:
    stripe_module = _require_stripe()
    customer = stripe_module.Customer.modify(
        customer_id,
        email=email or None,
        name=name or None,
        metadata=metadata or {},
    )
    return customer.to_dict_recursive()


def create_checkout_session(
    *,
    customer_id: str,
    stripe_price_id: str,
    quantity: int,
    success_url: str,
    cancel_url: str,
    client_reference_id: str,
    metadata: dict[str, str],
) -> dict[str, Any]:
    stripe_module = _require_stripe()
    session = stripe_module.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": stripe_price_id, "quantity": quantity}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=client_reference_id,
        allow_promotion_codes=True,
        metadata=metadata,
        subscription_data={"metadata": metadata},
    )
    return session.to_dict_recursive()


def create_portal_session(
    *,
    customer_id: str,
    return_url: str,
) -> dict[str, Any]:
    stripe_module = _require_stripe()
    payload: dict[str, Any] = {
        "customer": customer_id,
        "return_url": return_url,
    }
    if settings.stripe_portal_configuration_id.strip():
        payload["configuration"] = settings.stripe_portal_configuration_id.strip()
    session = stripe_module.billing_portal.Session.create(**payload)
    return session.to_dict_recursive()


def construct_webhook_event(payload: bytes, signature_header: str | None) -> dict[str, Any]:
    stripe_module = _require_stripe()
    if not settings.stripe_webhook_secret.strip():
        raise StripeConfigurationError("Stripe webhook secret is not configured")
    if not signature_header:
        raise StripeWebhookSignatureError("Missing Stripe signature header")
    try:
        event = stripe_module.Webhook.construct_event(
            payload,
            signature_header,
            settings.stripe_webhook_secret,
        )
    except Exception as exc:  # noqa: BLE001
        raise StripeWebhookSignatureError("Stripe webhook signature verification failed") from exc
    return event.to_dict_recursive()
