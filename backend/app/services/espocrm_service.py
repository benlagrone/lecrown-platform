from __future__ import annotations

import base64
from typing import Any

import requests

from app.config import get_settings

settings = get_settings()


class EspoCRMError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


def has_base_url() -> bool:
    return bool(settings.espocrm_base_url.strip())


def has_credentials() -> bool:
    return bool(
        settings.espocrm_api_key
        or (settings.espocrm_username.strip() and settings.espocrm_password.strip())
    )


def is_configured() -> bool:
    return has_base_url() and has_credentials()


def _base_url() -> str:
    base_url = settings.espocrm_base_url.strip().rstrip("/")
    if not base_url:
        raise EspoCRMError("EspoCRM base URL is not configured")
    if base_url.endswith("/api/v1"):
        return base_url
    return f"{base_url}/api/v1"


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if settings.espocrm_api_key:
        headers["X-Api-Key"] = settings.espocrm_api_key
        return headers
    if settings.espocrm_username and settings.espocrm_password:
        token = base64.b64encode(
            f"{settings.espocrm_username}:{settings.espocrm_password}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
        return headers
    raise EspoCRMError("EspoCRM credentials are not configured")


def create_lead(payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{_base_url()}/Lead"
    try:
        response = requests.post(
            url,
            json=payload,
            headers=_headers(),
            timeout=settings.espocrm_timeout_seconds,
        )
    except requests.RequestException as exc:
        raise EspoCRMError("EspoCRM lead request failed") from exc

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code < 200 or response.status_code >= 300:
        raise EspoCRMError(
            "EspoCRM lead request returned a non-success response",
            status_code=response.status_code,
            body=body,
        )

    return body
