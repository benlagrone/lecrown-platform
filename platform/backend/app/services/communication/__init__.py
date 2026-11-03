from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests
from pydantic import BaseModel

from app.config import get_settings
from app.models.gov_contract import GovContractTask

logger = logging.getLogger(__name__)
settings = get_settings()


class CommunicationError(RuntimeError):
    pass


class CommunicationConfigurationError(CommunicationError):
    pass


class CommunicationDeliveryError(CommunicationError):
    pass


# Recipients that are allowed to receive automated messages
ALLOWED_RECIPIENTS = {
    "benjaminlagrone@gmail.com",
    "jie.huang@lecrowndevelopment.com"
}


class TaskProgressRecord(BaseModel):
    """Represents a record of task progress and communication"""
    task_id: str
    task_type: str  # e.g., 'certification', 'contracting'
    message_id: Optional[str] = None
    status: str  # 'queued', 'sent', 'delivery_unknown', 'failed'
    recipient: str
    subject: str
    content: str
    created_at: datetime
    updated_at: datetime
    related_task_id: Optional[str] = None


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_sender_email() -> tuple[str, str]:
    """Resolve the sender email and refresh token from settings"""
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise CommunicationConfigurationError(
            "Communication is not configured. Set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET."
        )

    preferred_sender = _clean(settings.invite_sender_email)
    refresh_tokens = settings.gmail_refresh_tokens
    if preferred_sender:
        refresh_token = _clean(refresh_tokens.get(preferred_sender))
        if preferred_sender not in refresh_tokens:
            raise CommunicationConfigurationError(
                f"Communications sender mailbox '{preferred_sender}' is not supported."
            )
        if not refresh_token:
            raise CommunicationConfigurationError(
                f"Communications sender mailbox '{preferred_sender}' does not have a Gmail refresh token configured."
            )
        return preferred_sender, refresh_token

    for email, refresh_token in refresh_tokens.items():
        cleaned_refresh_token = _clean(refresh_token)
        if cleaned_refresh_token:
            return email, cleaned_refresh_token

    raise CommunicationConfigurationError(
        "Communication is not configured. Set INVITE_SENDER_EMAIL or provide a Gmail refresh token for a supported mailbox."
    )


def _fetch_access_token(sender_email: str, refresh_token: str) -> str:
    """Fetch an access token using the refresh token"""
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
        raise CommunicationDeliveryError("Failed to refresh the Gmail access token") from exc

    if not response.ok:
        raise CommunicationConfigurationError(
            f"Google OAuth token refresh failed for '{sender_email}' with {response.status_code}: {response.text[:200]}"
        )

    payload = response.json()
    access_token = _clean(payload.get("access_token"))
    if not access_token:
        raise CommunicationConfigurationError(
            f"Google OAuth token refresh for '{sender_email}' did not return an access token"
        )
    return access_token


def _build_plain_email_body(
    *,
    subject: str,
    content: str,
    recipient_email: str,
    task_id: str,
    task_type: str,
    related_task_id: Optional[str] = None,
) -> str:
    """Build plain text email body"""
    lines = [
        "Hello,",
        "",
        f"This is an automated message from Sextant automation for {task_type} task {task_id}.",
        "",
        content,
        "",
        "Next action required or status update.",
        ""
    ]
    
    if related_task_id:
        lines.extend([
            f"Related task ID: {related_task_id}",
            ""
        ])
    
    lines.extend([
        "Message sent from Sextant automation system.",
        f"Task: {task_id}",
        f"Time: {_coerce_utc(datetime.now()).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        f"This message was sent to {recipient_email}."
    ])
    
    return "\n".join(lines)


def _build_html_email_body(
    *,
    subject: str,
    content: str,
    recipient_email: str,
    task_id: str,
    task_type: str,
    related_task_id: Optional[str] = None,
) -> str:
    """Build HTML email body"""
    return "".join([
        "<p>Hello,</p>",
        f"<p>This is an automated message from Sextant automation for <strong>{task_type}</strong> task <strong>{task_id}</strong>.</p>",
        f"<p><strong>Subject:</strong> {subject}</p>",
        f"<p><strong>Content:</strong></p>",
        f"<p>{content}</p>",
        "<p><strong>Next action required or status update.</strong></p>",
        ""
    ])


