from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from typing import Any
from urllib.parse import quote

import requests

from app.config import get_settings

settings = get_settings()


class InviteEmailError(RuntimeError):
    pass


class InviteEmailConfigurationError(InviteEmailError):
    pass


class InviteEmailDeliveryError(InviteEmailError):
    pass


@dataclass(frozen=True)
class InviteEmailDeliveryResult:
    sender_email: str
    message_id: str | None = None


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_expiration(value: datetime) -> str:
    return _coerce_utc(value).strftime("%B %d, %Y at %I:%M %p UTC")


def _resolve_sender_email() -> tuple[str, str]:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise InviteEmailConfigurationError(
            "Invite email delivery is not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
        )

    preferred_sender = _clean(settings.invite_sender_email)
    refresh_tokens = settings.gmail_refresh_tokens
    if preferred_sender:
        refresh_token = _clean(refresh_tokens.get(preferred_sender))
        if preferred_sender not in refresh_tokens:
            raise InviteEmailConfigurationError(
                f"Invite sender mailbox '{preferred_sender}' is not supported."
            )
        if not refresh_token:
            raise InviteEmailConfigurationError(
                f"Invite sender mailbox '{preferred_sender}' does not have a Gmail refresh token configured."
            )
        return preferred_sender, refresh_token

    for email, refresh_token in refresh_tokens.items():
        cleaned_refresh_token = _clean(refresh_token)
        if cleaned_refresh_token:
            return email, cleaned_refresh_token

    raise InviteEmailConfigurationError(
        "Invite email delivery is not configured. Set INVITE_SENDER_EMAIL or provide a Gmail refresh token for a supported mailbox."
    )


def _fetch_access_token(sender_email: str, refresh_token: str) -> str:
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        raise InviteEmailDeliveryError("Failed to refresh the Gmail access token") from exc

    if not response.ok:
        raise InviteEmailConfigurationError(
            f"Google OAuth token refresh failed for '{sender_email}' with {response.status_code}: {response.text[:200]}"
        )

    payload = response.json()
    access_token = _clean(payload.get("access_token"))
    if not access_token:
        raise InviteEmailConfigurationError(
            f"Google OAuth token refresh for '{sender_email}' did not return an access token"
        )
    return access_token


def _invite_url(invite_code: str) -> str:
    base_url = settings.resolved_public_app_url
    return f"{base_url}/#/opportunities?invite_code={quote(invite_code)}"


def _build_plain_email_body(
    *,
    recipient_email: str,
    invite_code: str,
    expires_at: datetime,
    invited_by_email: str | None,
) -> str:
    invite_url = _invite_url(invite_code)
    lines = [
        "Hello,",
        "",
        f"You've been invited to {settings.app_name}.",
        "",
        f"Invite link: {invite_url}",
        f"Invite code: {invite_code}",
        f"Expires: {_format_expiration(expires_at)}",
        "",
        "If the link does not prefill the code, paste the invite code into the activation form.",
    ]
    if invited_by_email:
        lines.extend(["", f"Invite created by: {invited_by_email}"])
    lines.extend(["", f"This message was sent to {recipient_email}."])
    return "\n".join(lines)


def _build_html_email_body(
    *,
    invite_code: str,
    expires_at: datetime,
    invited_by_email: str | None,
) -> str:
    invite_url = _invite_url(invite_code)
    invited_by_line = ""
    if invited_by_email:
        invited_by_line = f"<p><strong>Invite created by:</strong> {escape(invited_by_email)}</p>"
    return "".join(
        [
            "<p>Hello,</p>",
            f"<p>You've been invited to <strong>{escape(settings.app_name)}</strong>.</p>",
            (
                "<p>"
                f'<a href="{escape(invite_url)}">Open the invite link</a><br />'
                f"Invite code: <strong>{escape(invite_code)}</strong><br />"
                f"Expires: <strong>{escape(_format_expiration(expires_at))}</strong>"
                "</p>"
            ),
            "<p>If the link does not prefill the code, paste the invite code into the activation form.</p>",
            invited_by_line,
        ]
    )


def send_user_invite_email(
    *,
    recipient_email: str,
    invite_code: str,
    expires_at: datetime,
    invited_by_email: str | None = None,
) -> InviteEmailDeliveryResult:
    sender_email, refresh_token = _resolve_sender_email()
    access_token = _fetch_access_token(sender_email, refresh_token)

    message = EmailMessage()
    message["To"] = recipient_email
    message["From"] = formataddr((settings.app_name, sender_email))
    message["Subject"] = f"You're invited to {settings.app_name}"
    message.set_content(
        _build_plain_email_body(
            recipient_email=recipient_email,
            invite_code=invite_code,
            expires_at=expires_at,
            invited_by_email=invited_by_email,
        )
    )
    message.add_alternative(
        _build_html_email_body(
            invite_code=invite_code,
            expires_at=expires_at,
            invited_by_email=invited_by_email,
        ),
        subtype="html",
    )

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    try:
        response = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": raw_message},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise InviteEmailDeliveryError("Failed to send the invite email") from exc

    if not response.ok:
        raise InviteEmailDeliveryError(
            f"Invite email send failed with {response.status_code}: {response.text[:200]}"
        )

    payload = response.json()
    return InviteEmailDeliveryResult(
        sender_email=sender_email,
        message_id=_clean(payload.get("id")) or None,
    )
