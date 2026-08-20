"""Booking app middleware."""

from django.conf import settings
from django.utils import translation

from .domain_utils import is_customer_domain


class DefaultMacedonianLocaleMiddleware:
    """
    Keep LANGUAGE_CODE (mk) for first-time visitors.

    Django's LocaleMiddleware falls back to the browser Accept-Language header
    when no language cookie/session exists. For this salon product, Macedonian
    is the default UI; English is opt-in via the language switcher only.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_name = settings.LANGUAGE_COOKIE_NAME
        if cookie_name not in request.COOKIES:
            translation.activate(settings.LANGUAGE_CODE)
            request.LANGUAGE_CODE = settings.LANGUAGE_CODE

        response = self.get_response(request)
        return response


class CustomerDomainMiddleware:
    """
    On salon-branded domains, map / to the salon page without a browser redirect.

    Rewrites the path internally so later middleware (locale default, CSRF, etc.)
    still runs. The address bar stays https://www.example.mk/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            is_customer_domain(request)
            and request.path == "/"
            and settings.CUSTOMER_DOMAIN_SALON_SLUG
        ):
            salon_path = f"/book/{settings.CUSTOMER_DOMAIN_SALON_SLUG}/"
            request.path = salon_path
            request.path_info = salon_path
        return self.get_response(request)


class NeverCacheOwnerMiddleware:
    """Prevent browsers from caching owner pages (back button after logout)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/owner/") and not request.path.rstrip("/").endswith("/photo"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response


# Baseline CSP for the current stack (same-origin assets + Google Fonts + jsDelivr
# CSS/icons). 'unsafe-inline' is required while templates still use inline <script>
# and style="" attributes; tighten later with nonces if needed.
DEFAULT_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net; "
    "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net https://*.ingest.sentry.io https://*.ingest.de.sentry.io"
)


# Disables powerful browser features we do not use (camera is allowed only if a
# future flow needs it — keep locked down for now).
DEFAULT_PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()"
)


class ContentSecurityPolicyMiddleware:
    """Attach CSP and related browser security headers when enabled."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "CONTENT_SECURITY_POLICY_ENABLED", False):
            return response
        # Django admin is staff-only and ships its own assets; skip CSP there.
        if request.path.startswith("/admin/"):
            return response
        # Do not override a view that already set CSP.
        if "Content-Security-Policy" not in response:
            policy = getattr(
                settings, "CONTENT_SECURITY_POLICY", DEFAULT_CONTENT_SECURITY_POLICY
            )
            if policy:
                response["Content-Security-Policy"] = policy
        if "Permissions-Policy" not in response:
            permissions = getattr(
                settings, "PERMISSIONS_POLICY", DEFAULT_PERMISSIONS_POLICY
            )
            if permissions:
                response["Permissions-Policy"] = permissions
        return response
