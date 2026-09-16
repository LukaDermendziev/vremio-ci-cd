"""Helpers for linking a salon location in external maps apps."""

from urllib.parse import quote_plus, urlparse


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def salon_location_label(salon) -> str:
    """Human-readable address line from salon profile fields."""
    parts = []
    address = (getattr(salon, "address", None) or "").strip()
    city = (getattr(salon, "city", None) or "").strip()
    if address:
        parts.append(address)
    if city and city not in address:
        parts.append(city)
    if parts:
        return ", ".join(parts)
    # Maps link only — still show a short label on the public page.
    if (getattr(salon, "maps_url", None) or "").strip():
        return city or (getattr(salon, "name", None) or "").strip()
    return ""


def salon_maps_search_url(salon) -> str:
    """External maps URL: prefer a pasted Maps link, else search by address."""
    direct = (getattr(salon, "maps_url", None) or "").strip()
    if direct and _is_http_url(direct):
        return direct

    label_parts = []
    address = (getattr(salon, "address", None) or "").strip()
    city = (getattr(salon, "city", None) or "").strip()
    if address:
        label_parts.append(address)
    if city and city not in address:
        label_parts.append(city)
    label = ", ".join(label_parts)
    if not label:
        return ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(label)}"
