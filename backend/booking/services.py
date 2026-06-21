import logging
import re
from decimal import Decimal
from datetime import datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Booking, BookingActivityLog, BookingPolicy, DateWorkingHoursOverride, WorkingHours

logger = logging.getLogger(__name__)


DEFAULT_START_TIME = time(8, 0)
DEFAULT_END_TIME = time(18, 0)


def get_available_slots(
    salon,
    service,
    selected_date,
    now=None,
    *,
    for_owner=False,
    exclude_booking_id=None,
):
    if now is None:
        now = timezone.now()

    if not service or service.salon_id != salon.id:
        return []

    if not for_owner and not is_date_allowed(salon, selected_date, now=now):
        return []

    working_interval = get_working_interval_for_date(salon, selected_date)
    if not working_interval:
        return []

    working_start, working_end = working_interval
    service_duration = timedelta(minutes=service.duration_minutes)
    slot_interval = timedelta(minutes=get_policy_value(salon, "slot_interval_minutes", 30))
    if slot_interval.total_seconds() <= 0:
        slot_interval = timedelta(minutes=30)

    busy_intervals = get_busy_intervals_for_date(
        salon,
        selected_date,
        exclude_booking_id=exclude_booking_id,
    )
    candidates = generate_candidate_slots(
        working_start=working_start,
        working_end=working_end,
        duration=service_duration,
        slot_interval=slot_interval,
    )

    slots = []
    for candidate_start, candidate_end in candidates:
        if candidate_start < now:
            continue

        if any(
            intervals_overlap(busy_start, busy_end, candidate_start, candidate_end)
            for busy_start, busy_end in busy_intervals
        ):
            continue

        slots.append(
            {
                "start": candidate_start,
                "end": candidate_end,
                "value": candidate_start.strftime("%H:%M"),
                "label": f"{candidate_start:%H:%M} - {candidate_end:%H:%M}",
            }
        )

    return slots


def calculate_available_slots(salon, service, selected_date, now=None):
    return get_available_slots(salon, service, selected_date, now=now)


def get_policy_value(salon, field_name, default):
    try:
        policy = salon.booking_policy
    except BookingPolicy.DoesNotExist:
        return default

    return getattr(policy, field_name, default)


def get_salon_timezone(salon):
    try:
        return ZoneInfo(salon.timezone)
    except ZoneInfoNotFoundError:
        return timezone.get_current_timezone()


def is_date_allowed(salon, selected_date, now=None):
    if now is None:
        now = timezone.now()

    today = timezone.localdate(now, get_salon_timezone(salon))
    minimum_notice_days = get_policy_value(salon, "minimum_notice_days", 14)
    maximum_booking_window_days = get_policy_value(salon, "maximum_booking_window_days", 60)
    allow_same_day_booking = get_policy_value(salon, "allow_same_day_booking", False)
    allow_next_day_booking = get_policy_value(salon, "allow_next_day_booking", False)

    if selected_date < today:
        return False

    if selected_date == today and not allow_same_day_booking:
        return False

    if selected_date == today + timedelta(days=1) and not allow_next_day_booking:
        return False

    if selected_date < today + timedelta(days=minimum_notice_days):
        return False

    if selected_date > today + timedelta(days=maximum_booking_window_days):
        return False

    return True


def get_working_interval_for_date(salon, selected_date):
    working_window = get_working_window_for_date(salon, selected_date)
    if not working_window:
        return None

    start_time, end_time = working_window
    if not start_time or not end_time or end_time <= start_time:
        return None

    salon_tz = get_salon_timezone(salon)
    return (
        timezone.make_aware(datetime.combine(selected_date, start_time), salon_tz),
        timezone.make_aware(datetime.combine(selected_date, end_time), salon_tz),
    )


def get_working_window_for_date(salon, selected_date):
    override = salon.date_working_hours_overrides.filter(date=selected_date).first()

    if override:
        if override.mode == DateWorkingHoursOverride.Mode.CLOSED:
            return None
        if override.mode == DateWorkingHoursOverride.Mode.CUSTOM_HOURS:
            return override.custom_start_time, override.custom_end_time

    working_hours = salon.working_hours.filter(weekday=selected_date.weekday()).first()
    if working_hours:
        if not working_hours.is_working_day:
            return None
        return working_hours.start_time, working_hours.end_time

    if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
        return None

    return DEFAULT_START_TIME, DEFAULT_END_TIME


