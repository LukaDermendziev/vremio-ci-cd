"""Owner login brute-force protection via cache (Redis in production)."""

from __future__ import annotations

import hashlib
import logging
import re

from django.core.cache import cache
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)

# Keep limits modest for a single-owner pilot: enough to stop password spraying,
# low enough that a forgotten password does not lock someone out for hours.
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60  # 15 minutes

MSG_LOGIN_LOCKED = _(
    "Too many failed sign-in attempts. Please wait a few minutes and try again."
)


def _safe_cache_get(key, default=0):
    try:
        return cache.get(key, default)
    except Exception:
        logger.warning("Cache read failed for %s; allowing login attempt", key, exc_info=True)
        return default


def _safe_cache_incr(key, timeout):
    """Increment a counter; create it if missing. Returns new value or None on failure."""
    try:
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout)
            return 1
    except Exception:
        logger.warning("Cache write failed for %s; allowing login attempt", key, exc_info=True)
        return None


def _safe_cache_delete(*keys):
    for key in keys:
        try:
            cache.delete(key)
        except Exception:
            logger.warning("Cache delete failed for %s", key, exc_info=True)


def _normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def _username_key_part(username: str) -> str:
    """Hash usernames so cache keys stay short and do not store raw handles."""
    normalized = _normalize_username(username)
    if not normalized:
        return "empty"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _ip_key_part(ip: str) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F:.\-]", "", (ip or "").strip()) or "unknown"
    return cleaned[:64]


def _keys(ip: str, username: str) -> tuple[str, str]:
    return (
        f"login_fail:ip:{_ip_key_part(ip)}",
        f"login_fail:user:{_username_key_part(username)}",
    )


def is_login_locked(ip: str, username: str) -> bool:
    """True when IP or username has exceeded failed-attempt limits."""
    ip_key, user_key = _keys(ip, username)
    ip_count = int(_safe_cache_get(ip_key, 0) or 0)
    user_count = int(_safe_cache_get(user_key, 0) or 0)
    return ip_count >= LOGIN_MAX_ATTEMPTS or user_count >= LOGIN_MAX_ATTEMPTS


def record_login_failure(ip: str, username: str) -> None:
    ip_key, user_key = _keys(ip, username)
    _safe_cache_incr(ip_key, LOGIN_WINDOW_SECONDS)
    if _normalize_username(username):
        _safe_cache_incr(user_key, LOGIN_WINDOW_SECONDS)


def clear_login_failures(ip: str, username: str) -> None:
    ip_key, user_key = _keys(ip, username)
    _safe_cache_delete(ip_key, user_key)
