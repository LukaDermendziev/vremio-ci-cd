from .legal_utils import get_vremio_contact_email


def language(request):
    from django.utils import translation

    return {
        "CURRENT_LANGUAGE": translation.get_language(),
    }


def vremio(request):
    contact_email = get_vremio_contact_email()
    return {
        "vremio_contact_email": contact_email,
        "vremio_contact_placeholder": not contact_email,
    }