def get_busy_intervals_for_date(salon, selected_date, exclude_booking_id=None):
    working_interval = get_working_interval_for_date(salon, selected_date)
    if not working_interval:
        return []

    day_start, day_end = working_interval
    buffer = timedelta(minutes=get_policy_value(salon, "buffer_minutes_between_bookings", 0))
    status_values = [Booking.Status.APPROVED]
    if get_policy_value(salon, "pending_holds_slot", True):
        status_values.append(Booking.Status.PENDING)

    busy_intervals = []
    bookings = salon.bookings.filter(
        status__in=status_values,
        start_at__lt=day_end,
        end_at__gt=day_start,
    )
    if exclude_booking_id:
        bookings = bookings.exclude(pk=exclude_booking_id)
    for booking in bookings:
        busy_intervals.append((booking.start_at - buffer, booking.end_at + buffer))

    salon_tz = get_salon_timezone(salon)
    blocks = salon.unavailable_time_blocks.filter(date=selected_date)
    for block in blocks:
        busy_intervals.append(
            (
                timezone.make_aware(datetime.combine(block.date, block.start_time), salon_tz),
                timezone.make_aware(datetime.combine(block.date, block.end_time), salon_tz),
            )
        )

    return busy_intervals


def intervals_overlap(existing_start, existing_end, new_start, new_end):
    return existing_start < new_end and new_start < existing_end


def round_to_next_slot(value, slot_interval, base=None):
    if base is None:
        base = value.replace(hour=0, minute=0, second=0, microsecond=0)

    elapsed = value - base
    remainder = elapsed % slot_interval
    if not remainder:
        return value

    return value + (slot_interval - remainder)


def generate_candidate_slots(working_start, working_end, duration, slot_interval):
    candidate_start = round_to_next_slot(
        working_start,
        slot_interval,
        base=working_start,
    )

    while candidate_start + duration <= working_end:
        candidate_end = candidate_start + duration
        yield candidate_start, candidate_end
        candidate_start += slot_interval


def is_slot_available(
    salon,
    service,
    selected_date,
    start_time_value,
    *,
    for_owner=False,
    exclude_booking_id=None,
):
    slots = get_available_slots(
        salon,
        service,
        selected_date,
        for_owner=for_owner,
        exclude_booking_id=exclude_booking_id,
    )
    return next((slot for slot in slots if slot["value"] == start_time_value), None)


def ensure_default_working_hours(salon):
    for weekday in range(7):
        WorkingHours.objects.get_or_create(
            salon=salon,
            weekday=weekday,
            defaults={
                "is_working_day": weekday != WorkingHours.Weekday.SUNDAY,
                "start_time": DEFAULT_START_TIME,
                "end_time": DEFAULT_END_TIME,
            },
        )


def get_revenue_stats(salon):
    completed = salon.bookings.filter(status=Booking.Status.COMPLETED)
    total = completed.aggregate(total=Sum("booking_services__price_snapshot"))["total"]
    total_revenue = total or Decimal("0")

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    weekly = completed.filter(
        start_at__date__gte=week_start,
        start_at__date__lte=week_end,
    ).aggregate(total=Sum("booking_services__price_snapshot"))["total"]
    weekly_revenue = weekly or Decimal("0")

    return {
        "total_revenue": total_revenue,
        "weekly_revenue": weekly_revenue,
        "week_start": week_start,
        "week_end": week_end,
    }


def normalize_phone_for_links(phone_number):
    digits = re.sub(r"\D", "", phone_number or "")
    if not digits:
        return ""

    if digits.startswith("389"):
        return digits
    if digits.startswith("0"):
        return "389" + digits[1:]
    return "389" + digits


def build_prepared_message(booking, message_type):
    first_name = booking.customer.full_name.split()[0]
    date_label = timezone.localtime(booking.start_at).strftime("%d %B %Y").lstrip("0")
    time_label = timezone.localtime(booking.start_at).strftime("%H:%M")
    salon_name = booking.salon.name

    vars_ = {"ime": first_name, "datum": date_label, "vreme": time_label, "salon": salon_name}

    # Try custom template from BookingPolicy first
    try:
        policy = booking.salon.booking_policy
        field_map = {
            "approved":  "msg_approved",
            "rejected":  "msg_rejected",
            "cancelled": "msg_cancelled",
            "edited":    "msg_edited",
            "no_show":   "msg_no_show",
            "pending":   "msg_pending",
            "reminder":  "msg_reminder",
        }
        field = field_map.get(message_type)
        if field:
            template = getattr(policy, field, "").strip()
            if template:
                return template.format(**vars_)
    except Exception:
        pass  # no policy configured — fall through to hardcoded defaults

    # Hardcoded fallbacks (translated via locale; policy templates stay as stored)
    if message_type == "approved":
        return _(
            "Hello %(name)s, your appointment on %(date)s at %(time)s has been confirmed. "
            "We look forward to seeing you! — %(salon)s"
        ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}
    if message_type == "rejected":
        return _(
            "Hello %(name)s, unfortunately the appointment on %(date)s at %(time)s is not available. "
            "Please choose another time. — %(salon)s"
        ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}
    if message_type == "cancelled":
        return _(
            "Hello %(name)s, your appointment on %(date)s at %(time)s has been cancelled. "
            "Thank you for your understanding. — %(salon)s"
        ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}
    if message_type == "edited":
        return _(
            "Hello %(name)s, your appointment has been changed to %(date)s at %(time)s. "
            "We look forward to seeing you! — %(salon)s"
        ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}
    if message_type == "no_show":
        return _(
            "Hello %(name)s, you did not attend your appointment on %(date)s at %(time)s. "
            "If you would like to book again, please contact us. — %(salon)s"
        ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}
    if message_type == "pending":
        return _(
            "Hello %(name)s, your appointment request for %(date)s at %(time)s has been received. "
            "We will contact you soon. — %(salon)s"
        ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}
    return _(
        "Hello %(name)s, this is a reminder that you have an appointment on %(date)s at %(time)s. "
        "We look forward to seeing you! — %(salon)s"
    ) % {"name": first_name, "date": date_label, "time": time_label, "salon": salon_name}


