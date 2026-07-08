"""Brevo transactional SMS for OTP verification and booking notifications."""
from __future__ import annotations

import json
import logging
import re
import secrets
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils.translation import gettext as _

logger = logging.getLogger("booking.sms")

BREVO_SMS_API_URL = "https://api.brevo.com/v3/transactionalSMS/send"

ACTION_TO_MESSAGE_TYPE = {
    "approved": "approved",
    "rejected": "rejected",
    "cancelled": "cancelled",
    "edited": "edited",
    "no_show": "no_show",
    "pending": "pending",
    "request_received": "pending",
    "customer_cancelled": "cancelled",
    "reminder": "reminder",
}


def format_phone_for_brevo(phone: str) -> str:
    """Return digits with country code for Brevo (e.g. 38970123456)."""
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("389"):
        return digits
    if digits.startswith("0") and len(digits) >= 9:
        return "389" + digits[1:]
    if len(digits) == 8 and digits[0] in "78":
        return "389" + digits
    return digits


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def set_booking_sms_otp(booking, code: str) -> None:
    booking.sms_otp_digest = make_password(code)
    booking.save(update_fields=["sms_otp_digest"])


def verify_booking_sms_otp(booking, code: str) -> bool:
    digest = (booking.sms_otp_digest or "").strip()
    if not digest:
        return False
    normalized = re.sub(r"\D", "", code or "")
    if len(normalized) != 6:
        return False
    return check_password(normalized, digest)


def send_brevo_transactional_sms(recipient: str, content: str, *, tag: str = "") -> tuple[bool, str]:
    api_key = getattr(settings, "BREVO_API_KEY", "").strip()
    sender = getattr(settings, "BREVO_SMS_SENDER", "").strip()
    if not api_key:
        logger.error("BREVO_API_KEY is not configured; cannot send SMS")
        return False, "no_api_key"
    if not sender:
        logger.error("BREVO_SMS_SENDER is not configured; cannot send SMS")
        return False, "no_sender"

    phone = format_phone_for_brevo(recipient)
    if not phone:
        return False, "invalid_phone"

    payload = {
        "sender": sender[:11],
        "recipient": phone,
        "content": content,
        "type": "transactional",
    }
    if tag:
        payload["tag"] = tag[:50]

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        BREVO_SMS_API_URL,
        data=body,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )
    timeout = int(getattr(settings, "EMAIL_TIMEOUT", 15))

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if 200 <= response.status < 300:
                logger.info("Brevo SMS sent to %s (tag=%s)", phone, tag or "-")
                return True, "sent"
            raw = response.read().decode("utf-8", errors="replace")
            logger.warning("Brevo SMS unexpected status %s for %s: %s", response.status, phone, raw)
            return False, "api_error"
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        logger.warning("Brevo SMS HTTP %s for %s: %s", exc.code, phone, raw)
        return False, "api_error"
    except urllib.error.URLError as exc:
        logger.warning("Brevo SMS connection error for %s: %s", phone, exc.reason)
        return False, "connection_error"


def build_otp_sms_message(booking, code: str, expiration_minutes: int) -> str:
    salon_name = booking.salon.name
    return _(
        "Your verification code for %(salon)s is %(code)s. "
        "Valid for %(minutes)s minutes. Do not share this code."
    ) % {"salon": salon_name, "code": code, "minutes": expiration_minutes}


def send_otp_sms(booking, code: str) -> tuple[bool, str]:
    policy = getattr(booking.salon, "booking_policy", None)
    expiration_minutes = 10
    if policy:
        expiration_minutes = policy.sms_verification_expiration_minutes
    message = build_otp_sms_message(booking, code, expiration_minutes)
    return send_brevo_transactional_sms(
        booking.customer.phone_number,
        message,
        tag="booking_otp",
    )


def send_booking_status_sms(booking, action: str) -> tuple[bool, str]:
    from .services import build_prepared_message

    message_type = ACTION_TO_MESSAGE_TYPE.get(action)
    if not message_type:
        return False, "unknown_action"
    content = build_prepared_message(booking, message_type)
    if not content:
        return False, "empty_message"
    return send_brevo_transactional_sms(
        booking.customer.phone_number,
        content,
        tag=f"booking_{message_type}",
    )
