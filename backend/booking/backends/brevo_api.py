"""Brevo (Sendinblue) transactional email via HTTPS API.

Railway Hobby/Free blocks outbound SMTP (ports 587/465). This backend uses
Brevo's REST API on port 443, which works on all Railway plans.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("booking.email")

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _address_dict(value: str) -> dict:
    name, email = parseaddr(value or "")
    payload = {"email": email}
    if name:
        payload["name"] = name
    return payload


class BrevoAPIEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = getattr(settings, "BREVO_API_KEY", "").strip()
        self.timeout = int(getattr(settings, "EMAIL_TIMEOUT", 15))

    def send_messages(self, email_messages):
        if not self.api_key:
            if not self.fail_silently:
                raise ValueError("BREVO_API_KEY is not configured")
            logger.error("BREVO_API_KEY is not configured; cannot send email")
            return 0

        sent = 0
        for message in email_messages:
            try:
                if self._send(message):
                    sent += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception("Brevo API email failed")
        return sent

    def _send(self, message) -> bool:
        recipients = [addr for addr in message.recipients() if addr]
        if not recipients:
            return False

        sender = _address_dict(message.from_email or settings.DEFAULT_FROM_EMAIL)
        if not sender.get("email"):
            logger.error("Brevo email skipped: missing sender address")
            return False

        html_body = None
        for content, mimetype in getattr(message, "alternatives", []) or []:
            if mimetype == "text/html":
                html_body = content
                break

        payload = {
            "sender": sender,
            "to": [_address_dict(addr) for addr in recipients],
            "subject": message.subject or "",
            "textContent": message.body or "",
        }
        if html_body:
            payload["htmlContent"] = html_body

        reply_to = [addr for addr in (message.reply_to or []) if addr]
        if reply_to:
            payload["replyTo"] = _address_dict(reply_to[0])

        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            BREVO_API_URL,
            data=body,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if 200 <= response.status < 300:
                    logger.info(
                        "Brevo API email sent to %s — subject: %s",
                        ", ".join(recipients),
                        message.subject,
                    )
                    return True
                raw = response.read().decode("utf-8", errors="replace")
                logger.warning(
                    "Brevo API unexpected status %s for %s: %s",
                    response.status,
                    recipients,
                    raw,
                )
                return False
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "Brevo API HTTP %s for %s: %s",
                exc.code,
                recipients,
                raw,
            )
            if not self.fail_silently:
                raise
            return False
        except urllib.error.URLError as exc:
            logger.warning("Brevo API connection error for %s: %s", recipients, exc.reason)
            if not self.fail_silently:
                raise
            return False
