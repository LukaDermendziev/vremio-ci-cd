"""Catch common email domain typos (e.g. gmai.com → gmail.com)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Domains we trust as correct — never flag these.
COMMON_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "mail.com",
        "protonmail.com",
        "proton.me",
        "aol.com",
        "gmx.com",
        "gmx.de",
        "yandex.com",
        "yandex.ru",
        "zoho.com",
        "tutanota.com",
        "fastmail.com",
        # Local / regional
        "t.mk",
        "telekom.mk",
        "mt.net.mk",
        "unet.com.mk",
        "mail.mk",
    }
)

# Exact typos seen in the wild (and close cousins).
TYPO_DOMAIN_MAP = {
    # Gmail
    "gmai.com": "gmail.com",
    "gmil.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gnail.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmail.con": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.cm": "gmail.com",
    "gmail.om": "gmail.com",
    "gmail.cpm": "gmail.com",
    "gmail.comm": "gmail.com",
    "gmail.coml": "gmail.com",
    "gmail.coma": "gmail.com",
    "gmaul.com": "gmail.com",
    "gmeil.com": "gmail.com",
    "gmsil.com": "gmail.com",
    "gmai.lcom": "gmail.com",
    "gmail.cok": "gmail.com",
    "gmailcom": "gmail.com",
    "googlemail.co": "googlemail.com",
    "googlemail.con": "googlemail.com",
    # Yahoo
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yhaoo.com": "yahoo.com",
    "yaoo.com": "yahoo.com",
    "yahoo.con": "yahoo.com",
    "yahoo.co": "yahoo.com",
    "yahoo.cm": "yahoo.com",
    # Hotmail / Outlook / Live
    "hotmial.com": "hotmail.com",
    "hotnail.com": "hotmail.com",
    "hotmai.com": "hotmail.com",
    "hotmail.con": "hotmail.com",
    "hotmail.co": "hotmail.com",
    "outlok.com": "outlook.com",
    "outloo.com": "outlook.com",
    "outlook.con": "outlook.com",
    "outlook.co": "outlook.com",
    "live.con": "live.com",
    # iCloud
    "icloud.con": "icloud.com",
    "icoud.com": "icloud.com",
}


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            insert = curr[j - 1] + 1
            delete = prev[j] + 1
            replace = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(insert, delete, replace))
        prev = curr
    return prev[-1]


def suggest_email_correction(email: str) -> str | None:
    """
    If the domain looks like a common typo, return the corrected full address.
    Returns None when the email looks fine or cannot be safely corrected.
    """
    value = (email or "").strip().lower()
    if "@" not in value:
        return None
    local, _, domain = value.rpartition("@")
    local = local.strip()
    domain = domain.strip().rstrip(".")
    if not local or not domain or " " in domain:
        return None
    if domain in COMMON_EMAIL_DOMAINS:
        return None
    if domain in TYPO_DOMAIN_MAP:
        return f"{local}@{TYPO_DOMAIN_MAP[domain]}"

    # Fuzzy match against popular domains (distance 1, or 2 for longer domains).
    best_domain = None
    best_distance = 99
    for known in COMMON_EMAIL_DOMAINS:
        if abs(len(known) - len(domain)) > 2:
            continue
        distance = _levenshtein(domain, known)
        if distance < best_distance:
            best_distance = distance
            best_domain = known

    if best_domain is None:
        return None
    if best_distance == 1:
        return f"{local}@{best_domain}"
    if best_distance == 2 and len(domain) >= 6:
        return f"{local}@{best_domain}"
    return None


def validate_email_no_common_typos(email: str) -> str:
    """
    Normalize and reject emails with common domain typos.
    Empty string is allowed (caller decides required/optional).
    """
    value = (email or "").strip()
    if not value:
        return ""
    suggestion = suggest_email_correction(value)
    if suggestion:
        raise ValidationError(
            _("Did you mean %(suggestion)s? Please check your email address."),
            code="email_typo",
            params={"suggestion": suggestion},
        )
    return value
