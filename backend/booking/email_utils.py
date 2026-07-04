"""Outgoing email helpers for booking notifications."""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import escape
from django.utils import timezone
from django.utils import translation
from django.utils.translation import gettext as _

logger = logging.getLogger("booking.email")

# (subject template name, body template name)
CUSTOMER_EMAIL_TEMPLATES = {
    "approved": ("booking/emails/subject_approved.txt", "booking/emails/customer_approved.txt"),
    "rejected": ("booking/emails/subject_rejected.txt", "booking/emails/customer_rejected.txt"),
    "edited": ("booking/emails/subject_edited.txt", "booking/emails/customer_edited.txt"),
    "cancelled": ("booking/emails/subject_cancelled.txt", "booking/emails/customer_cancelled.txt"),
    "no_show": ("booking/emails/subject_no_show.txt", "booking/emails/customer_no_show.txt"),
    "pending": ("booking/emails/subject_pending.txt", "booking/emails/customer_pending.txt"),
}

OWNER_NEW_BOOKING_TEMPLATES = (
    "booking/emails/subject_owner_new_booking.txt",
    "booking/emails/owner_new_booking.txt",
)

REQUEST_RECEIVED_TEMPLATES = (
    "booking/emails/subject_request_received.txt",
    "booking/emails/customer_request_received.txt",
)

VERIFY_BOOKING_TEMPLATES = (
    "booking/emails/subject_verify_booking.txt",
    "booking/emails/customer_verify_booking.txt",
)

CUSTOMER_CANCELLATION_CONFIRMED_TEMPLATES = (
    "booking/emails/subject_customer_cancellation_confirmed.txt",
    "booking/emails/customer_cancellation_confirmed.txt",
)

OWNER_CUSTOMER_CANCELLED_TEMPLATES = (
    "booking/emails/subject_owner_customer_cancelled.txt",
    "booking/emails/owner_customer_cancelled.txt",
)


def get_owner_notification_email(salon):
    """Owner inbox for notifications; falls back to salon owner account email."""
    configured = getattr(settings, "OWNER_NOTIFICATION_EMAIL", "").strip()
    if configured:
        return configured
    owner = salon.owner
    return (owner.email or "").strip()


def get_owner_reply_to(salon):
    """Reply-To for customer-facing booking emails."""
    email = get_owner_notification_email(salon)
    return [email] if email else []


def _booking_email_context(booking):
    from .services import (
        build_service_schedule,
        format_services_for_email,
        format_services_label,
        get_manage_booking_url,
    )

    local_start = timezone.localtime(booking.start_at)
    local_end = timezone.localtime(booking.end_at)
    customer = booking.customer
    first_name = (customer.full_name or "").split()[0] if customer.full_name else customer.full_name
    booking_service_items = list(booking.booking_services.all())
    service_schedule = build_service_schedule(
        booking.start_at, booking_service_items, booking.salon
    )
    services_text = format_services_for_email(booking)
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    return {
        "booking": booking,
        "customer": customer,
        "salon": booking.salon,
        "first_name": first_name,
        "customer_name": customer.full_name,
        "phone": customer.phone_number,
        "instagram": customer.instagram_username or "—",
        "services": services_text or "—",
        "services_label": format_services_label(booking),
        "services_list": service_schedule,
        "service_schedule": service_schedule,
        "total_duration": booking.total_duration_minutes,
        "date": local_start.strftime("%d/%m/%Y"),
        "time": local_start.strftime("%H:%M"),
        "end_time": local_end.strftime("%H:%M"),
        "dashboard_url": f"{site_url}/owner/dashboard/" if site_url else "/owner/dashboard/",
        "manage_url": get_manage_booking_url(booking),
    }


def _render_email_parts(subject_template, body_template, context):
    language = getattr(settings, "LANGUAGE_CODE", "mk")
    with translation.override(language):
        subject = render_to_string(subject_template, context).strip().replace("\n", " ")
        body = render_to_string(body_template, context).strip()
    return subject, body


def _send_email(*, subject, body, to_email, reply_to=None):
    if not to_email:
        return False, "no_email"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@salonscheduler.app")
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to_email],
            reply_to=reply_to or [],
        )
        html_body = escape(body).replace("\n", "<br>\n")
        message.attach_alternative(f"<html><body>{html_body}</body></html>", "text/html")
        message.send(fail_silently=False)
        return True, "sent"
    except Exception as exc:
        logger.warning("Email send failed to %s: %s", to_email, exc)
        return False, "error"


