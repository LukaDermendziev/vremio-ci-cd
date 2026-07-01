"""Booking app middleware."""

from django.conf import settings
from django.utils import translation


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


class NeverCacheOwnerMiddleware:
    """Prevent browsers from caching owner pages (back button after logout)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/owner/"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
