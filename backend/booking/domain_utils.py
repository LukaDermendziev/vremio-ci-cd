"""Helpers for salon-branded customer domains (e.g. www.fancyfingers.mk)."""

from django.conf import settings


def _normalize_host(host):
    host = (host or "").split(",")[0]
    return host.split(":")[0].lower().strip()


def get_customer_hosts():
    return {_normalize_host(h) for h in getattr(settings, "CUSTOMER_DOMAINS", []) if h}


def request_host(request):
    """Host header without triggering DisallowedHost (safe in early middleware)."""
    forwarded = request.META.get("HTTP_X_FORWARDED_HOST", "")
    return _normalize_host(forwarded or request.META.get("HTTP_HOST", ""))


def _host_aliases(host):
    if not host:
        return set()
    bare = host[4:] if host.startswith("www.") else host
    return {host, bare, f"www.{bare}"}


def is_customer_domain(request):
    hosts = get_customer_hosts()
    if not hosts:
        return False
    return bool(_host_aliases(request_host(request)) & hosts)
