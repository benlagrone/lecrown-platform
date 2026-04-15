from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

from app.config import get_settings

settings = get_settings()


@dataclass(frozen=True)
class BillingServiceCaller:
    app_key: str


def require_billing_service_caller(
    x_billing_app: Optional[str] = Header(default=None),
    x_billing_key: Optional[str] = Header(default=None),
) -> BillingServiceCaller:
    app_key = (x_billing_app or "").strip()
    secret = (x_billing_key or "").strip()
    if not app_key or not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Billing service credentials are required",
        )

    expected_secret = settings.billing_service_key_map.get(app_key)
    if expected_secret is None or secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid billing service credentials",
        )
    return BillingServiceCaller(app_key=app_key)
