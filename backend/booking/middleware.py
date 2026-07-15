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

        response = self.get_response(request)
        return response


class CustomerDomainMiddleware:
    """
    On salon-branded domains, serve the salon page at / (URL stays clean).

    Example: www.fancyfingers.mk/ shows Fancy Fingers without redirecting to
    /book/fancy-fingers/. The Vremio platform stays on *.up.railway.app.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            is_customer_domain(request)
            and request.path == "/"
            and settings.CUSTOMER_DOMAIN_SALON_SLUG
        ):
            from .views import salon_page

            return salon_page(request, settings.CUSTOMER_DOMAIN_SALON_SLUG)
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
