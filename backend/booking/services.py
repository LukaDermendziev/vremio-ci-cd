import re
from decimal import Decimal
from datetime import datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db.models import Sum
from django.utils import timezone

from .models import Booking, BookingPolicy, DateWorkingHoursOverride, WorkingHours


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

    if message_type == "approved":
        return (
            f"Здраво {first_name}, вашиот термин за {date_label} во {time_label} "
            f"е потврден. Ве очекуваме! — {salon_name}"
        )
    if message_type in {"rejected", "cancelled"}:
        return (
            f"Здраво {first_name}, за жал терминот за {date_label} во {time_label} "
            f"не е достапен. Ве молиме изберете друг термин. — {salon_name}"
        )
    if message_type == "pending":
        return (
            f"Здраво {first_name}, вашето барање за термин на {date_label} во {time_label} "
            f"е примено. Ќе ве контактираме наскоро. — {salon_name}"
        )
    return (
        f"Здраво {first_name}, ве потсетуваме дека имате термин на {date_label} "
        f"во {time_label}. Ве очекуваме! — {salon_name}"
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