def send_communication_email(
    *,
    recipient_email: str,
    subject: str,
    content: str,
    task_id: str,
    task_type: str,
    related_task_id: Optional[str] = None,
) -> str:
    """Send an email to the specified recipient with communication details"""
    
    # Validate recipient
    if recipient_email.lower() not in ALLOWED_RECIPIENTS:
        raise CommunicationConfigurationError(
            f"Recipient {recipient_email} is not authorized for automated communication."
        )
    
    sender_email, refresh_token = _resolve_sender_email()
    access_token = _fetch_access_token(sender_email, refresh_token)

    message = EmailMessage()
    message["To"] = recipient_email
    message["From"] = formataddr((settings.app_name, sender_email))
    message["Subject"] = subject
    message.set_content(
        _build_plain_email_body(
            subject=subject,
            content=content,
            recipient_email=recipient_email,
            task_id=task_id,
            task_type=task_type,
            related_task_id=related_task_id,
        )
    )
    message.add_alternative(
        _build_html_email_body(
            subject=subject,
            content=content,
            recipient_email=recipient_email,
            task_id=task_id,
            task_type=task_type,
            related_task_id=related_task_id,
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
        raise CommunicationDeliveryError("Failed to send the communication email") from exc

    if not response.ok:
        raise CommunicationDeliveryError(
            f"Communication email send failed with {response.status_code}: {response.text[:200]}"
        )

    payload = response.json()
    message_id = _clean(payload.get("id")) or None
    
    logger.info(f"Communication email sent to {recipient_email} for task {task_id}, message ID: {message_id}")
    
    return message_id


def record_task_progress(
    *,
    task_id: str,
    task_type: str,
    recipient: str,
    subject: str,
    content: str,
    status: str = "sent",
    related_task_id: Optional[str] = None
) -> TaskProgressRecord:
    """Record the task progress in a durable way"""
    # This would typically write to a database or file system
    # For now, we'll simulate with an in-memory approach
    
    record = TaskProgressRecord(
        task_id=task_id,
        task_type=task_type,
        recipient=recipient,
        subject=subject,
        content=content,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        related_task_id=related_task_id
    )
    
    logger.info(f"Task progress recorded for {task_id}")
    return record


def handle_inbound_reply(
    *,
    message_id: str,
    sender_email: str,
    subject: str,
    content: str
) -> bool:
    """Handle an inbound reply to a communication email"""
    # Validate sender is one of our allowed recipients
    if sender_email.lower() not in ALLOWED_RECIPIENTS:
        logger.warning(f"Unauthorized sender {sender_email} attempted to reply")
        return False
    
    # This would check if the message_id corresponds to an existing task
    # For now, we'll just log that a reply was received
    
    logger.info(f"Inbound reply received from {sender_email} for message {message_id}")
    
    # In a real implementation, we would:
    # 1. Look up the original communication by message_id
    # 2. Validate it's still relevant (not expired)
    # 3. Update the corresponding task with the reply content
    # 4. Log the audit trail
    
    return True


def process_task_milestone(
    *,
    task: GovContractTask,
    milestone_type: str,
    description: str,
    related_task_id: Optional[str] = None
) -> None:
    """Process a task milestone and send communication to authorized recipients"""
    
    if milestone_type == "certification_eligibility_review":
        # Example milestone handling for certification eligibility review
        subject = f"Certification Eligibility Review - {task.title}"
        content = (
            f"Certification eligibility review completed for {task.title}.\n"
            f"Decision: {description}\n\n"
            "Please review the next steps."
        )
        
    elif milestone_type == "application_submitted":
        # Example milestone handling for application submission
        subject = f"Application Submitted - {task.title}"
        content = (
            f"Application submitted for {task.title}.\n"
            f"Status: {description}\n\n"
            "Awaiting confirmation from the portal."
        )
        
    elif milestone_type == "require_input":
        # Example milestone handling for requiring input
        subject = f"Input Required - {task.title}"
        content = (
            f"Input required for {task.title}.\n"
            f"Reason: {description}\n\n"
            "Please provide the necessary information to proceed."
        )
        
    elif milestone_type == "failure":
        # Example milestone handling for failure
        subject = f"Task Failed - {task.title}"
        content = (
            f"Task failed for {task.title}.\n"
            f"Error: {description}\n\n"
            "Please review and take corrective action."
        )
        
    else:
        # Default case
        subject = f"Task Update - {task.title}"
        content = description
    
    # Send to both authorized recipients
    for recipient in ALLOWED_RECIPIENTS:
        try:
            message_id = send_communication_email(
                recipient_email=recipient,
                subject=subject,
                content=content,
                task_id=task.id,
                task_type="gov_contract",
                related_task_id=related_task_id
            )
            
            # Record the progress
            record_task_progress(
                task_id=task.id,
                task_type="gov_contract",
                recipient=recipient,
                subject=subject,
                content=content,
                status="sent",
                related_task_id=related_task_id
            )
            
        except CommunicationError as e:
            logger.error(f"Failed to send communication to {recipient}: {e}")
            # Record failure in the task progress
            record_task_progress(
                task_id=task.id,
                task_type="gov_contract",
                recipient=recipient,
                subject=subject,
                content=content,
                status="failed",
                related_task_id=related_task_id
            )
            continue

