from django.conf import settings

from .domain_utils import is_customer_domain
from .legal_utils import get_vremio_contact_email


def language(request):
    from django.utils import translation

    return {
        "CURRENT_LANGUAGE": translation.get_language(),
    }


def vremio(request):
    contact_email = get_vremio_contact_email()
    platform_url = getattr(settings, "PLATFORM_URL", "").rstrip("/") or "/"
    instagram = getattr(settings, "VREMIO_INSTAGRAM", "").strip().lstrip("@")
    return {
        "vremio_contact_email": contact_email,
        "vremio_contact_placeholder": not contact_email,
        "is_customer_domain": is_customer_domain(request),
        "vremio_home_url": platform_url if platform_url != "/" else "/",
        "vremio_instagram": instagram,
        "vremio_instagram_url": f"https://ig.me/m/{instagram}" if instagram else "",
    }
