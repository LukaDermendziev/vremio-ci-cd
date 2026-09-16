from django.conf import settings


def get_vremio_contact_email():
    return (
        getattr(settings, "VREMIO_CONTACT_EMAIL", "").strip()
        or getattr(settings, "OWNER_NOTIFICATION_EMAIL", "").strip()
        or ""
    )