def send_booking_notification(booking, action, request=None):
    """
    Send an email to the customer if they have one.
    Returns (sent: bool, reason: str).
    """
    email = booking.customer.email
    if not email:
        return False, "no_email"

    subject_map = {
        "approved": _("Your appointment is confirmed — %(salon)s") % {"salon": booking.salon.name},
        "rejected": _("Unfortunately the appointment is unavailable — %(salon)s") % {"salon": booking.salon.name},
        "cancelled": _("Your appointment was cancelled — %(salon)s") % {"salon": booking.salon.name},
        "edited": _("Your appointment was changed — %(salon)s") % {"salon": booking.salon.name},
        "no_show": _("Missed appointment — %(salon)s") % {"salon": booking.salon.name},
        "pending": _("Request received — %(salon)s") % {"salon": booking.salon.name},
    }
    subject = subject_map.get(
        action,
        _("Appointment information — %(salon)s") % {"salon": booking.salon.name},
    )
    body = build_prepared_message(booking, action)

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@salonscheduler.app"),
            recipient_list=[email],
            fail_silently=False,
        )
        return True, "sent"
    except Exception as exc:
        logger.warning("Could not send booking email to %s: %s", email, exc)
        return False, "error"


def send_owner_new_booking_notification(booking):
    """
    Notify the salon owner when a new online booking request arrives.
    Returns (sent: bool, reason: str). Never raises — booking must always succeed.
    """
    owner = booking.salon.owner
    owner_email = (owner.email or "").strip()
    if not owner_email:
        return False, "no_email"

    local_start = timezone.localtime(booking.start_at)
    services = ", ".join(
        item.service_name_snapshot for item in booking.booking_services.all()
    )
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    dashboard_hint = f"{site_url}/owner/dashboard/" if site_url else "/owner/dashboard/"

    subject = _("New booking request — %(salon)s") % {"salon": booking.salon.name}
    body = _(
        "A new booking request was submitted.\n\n"
        "Customer: %(customer)s\n"
        "Phone: %(phone)s\n"
        "Instagram: %(instagram)s\n"
        "Service: %(service)s\n"
        "Date: %(date)s\n"
        "Time: %(time)s\n"
        "Status: Pending (awaiting your approval)\n\n"
        "Review in dashboard: %(dashboard)s\n"
    ) % {
        "customer": booking.customer.full_name,
        "phone": booking.customer.phone_number,
        "instagram": booking.customer.instagram_username or "—",
        "service": services or "—",
        "date": local_start.strftime("%d/%m/%Y"),
        "time": local_start.strftime("%H:%M"),
        "dashboard": dashboard_hint,
    }

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@salonscheduler.app"),
            recipient_list=[owner_email],
            fail_silently=False,
        )
        return True, "sent"
    except Exception as exc:
        logger.warning("Could not send owner notification to %s: %s", owner_email, exc)
        return False, "error"


def log_booking_activity(booking, action, user=None, note=""):
    """Create a BookingActivityLog entry for a booking action."""
    BookingActivityLog.objects.create(
        booking=booking,
        action=action,
        performed_by=user,
        note=note,
    )


def build_contact_links(phone_number, message):
    digits = normalize_phone_for_links(phone_number)
    encoded_message = quote(message)
    links = {
        "tel": f"tel:{phone_number}",
        "sms": f"sms:+{digits}?body={encoded_message}" if digits else "",
        "viber": (
            f"viber://chat?number=%2B{digits}&text={encoded_message}" if digits else ""
        ),
        "whatsapp": f"https://wa.me/{digits}?text={encoded_message}" if digits else "",
    }
    return links


def get_booking_total_price(booking):
    return sum(
        (item.price_snapshot for item in booking.booking_services.all()),
        Decimal("0"),
    )
