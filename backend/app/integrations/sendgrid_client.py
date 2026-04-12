"""
sendgrid_client.py — VitalMind SendGrid email integration.

Supports plain-text and HTML emails with optional template IDs.
Gracefully degrades when SENDGRID_API_KEY is not set.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Default sender — override with SENDGRID_FROM_EMAIL env var
DEFAULT_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@vitalmind.ai")
DEFAULT_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "VitalMind Health")


@dataclass
class SendGridResult:
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    degraded: bool = False   # True when SendGrid is not configured

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
            "degraded": self.degraded,
        }


def _get_api_key() -> Optional[str]:
    key = os.getenv("SENDGRID_API_KEY")
    if not key:
        logger.warning("SendGridClient: SENDGRID_API_KEY not set — email delivery disabled")
    return key


def send_email(
    to_email: str,
    to_name: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    template_id: Optional[str] = None,
    template_data: Optional[dict] = None,
) -> SendGridResult:
    """
    Send an email via SendGrid.

    Args:
        to_email:      Recipient email address
        to_name:       Recipient display name
        subject:       Email subject line
        body_text:     Plain-text fallback body
        body_html:     Optional HTML body (preferred if provided)
        from_email:    Sender email (defaults to SENDGRID_FROM_EMAIL env var)
        from_name:     Sender display name
        reply_to:      Optional reply-to address
        template_id:   SendGrid dynamic template ID (overrides body if set)
        template_data: Key-value pairs for template substitution

    Returns:
        SendGridResult with success flag and HTTP status code.
    """
    api_key = _get_api_key()
    if not api_key:
        return SendGridResult(success=False, degraded=True, error="SendGrid not configured")

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail, To, From, Content, ReplyTo,
            TemplateId, DynamicTemplateData,
        )

        sender_email = from_email or DEFAULT_FROM_EMAIL
        sender_name = from_name or DEFAULT_FROM_NAME

        message = Mail()
        message.to = [To(email=to_email, name=to_name)]
        message.from_email = From(email=sender_email, name=sender_name)
        message.subject = subject

        if reply_to:
            message.reply_to = ReplyTo(email=reply_to)

        if template_id:
            # SendGrid dynamic template mode
            message.template_id = TemplateId(template_id)
            if template_data:
                message.dynamic_template_data = DynamicTemplateData(template_data)
        else:
            # Plain content mode
            message.content = [Content("text/plain", body_text)]
            if body_html:
                message.content.append(Content("text/html", body_html))

        sg = SendGridAPIClient(api_key=api_key)
        response = sg.send(message)

        logger.info(
            "SendGridClient: email sent to=%s status=%d",
            to_email, response.status_code,
        )
        return SendGridResult(success=response.status_code in (200, 201, 202), status_code=response.status_code)

    except ImportError:
        logger.warning("SendGridClient: sendgrid package not installed")
        return SendGridResult(success=False, degraded=True, error="sendgrid package not installed")
    except Exception as exc:
        logger.error("SendGridClient: email failed to=%s: %s", to_email, exc)
        return SendGridResult(success=False, error=str(exc))


def send_bulk_emails(
    recipients: list[dict],  # [{"email": str, "name": str, "data": dict}]
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    template_id: Optional[str] = None,
) -> list[SendGridResult]:
    """
    Send emails to multiple recipients.
    Each recipient can have individual template_data via the 'data' key.
    Returns a list of SendGridResult, one per recipient.
    """
    results = []
    for r in recipients:
        result = send_email(
            to_email=r["email"],
            to_name=r.get("name", ""),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            template_id=template_id,
            template_data=r.get("data"),
        )
        results.append(result)
    return results


def is_configured() -> bool:
    """Return True if SendGrid API key is present."""
    return bool(os.getenv("SENDGRID_API_KEY"))
