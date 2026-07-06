"""Helpers for salon-branded customer domains (e.g. www.fancyfingers.mk)."""

from django.conf import settings


def _normalize_host(host):
    return host.split(":")[0].lower().strip()


def get_customer_hosts():
    return {_normalize_host(h) for h in getattr(settings, "CUSTOMER_DOMAINS", [])}


def request_host(request):
    """Host header without triggering DisallowedHost (safe in early middleware)."""
    return _normalize_host(request.META.get("HTTP_HOST", ""))


def is_customer_domain(request):
    hosts = get_customer_hosts()
    if not hosts:
        return False
    return request_host(request) in hosts
