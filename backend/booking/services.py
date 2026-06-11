from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

from .models import Booking, BookingPolicy, DateWorkingHoursOverride, WorkingHours


DEFAULT_START_TIME = time(8, 0)
DEFAULT_END_TIME = time(18, 0)


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


def calculate_available_slots(salon, service, selected_date, now=None):
    if now is None:
        now = timezone.now()

    if not service or service.salon_id != salon.id:
        return []

    if not is_date_allowed(salon, selected_date, now=now):
        return []

    working_window = get_working_window_for_date(salon, selected_date)
    if not working_window:
        return []

    start_time, end_time = working_window
    if not start_time or not end_time or end_time <= start_time:
        return []

    salon_tz = get_salon_timezone(salon)
    day_start = timezone.make_aware(datetime.combine(selected_date, start_time), salon_tz)
    day_end = timezone.make_aware(datetime.combine(selected_date, end_time), salon_tz)
    duration = timedelta(minutes=service.duration_minutes)
    slot_interval = timedelta(
        minutes=get_policy_value(salon, "slot_interval_minutes", 30)
    )
    buffer = timedelta(
        minutes=get_policy_value(salon, "buffer_minutes_between_bookings", 0)
    )

    if slot_interval.total_seconds() <= 0:
        slot_interval = timedelta(minutes=30)

    occupied_intervals = _get_occupied_intervals(salon, day_start, day_end, buffer)
    slots = []
    candidate_start = day_start

    while candidate_start + duration <= day_end:
        candidate_end = candidate_start + duration

        if candidate_start >= now and not _overlaps_any(
            candidate_start,
            candidate_end,
            occupied_intervals,
        ):
            slots.append(
                {
                    "start": candidate_start,
                    "end": candidate_end,
                    "value": candidate_start.strftime("%H:%M"),
                    "label": (
                        f"{candidate_start:%H:%M}-{candidate_end:%H:%M}"
                    ),
                }
            )

        candidate_start += slot_interval

    return slots


def is_slot_available(salon, service, selected_date, start_time_value):
    slots = calculate_available_slots(salon, service, selected_date)
    return next((slot for slot in slots if slot["value"] == start_time_value), None)


def _get_occupied_intervals(salon, day_start, day_end, buffer):
    status_values = [Booking.Status.APPROVED]
    if get_policy_value(salon, "pending_holds_slot", True):
        status_values.append(Booking.Status.PENDING)

    occupied_intervals = []

    bookings = salon.bookings.filter(
        status__in=status_values,
        start_at__lt=day_end,
        end_at__gt=day_start,
    )
    for booking in bookings:
        occupied_intervals.append((booking.start_at - buffer, booking.end_at + buffer))

    blocks = salon.unavailable_time_blocks.filter(date=day_start.date())
    salon_tz = get_salon_timezone(salon)
    for block in blocks:
        block_start = timezone.make_aware(
            datetime.combine(block.date, block.start_time),
            salon_tz,
        )
        block_end = timezone.make_aware(
            datetime.combine(block.date, block.end_time),
            salon_tz,
        )
        occupied_intervals.append((block_start, block_end))

    return occupied_intervals


def _overlaps_any(candidate_start, candidate_end, occupied_intervals):
    return any(
        occupied_start < candidate_end and candidate_start < occupied_end
        for occupied_start, occupied_end in occupied_intervals
    )