def send_customer_booking_email(booking, action):
    """
    Send a booking notification email to the customer.
    Returns (sent: bool, reason: str) where reason is 'sent', 'no_email', or 'error'.
    """
    email = (booking.customer.email or "").strip()
    if not email:
        return False, "no_email"

    templates = CUSTOMER_EMAIL_TEMPLATES.get(action)
    if not templates:
        return False, "unknown_action"

    context = _booking_email_context(booking)
    subject, body = _render_email_parts(templates[0], templates[1], context)
    return _send_email(
        subject=subject,
        body=body,
        to_email=email,
        reply_to=get_owner_reply_to(booking.salon),
    )


def send_booking_approved_email(booking):
    return send_customer_booking_email(booking, "approved")


def send_booking_rejected_email(booking):
    return send_customer_booking_email(booking, "rejected")


def send_booking_updated_email(booking):
    return send_customer_booking_email(booking, "edited")


def send_booking_cancelled_email(booking):
    return send_customer_booking_email(booking, "cancelled")


def send_owner_new_booking_email(booking):
    """
    Notify the salon owner of a new online booking request.
    Never raises — booking creation must always succeed.
    """
    owner_email = get_owner_notification_email(booking.salon)
    if not owner_email:
        return False, "no_email"

    customer_email = (booking.customer.email or "").strip()
    if customer_email and owner_email.casefold() == customer_email.casefold():
        logger.info(
            "Skipping owner new-booking email for booking %s — owner inbox matches customer email",
            booking.pk,
        )
        return False, "same_as_customer"

    context = _booking_email_context(booking)
    subject, body = _render_email_parts(*OWNER_NEW_BOOKING_TEMPLATES, context)
    return _send_email(subject=subject, body=body, to_email=owner_email)


def send_booking_request_received_email(booking):
    """Send customer confirmation with manage link after online request."""
    return _send_customer_templated_email(booking, REQUEST_RECEIVED_TEMPLATES)


def send_booking_verification_email(booking):
    """Send email verification link before a booking request is submitted."""
    email = (booking.customer.email or "").strip()
    if not email or not booking.email_verification_token:
        return False, "no_email"

    policy = getattr(booking.salon, "booking_policy", None)
    expiration_minutes = 60
    if policy:
        expiration_minutes = policy.email_verification_expiration_minutes

    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    verify_url = (
        f"{site_url}/book/{booking.salon.slug}/verify/{booking.email_verification_token}/"
    )
    context = _booking_email_context(booking)
    context.update({
        "verify_url": verify_url,
        "expiration_minutes": expiration_minutes,
    })
    subject, body = _render_email_parts(*VERIFY_BOOKING_TEMPLATES, context)
    return _send_email(
        subject=subject,
        body=body,
        to_email=email,
        reply_to=get_owner_reply_to(booking.salon),
    )


def send_customer_cancellation_confirmation_email(booking):
    """Confirm to customer that their self-cancellation was recorded."""
    return _send_customer_templated_email(booking, CUSTOMER_CANCELLATION_CONFIRMED_TEMPLATES)


def send_owner_customer_cancelled_email(booking):
    """Notify owner that customer cancelled via manage link."""
    owner_email = get_owner_notification_email(booking.salon)
    if not owner_email:
        return False, "no_email"

    context = _booking_email_context(booking)
    subject, body = _render_email_parts(*OWNER_CUSTOMER_CANCELLED_TEMPLATES, context)
    return _send_email(subject=subject, body=body, to_email=owner_email)


def _send_customer_templated_email(booking, templates):
    email = (booking.customer.email or "").strip()
    if not email:
        return False, "no_email"

    context = _booking_email_context(booking)
    subject, body = _render_email_parts(templates[0], templates[1], context)
    return _send_email(
        subject=subject,
        body=body,
        to_email=email,
        reply_to=get_owner_reply_to(booking.salon),
    )


def send_test_email(recipient):
    """Send a simple test message to verify SMTP/console configuration."""
    language = getattr(settings, "LANGUAGE_CODE", "mk")
    with translation.override(language):
        subject = _("Vremio test email")
        body = _(
            "This is a test email from Vremio.\n\n"
            "If you received this message, outgoing email is configured correctly."
        )
    return _send_email(subject=subject, body=body, to_email=recipient)
