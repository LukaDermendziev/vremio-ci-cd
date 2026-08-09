"""Validate North Macedonian mobile phone numbers.

Accepted inputs (separators like spaces, dashes, dots and parentheses are ignored):

* National form: ``07XXXXXXX`` — starts with ``07`` and is exactly 9 digits.
* International form: ``+3897XXXXXXX`` / ``3897XXXXXXX`` / ``003897XXXXXXX`` —
  the ``389`` country code followed by ``7`` + 7 digits (i.e. the same number
  as the national ``07...`` form without the trunk ``0``).

All accepted inputs normalize to the canonical national form ``07XXXXXXX``.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .anti_abuse import normalize_phone

# Canonical MK mobile: 07 followed by exactly 7 more digits (9 digits total).
MK_MOBILE_RE = re.compile(r"^07\d{7}$")


def is_valid_mk_mobile(value: str) -> bool:
    """Return True when ``value`` is a recognisable MK mobile number."""
    return bool(MK_MOBILE_RE.match(normalize_phone(value or "")))


def validate_mk_mobile_number(value: str) -> str:
    """Validate and normalize an MK mobile number.

    Returns the canonical national form (``07XXXXXXX``). Empty input is passed
    through unchanged so that "required" enforcement stays with the form field.
    Raises ``ValidationError`` for anything that is not a valid MK mobile.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    normalized = normalize_phone(raw)
    if not MK_MOBILE_RE.match(normalized):
        raise ValidationError(
            _(
                "Enter a valid Macedonian mobile number, for example "
                "070 123 456 or +389 70 123 456."
            ),
            code="invalid_mk_mobile",
        )
    return normalized
