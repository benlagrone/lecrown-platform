from __future__ import annotations

import base64
from urllib.parse import quote
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
        token = _get_access_token()
        auth_token = _encode_auth_pair(settings.espocrm_username, token)
        headers["Espo-Authorization"] = auth_token
        return headers
    raise EspoCRMError("EspoCRM credentials are not configured")


def _encode_auth_pair(username: str, password_or_token: str) -> str:
    return base64.b64encode(f"{username}:{password_or_token}".encode("utf-8")).decode("ascii")


def _get_access_token() -> str:
    url = f"{_base_url()}/App/user"
    headers = {
        "Accept": "application/json",
        "Espo-Authorization": _encode_auth_pair(settings.espocrm_username, settings.espocrm_password),
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=settings.espocrm_timeout_seconds,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise EspoCRMError("EspoCRM authentication request failed") from exc

    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text}

    if response.status_code < 200 or response.status_code >= 300:
        raise EspoCRMError(
            "EspoCRM authentication returned a non-success response",
            status_code=response.status_code,
            body=body,
        )

    token = body.get("token") if isinstance(body, dict) else None
    if not isinstance(token, str) or not token:
        raise EspoCRMError("EspoCRM authentication response did not include a token")
    return token


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


def list_accounts() -> list[dict[str, Any]]:
    """Read a complete catalog or fail; never return a partial snapshot."""
    headers = _headers()
    accounts: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_total = None
    for _ in range(500):
        try:
            response = requests.get(
                f"{_base_url()}/Account",
                headers=headers,
                params={"select": "id,name,website,description", "maxSize": 200,
                        "offset": len(accounts), "orderBy": "id", "order": "asc"},
                timeout=settings.espocrm_timeout_seconds,
                allow_redirects=False,
            )
            if not 200 <= response.status_code < 300:
                raise EspoCRMError("EspoCRM Account read failed", status_code=response.status_code)
            body = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise EspoCRMError("EspoCRM Account read failed") from exc
        rows = body.get("list") if isinstance(body, dict) else None
        total = body.get("total") if isinstance(body, dict) else None
        if not isinstance(rows, list) or type(total) is not int or total < 0:
            raise EspoCRMError("EspoCRM Account response is malformed or has no exact total")
        if expected_total is not None and total != expected_total:
            raise EspoCRMError("EspoCRM catalog changed during pagination; retry the refresh")
        expected_total = total
        for row in rows:
            account_id = row.get("id") if isinstance(row, dict) else None
            if not isinstance(account_id, str) or not account_id or account_id in seen:
                raise EspoCRMError("EspoCRM Account pagination returned a missing or repeated ID")
            seen.add(account_id)
            accounts.append(row)
        if len(accounts) == total:
            return accounts
        if not rows or len(accounts) > total:
            raise EspoCRMError("EspoCRM Account pagination ended before a complete snapshot")
    raise EspoCRMError("EspoCRM Account catalog exceeded the pagination safety limit")


def _opportunity_request(method: str, path: str = "", **kwargs) -> dict[str, Any]:
    try:
        response = requests.request(
            method, f"{_base_url()}/Opportunity{path}", headers=_headers(),
            timeout=settings.espocrm_timeout_seconds, allow_redirects=False, **kwargs,
        )
    except requests.RequestException as exc:
        raise EspoCRMError("EspoCRM Opportunity request failed; delivery may be uncertain") from exc
    if not 200 <= response.status_code < 300:
        raise EspoCRMError("EspoCRM Opportunity request was rejected", status_code=response.status_code)
    try:
        body = response.json()
    except ValueError as exc:
        raise EspoCRMError("EspoCRM Opportunity response was not JSON; delivery may be uncertain") from exc
    if not isinstance(body, dict):
        raise EspoCRMError("EspoCRM Opportunity response was malformed")
    return body


def create_opportunity(payload: dict[str, Any]) -> dict[str, Any]:
    body = _opportunity_request("POST", json=payload)
    if not isinstance(body.get("id"), str) or not body["id"]:
        raise EspoCRMError("EspoCRM did not return an Opportunity ID; delivery may be uncertain")
    return body


def get_opportunity(record_id: str) -> dict[str, Any]:
    body = _opportunity_request("GET", f"/{quote(record_id, safe='')}")
    if body.get("id") != record_id:
        raise EspoCRMError("EspoCRM Opportunity verification returned a different record")
    return body


def find_opportunity(marker: str) -> dict[str, Any] | None:
    body = _opportunity_request("GET", params={
        "select": "id,description", "maxSize": 2,
        "where[0][type]": "contains", "where[0][attribute]": "description", "where[0][value]": marker,
    })
    rows, total = body.get("list"), body.get("total")
    if not isinstance(rows, list) or type(total) is not int or total != len(rows) or total > 1:
        raise EspoCRMError("Cannot safely reconcile existing CRM Opportunities for this candidate")
    if not rows:
        return None
    if not isinstance(rows[0], dict) or not rows[0].get("id") or marker not in str(rows[0].get("description") or ""):
        raise EspoCRMError("CRM Opportunity reconciliation returned a mismatched record")
    return rows[0]
