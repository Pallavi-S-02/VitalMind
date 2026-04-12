"""
twilio_client.py — VitalMind Twilio integration (SMS + Voice calls).

Gracefully degrades if TWILIO_* env vars are not set — all errors are logged
and the function returns a structured result indicating degraded state.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TwilioResult:
    success: bool
    sid: Optional[str] = None
    error: Optional[str] = None
    degraded: bool = False   # True when Twilio is not configured

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "sid": self.sid,
            "error": self.error,
            "degraded": self.degraded,
        }


def _get_client():
    """Build a Twilio REST client. Returns None if credentials missing."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid or not auth_token:
        return None, None

    try:
        from twilio.rest import Client
        return Client(account_sid, auth_token), os.getenv("TWILIO_FROM_NUMBER", "")
    except ImportError:
        logger.warning("TwilioClient: twilio package not installed — SMS/voice unavailable")
        return None, None
    except Exception as exc:
        logger.error("TwilioClient: failed to initialise client: %s", exc)
        return None, None


def send_sms(to: str, body: str) -> TwilioResult:
    """
    Send an SMS message via Twilio.

    Args:
        to:   Recipient phone number in E.164 format (+15551234567)
        body: SMS message text (max 1600 chars; long messages auto-split)

    Returns:
        TwilioResult with success flag and message SID.
    """
    client, from_number = _get_client()
    if not client:
        logger.warning("TwilioClient: SMS skipped (not configured) → would send to %s", to)
        return TwilioResult(success=False, degraded=True, error="Twilio not configured")

    if not from_number:
        return TwilioResult(success=False, error="TWILIO_FROM_NUMBER not set")

    try:
        message = client.messages.create(body=body[:1600], from_=from_number, to=to)
        logger.info("TwilioClient: SMS sent SID=%s to=%s", message.sid, to)
        return TwilioResult(success=True, sid=message.sid)
    except Exception as exc:
        logger.error("TwilioClient: SMS failed to=%s: %s", to, exc)
        return TwilioResult(success=False, error=str(exc))


def send_voice_call(to: str, twiml_url: str) -> TwilioResult:
    """
    Initiate an automated voice call via Twilio.

    Args:
        to:         Recipient phone number in E.164 format
        twiml_url:  Publicly reachable URL that serves TwiML for the call script

    Returns:
        TwilioResult with success flag and call SID.
    """
    client, from_number = _get_client()
    if not client:
        logger.warning("TwilioClient: voice call skipped (not configured) → would call %s", to)
        return TwilioResult(success=False, degraded=True, error="Twilio not configured")

    if not from_number:
        return TwilioResult(success=False, error="TWILIO_FROM_NUMBER not set")

    try:
        call = client.calls.create(to=to, from_=from_number, url=twiml_url)
        logger.info("TwilioClient: voice call initiated SID=%s to=%s", call.sid, to)
        return TwilioResult(success=True, sid=call.sid)
    except Exception as exc:
        logger.error("TwilioClient: voice call failed to=%s: %s", to, exc)
        return TwilioResult(success=False, error=str(exc))


def is_configured() -> bool:
    """Return True if Twilio credentials are present in environment."""
    return bool(
        os.getenv("TWILIO_ACCOUNT_SID") and
        os.getenv("TWILIO_AUTH_TOKEN") and
        os.getenv("TWILIO_FROM_NUMBER")
    )
