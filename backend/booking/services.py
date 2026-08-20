import logging
import re
import threading
from decimal import Decimal
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext as _

from .models import (
    Booking,
    BookingActivityLog,
    BookingPolicy,
    BookingService,
    DateWorkingHoursOverride,
    ReleasedSlot,
    Service,
    WorkingHours,
)

logger = logging.getLogger(__name__)


DEFAULT_START_TIME = time(8, 0)
DEFAULT_END_TIME = time(18, 0)
FIXED_START_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")
DEFAULT_FIXED_START_TIMES = ["08:00", "10:30", "13:00", "15:30"]
# After a visit that opens a real hole, the next extra start is end + this gap
# (sanitize / breath). Anchors still win when the visit ends before the next one.
FIXED_START_PACKING_GAP_MINUTES = 30


MSG_MULTI_SERVICE_NO_FIT = _(
    "There is not enough available time for the selected services together. "
    "Please choose another date or book the services separately."
)


def normalize_services(services):
    if not services:
        return []
    if isinstance(services, Service):
        return [services]
    return list(services)


def parse_service_ids_param(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        parts = value
    else:
        parts = str(value).split(",")
    ids = []
    for part in parts:
        part = str(part).strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def resolve_services_for_salon(salon, service_ids):
    if not service_ids:
        return None
    seen = set()
    ordered_ids = []
    for sid in service_ids:
        if sid not in seen:
            seen.add(sid)
            ordered_ids.append(sid)
    services = list(salon.services.filter(id__in=ordered_ids, is_active=True))
    by_id = {service.id: service for service in services}
    if len(by_id) != len(ordered_ids):
        return None
    return [by_id[sid] for sid in ordered_ids]


def get_service_gap_minutes(salon):
    return get_policy_value(salon, "service_gap_minutes", 30)


def normalize_price_item_selection(value):
    """Normalize one service's price-item selection.

    Accepts legacy ``price_item_id`` or ``{"base": id, "addons": [ids]}``.
    Returns ``(base_id_or_None, [addon_ids])``.
    """
    if value is None or value == "":
        return None, []
    if isinstance(value, dict):
        base_raw = value.get("base", value.get("price_item"))
        addons_raw = value.get("addons") or []
        try:
            base_id = int(base_raw) if base_raw not in (None, "") else None
        except (TypeError, ValueError):
            base_id = None
        addon_ids = []
        if isinstance(addons_raw, (list, tuple)):
            for raw in addons_raw:
                try:
                    addon_ids.append(int(raw))
                except (TypeError, ValueError):
                    continue
        return base_id, addon_ids
    try:
        return int(value), []
    except (TypeError, ValueError):
        return None, []


def line_item_duration_minutes(line):
    """Duration for one service selection (base + add-ons, no inter-service gap)."""
    service = line.get("service")
    price_item = line.get("price_item")
    addons = line.get("addons") or []
    if price_item is not None and getattr(price_item, "duration_minutes", 0):
        total = price_item.duration_minutes
    elif service is not None:
        total = service.duration_minutes
    else:
        total = 0
    for addon in addons:
        # Add-ons never fall back to the full parent service duration.
        total += getattr(addon, "duration_minutes", 0) or 0
    return total


def calculate_combined_duration_minutes(services, salon):
    services = normalize_services(services)
    if not services:
        return 0
    total = sum(service.duration_minutes for service in services)
    if len(services) > 1:
        total += get_service_gap_minutes(salon) * (len(services) - 1)
    return total


def calculate_line_items_duration_minutes(line_items, salon):
    """Total duration for booking lines, honouring sub-service durations and add-ons.

    ``line_items`` is an iterable of dicts like
    ``{"service": Service, "price_item": ServicePriceItem | None, "addons": [...]}``.

    Gap minutes apply between different service lines only — not between a base
    and its add-ons (those are one visit block).
    """
    line_items = list(line_items or [])
    if not line_items:
        return 0
    total = sum(line_item_duration_minutes(line) for line in line_items)
    if len(line_items) > 1:
        total += get_service_gap_minutes(salon) * (len(line_items) - 1)
    return total


def build_service_schedule(start_at, items, salon):
    """Build per-line start/end times for display (emails, manage page, owner UI).

    Add-ons with 0 extra minutes share the previous same-service block's window
    so they are not shown as a second full appointment slot.
    """
    gap = timedelta(minutes=get_service_gap_minutes(salon))
    current = start_at
    schedule = []
    items = list(items)
    for index, item in enumerate(items):
        duration = getattr(item, "duration_minutes_snapshot", None)
        if duration is None:
            duration = getattr(item, "duration_minutes", 0) or 0
        name = getattr(item, "service_name_snapshot", None) or getattr(item, "name", "")
        is_addon = bool(getattr(item, "is_addon_snapshot", False))
        prev_item = items[index - 1] if index > 0 else None
        same_service_as_prev = (
            prev_item is not None
            and getattr(item, "service_id", None) is not None
            and getattr(item, "service_id", None) == getattr(prev_item, "service_id", None)
        )

        # Zero-minute extras stay inside the parent block's displayed window.
        if duration == 0 and schedule and (is_addon or same_service_as_prev):
            prev = schedule[-1]
            schedule.append(
                {
                    "name": name,
                    "start": prev["start"],
                    "end": prev["end"],
                    "duration_minutes": 0,
                    "start_time": prev["start_time"],
                    "end_time": prev["end_time"],
                    "is_addon": True,
                }
            )
            continue

        end = current + timedelta(minutes=duration)
        local_start = timezone.localtime(current)
        local_end = timezone.localtime(end)
        schedule.append(
            {
                "name": name,
                "start": current,
                "end": end,
                "duration_minutes": duration,
                "start_time": local_start.strftime("%H:%M"),
                "end_time": local_end.strftime("%H:%M"),
                "is_addon": is_addon,
            }
        )
        current = end
        if index < len(items) - 1:
            next_item = items[index + 1]
            same_service = getattr(item, "service_id", None) is not None and (
                getattr(item, "service_id", None) == getattr(next_item, "service_id", None)
            )
            # No gap between a base and its add-ons (same parent service).
            if not same_service:
                current += gap
    return schedule


def format_services_label(booking, max_length=40):
    names = [item.service_name_snapshot for item in booking.booking_services.all()]
    if not names:
        return "—"
    if len(names) == 1:
        return names[0]
    joined = " + ".join(names)
    if len(joined) <= max_length:
        return joined
    return _("%(count)s services") % {"count": len(names)}


def format_services_for_email(booking):
    items = list(booking.booking_services.all())
    if not items:
        return "—"
    if len(items) == 1:
        return items[0].service_name_snapshot
    return "\n".join(f"• {item.service_name_snapshot}" for item in items)


def get_booking_total_price_display(booking):
    items = list(booking.booking_services.all())
    if not items:
        return ""
    total = sum((item.price_snapshot for item in items), Decimal("0"))
    if len(items) == 1:
        return f"{items[0].price_snapshot:.0f}"
    return f"{total:.0f}"


def get_blocking_booking_statuses(salon):
    statuses = [Booking.Status.APPROVED]
    if get_policy_value(salon, "pending_holds_slot", True):
        statuses.append(Booking.Status.PENDING)
    return statuses


def get_buffer_minutes(salon):
    return get_policy_value(salon, "buffer_minutes_between_bookings", 0)


def get_buffer_timedelta(salon):
    return timedelta(minutes=get_buffer_minutes(salon))


def get_salon_local_today(salon, now=None):
    if now is None:
        now = timezone.now()
    return timezone.localdate(now, get_salon_timezone(salon))


def intervals_overlap_with_buffer(existing_start, existing_end, new_start, new_end, buffer):
    return intervals_overlap(
        existing_start - buffer,
        existing_end + buffer,
        new_start,
        new_end,
    )


def count_blocking_bookings_on_date(salon, selected_date, exclude_booking_id=None):
    statuses = get_blocking_booking_statuses(salon)
    working_interval = get_working_interval_for_date(salon, selected_date)
    if not working_interval:
        return 0

    day_start, day_end = working_interval
    qs = salon.bookings.filter(
        status__in=statuses,
        start_at__lt=day_end,
        end_at__gt=day_start,
    )
    if exclude_booking_id:
        qs = qs.exclude(pk=exclude_booking_id)
    return qs.count()


def is_daily_appointment_limit_reached(salon, selected_date, exclude_booking_id=None):
    max_per_day = get_policy_value(salon, "max_appointments_per_day", 0)
    if not max_per_day:
        return False
    return count_blocking_bookings_on_date(
        salon, selected_date, exclude_booking_id=exclude_booking_id
    ) >= max_per_day


def find_conflicting_booking(
    salon,
    start_at,
    end_at,
    *,
    exclude_booking_id=None,
    booking_status=None,
):
    if not salon or not start_at or not end_at:
        return None

    statuses = get_blocking_booking_statuses(salon)
    if booking_status is not None and booking_status not in statuses:
        return None

    buffer = get_buffer_timedelta(salon)
    query = Booking.objects.filter(
        salon=salon,
        status__in=statuses,
        start_at__lt=end_at + buffer,
        end_at__gt=start_at - buffer,
    )
    if exclude_booking_id:
        query = query.exclude(pk=exclude_booking_id)

    for booking in query:
        if intervals_overlap_with_buffer(
            booking.start_at, booking.end_at, start_at, end_at, buffer
        ):
            return booking
    return None


def get_unbookable_dates_for_customer(salon, start_date, end_date):
    """ISO date strings that are closed or have no working window within the booking window."""
    closed = []
    current = start_date
    while current <= end_date:
        if get_working_window_for_date(salon, current) is None:
            closed.append(current.isoformat())
        current += timedelta(days=1)
    return closed


def _is_inside_notice_window(salon, start_at, now=None):
    """True when appointment date is before the normal minimum-notice cutoff."""
    if now is None:
        now = timezone.now()
    today = timezone.localdate(now, get_salon_timezone(salon))
    minimum_notice_days = get_policy_value(salon, "minimum_notice_days", 14)
    appointment_date = timezone.localdate(start_at, get_salon_timezone(salon))
    notice_cutoff = today + timedelta(days=minimum_notice_days)
    return today <= appointment_date < notice_cutoff


def release_interval(salon, start_at, end_at, source_booking=None):
    """Mark a freed interval as publicly bookable inside the notice window."""
    if start_at >= end_at:
        return None
    slot, _created = ReleasedSlot.objects.update_or_create(
        salon=salon,
        start_at=start_at,
        end_at=end_at,
        defaults={
            "is_active": True,
            "source_booking": source_booking,
        },
    )
    return slot


def release_booking_slot(booking):
    """Release a booking's time for last-minute public rebooking when policy allows."""
    result = release_timeslot(
        booking.salon,
        booking.start_at,
        booking.end_at,
        source_booking=booking,
    )
    if result:
        local_date = timezone.localdate(booking.start_at, get_salon_timezone(booking.salon))
        merge_adjacent_released_slots(booking.salon, local_date)
    return result


def release_timeslot(salon, start_at, end_at, source_booking=None):
    """Release a specific interval for last-minute public rebooking when policy allows."""
    if not get_policy_value(salon, "allow_last_minute_reopen", True):
        return None
    now = timezone.now()
    if start_at <= now:
        return None
    if not _is_inside_notice_window(salon, start_at, now=now):
        return None
    return release_interval(
        salon,
        start_at,
        end_at,
        source_booking=source_booking,
    )


def consume_released_slot(salon, start_at, end_at):
    """Carve a booked interval out of active releases, leaving the rest bookable."""
    overlapping = list(
        ReleasedSlot.objects.filter(
            salon=salon,
            is_active=True,
            start_at__lt=end_at,
            end_at__gt=start_at,
        )
    )
    for release in overlapping:
        source = release.source_booking
        release.is_active = False
        release.save(update_fields=["is_active"])
        if release.start_at < start_at:
            release_interval(
                salon,
                release.start_at,
                start_at,
                source_booking=source,
            )
        if end_at < release.end_at:
            release_interval(
                salon,
                end_at,
                release.end_at,
                source_booking=source,
            )


def merge_adjacent_released_slots(salon, selected_date):
    """Merge touching active releases on a date back into one bookable window."""
    salon_tz = get_salon_timezone(salon)
    day_start = timezone.make_aware(
        datetime.combine(selected_date, time.min),
        salon_tz,
    )
    day_end = day_start + timedelta(days=1)
    releases = list(
        ReleasedSlot.objects.filter(
            salon=salon,
            is_active=True,
            start_at__lt=day_end,
            end_at__gt=day_start,
        ).order_by("start_at")
    )
    if len(releases) < 2:
        return

    groups = []
    group_start = releases[0].start_at
    group_end = releases[0].end_at
    group_source = releases[0].source_booking
    group_ids = [releases[0].pk]

    for release in releases[1:]:
        if release.start_at <= group_end:
            group_end = max(group_end, release.end_at)
            group_ids.append(release.pk)
        else:
            groups.append((group_start, group_end, group_source, group_ids))
            group_start = release.start_at
            group_end = release.end_at
            group_source = release.source_booking
            group_ids = [release.pk]
    groups.append((group_start, group_end, group_source, group_ids))

    for group_start, group_end, group_source, group_ids in groups:
        if len(group_ids) < 2:
            continue
        ReleasedSlot.objects.filter(pk__in=group_ids).update(is_active=False)
        release_interval(
            salon,
            group_start,
            group_end,
            source_booking=group_source,
        )


def get_active_released_intervals(salon, selected_date, now=None):
    if now is None:
        now = timezone.now()
    salon_tz = get_salon_timezone(salon)
    day_start = timezone.make_aware(
        datetime.combine(selected_date, time.min),
        salon_tz,
    )
    day_end = day_start + timedelta(days=1)
    return list(
        ReleasedSlot.objects.filter(
            salon=salon,
            is_active=True,
            start_at__lt=day_end,
            end_at__gt=max(day_start, now),
        ).order_by("start_at")
    )


def get_last_minute_open_dates(salon, today, notice_cutoff_date, now=None):
    """ISO date strings with active released slots inside the notice window."""
    if not get_policy_value(salon, "allow_last_minute_reopen", True):
        return []
    if now is None:
        now = timezone.now()
    if notice_cutoff_date <= today:
        return []
    qs = ReleasedSlot.objects.filter(
        salon=salon,
        is_active=True,
        end_at__gt=now,
        start_at__date__lt=notice_cutoff_date,
    ).values_list("start_at", flat=True)
    dates = set()
    salon_tz = get_salon_timezone(salon)
    for start_at in qs:
        local_day = timezone.localdate(start_at, salon_tz)
        if today <= local_day < notice_cutoff_date:
            dates.add(local_day.isoformat())
    return sorted(dates)


def get_last_minute_open_dates_for_services(
    salon, services, today, notice_cutoff_date, now=None
):
    """Dates with at least one bookable last-minute slot for the selected services."""
    if now is None:
        now = timezone.now()
    services = normalize_services(services)
    if not services:
        return []

    bookable = []
    for date_str in get_last_minute_open_dates(salon, today, notice_cutoff_date, now=now):
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if get_available_slots(salon, services, selected_date, now=now):
            bookable.append(date_str)
    return bookable


def get_fully_booked_dates_for_services(
    salon, services, start_date, end_date, duration_override_minutes=None, now=None
):
    """ISO dates in ``[start_date, end_date]`` that are open (have a working
    window) but offer zero available slots for the selected services — i.e. days
    that are already fully booked.

    Closed days (no working window) are intentionally excluded here: the calendar
    already marks those separately, so we only want to flag *working* days that
    happen to be full. Iterates day-by-day reusing ``get_available_slots``; this
    is fine for the pilot's ~60-day booking window.
    """
    if now is None:
        now = timezone.now()
    services = normalize_services(services)
    if not services:
        return []

    full = []
    current = start_date
    while current <= end_date:
        if get_working_window_for_date(salon, current) is not None:
            slots = get_available_slots(
                salon,
                services,
                current,
                now=now,
                duration_override_minutes=duration_override_minutes,
            )
            if not slots:
                full.append(current.isoformat())
        current += timedelta(days=1)
    return full


def _slot_fits_release(slot_start, slot_end, release):
    return release.start_at <= slot_start and slot_end <= release.end_at


def _filter_slots_to_released_only(slots, released_intervals):
    if not released_intervals:
        return []
    filtered = []
    for slot in slots:
        slot_start = slot["start"]
        slot_end = slot["end"]
        for release in released_intervals:
            if _slot_fits_release(slot_start, slot_end, release):
                filtered.append(slot)
                break
    return filtered


def get_available_slots(
    salon,
    services,
    selected_date,
    now=None,
    *,
    for_owner=False,
    exclude_booking_id=None,
    duration_override_minutes=None,
):
    if now is None:
        now = timezone.now()

    services = normalize_services(services)
    if not services or any(service.salon_id != salon.id for service in services):
        return []

    last_minute_only = False
    released_intervals = []
    if not for_owner:
        date_ok = is_date_allowed(salon, selected_date, now=now)
        if get_policy_value(salon, "allow_last_minute_reopen", True):
            released_intervals = get_active_released_intervals(
                salon, selected_date, now=now
            )
        if not date_ok:
            if not released_intervals:
                return []
            last_minute_only = True

    working_interval = get_working_interval_for_date(salon, selected_date)
    if not working_interval:
        return []

    if is_daily_appointment_limit_reached(
        salon, selected_date, exclude_booking_id=exclude_booking_id
    ):
        return []

    working_start, working_end = working_interval
    if duration_override_minutes:
        combined_minutes = duration_override_minutes
    else:
        combined_minutes = calculate_combined_duration_minutes(services, salon)
    service_duration = timedelta(minutes=combined_minutes)

    busy_intervals = get_busy_intervals_for_date(
        salon,
        selected_date,
        exclude_booking_id=exclude_booking_id,
    )
    visit_spans = get_blocking_visit_spans_for_date(
        salon,
        selected_date,
        exclude_booking_id=exclude_booking_id,
    )
    fixed_times = get_salon_fixed_start_times(salon)
    if fixed_times is not None:
        candidates = generate_fixed_packing_candidates(
            selected_date=selected_date,
            salon=salon,
            working_start=working_start,
            working_end=working_end,
            duration=service_duration,
            fixed_time_strings=fixed_times,
            visit_spans=visit_spans,
        )
    else:
        slot_interval = timedelta(
            minutes=get_policy_value(salon, "slot_interval_minutes", 30)
        )
        if slot_interval.total_seconds() <= 0:
            slot_interval = timedelta(minutes=30)
        candidates = generate_candidate_slots(
            working_start=working_start,
            working_end=working_end,
            duration=service_duration,
            slot_interval=slot_interval,
        )

    slots = []
    salon_tz = get_salon_timezone(salon)
    for candidate_start, candidate_end in candidates:
        if candidate_start < now:
            continue

        if any(
            intervals_overlap(busy_start, busy_end, candidate_start, candidate_end)
            for busy_start, busy_end in busy_intervals
        ):
            continue

        local_start = timezone.localtime(candidate_start, salon_tz)
        local_end = timezone.localtime(candidate_end, salon_tz)
        slots.append(
            {
                "start": candidate_start,
                "end": candidate_end,
                "value": local_start.strftime("%H:%M"),
                "label": f"{local_start:%H:%M} - {local_end:%H:%M}",
            }
        )

    if last_minute_only:
        return _filter_slots_to_released_only(slots, released_intervals)

    return slots


def calculate_available_slots(salon, services, selected_date, now=None):
    return get_available_slots(salon, services, selected_date, now=now)


def get_policy_value(salon, field_name, default):
    try:
        policy = salon.booking_policy
    except BookingPolicy.DoesNotExist:
        return default

    return getattr(policy, field_name, default)


CALENDAR_TERMINAL_STATUSES = frozenset({
    Booking.Status.COMPLETED,
    Booking.Status.CANCELLED,
    Booking.Status.REJECTED,
    Booking.Status.NO_SHOW,
})


def get_calendar_history_days(salon):
    """Days of past terminal-status bookings to keep visible on the owner calendar."""
    return get_policy_value(salon, "calendar_history_days", 365)


def get_calendar_history_cutoff_date(salon, *, on_date=None):
    on_date = on_date or timezone.localdate()
    return on_date - timedelta(days=get_calendar_history_days(salon))


def booking_visible_on_calendar(booking, cutoff_date):
    if booking.status not in CALENDAR_TERMINAL_STATUSES:
        return True
    local_start = timezone.localtime(booking.start_at).date()
    return local_start >= cutoff_date


def auto_complete_past_bookings(*, salon=None, dry_run=False):
    """
    Mark approved bookings as completed once end_at + policy grace hours has passed.
    Returns the number of bookings updated (or that would be updated when dry_run=True).
    """
    now = timezone.now()
    qs = Booking.objects.filter(status=Booking.Status.APPROVED).select_related(
        "salon", "salon__booking_policy"
    )
    if salon is not None:
        qs = qs.filter(salon=salon)

    updated = 0
    for booking in qs:
        grace_hours = get_policy_value(booking.salon, "auto_complete_hours_after_end", 4)
        if grace_hours <= 0:
            continue
        if now < booking.end_at + timedelta(hours=grace_hours):
            continue
        updated += 1
        if dry_run:
            continue
        booking.status = Booking.Status.COMPLETED
        booking.save(update_fields=["status"])
        log_booking_activity(
            booking,
            BookingActivityLog.Action.COMPLETED,
            note="Auto-completed after appointment ended",
        )

    return updated


def send_due_booking_reminders(*, salon=None, dry_run=False):
    """
    Send appointment reminders for approved bookings when the salon policy window is due.
    Returns the number of bookings reminded (or that would be reminded when dry_run=True).
    """
    now = timezone.now()
    qs = Booking.objects.filter(
        status=Booking.Status.APPROVED,
        reminder_sent_at__isnull=True,
        start_at__gt=now,
    ).select_related("customer", "salon", "salon__booking_policy")
    if salon is not None:
        qs = qs.filter(salon=salon)

    reminded = 0
    for booking in qs:
        hours = get_policy_value(booking.salon, "reminder_hours_before", 24)
        if hours <= 0:
            continue

        reminder_due_at = booking.start_at - timedelta(hours=hours)
        if now < reminder_due_at:
            continue

        if dry_run:
            reminded += 1
            continue

        sent, reason = send_booking_notification(booking, "reminder")
        if sent:
            booking.reminder_sent_at = now
            booking.save(update_fields=["reminder_sent_at"])
            log_booking_activity(
                booking,
                BookingActivityLog.Action.EMAIL_SENT,
                note="Appointment reminder sent to customer",
            )
            reminded += 1
            continue

        policy = getattr(booking.salon, "booking_policy", None)
        has_email = bool((booking.customer.email or "").strip())
        sms_enabled = bool(policy and policy.sms_notifications_enabled)
        has_phone = bool((booking.customer.phone_number or "").strip())
        if not has_email and not (sms_enabled and has_phone):
            booking.reminder_sent_at = now
            booking.save(update_fields=["reminder_sent_at"])
            log_booking_activity(
                booking,
                BookingActivityLog.Action.EMAIL_SENT,
                note="Appointment reminder skipped — no customer contact channel",
            )
            logger.info(
                "Reminder skipped for booking %s — no email and SMS not available (%s)",
                booking.pk,
                reason,
            )
            reminded += 1

    return reminded


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


def get_blocking_visit_spans_for_date(salon, selected_date, exclude_booking_id=None):
    """Actual start/end of blocking bookings on a date (no policy buffer)."""
    working_interval = get_working_interval_for_date(salon, selected_date)
    if not working_interval:
        return []

    day_start, day_end = working_interval
    status_values = get_blocking_booking_statuses(salon)
    bookings = salon.bookings.filter(
        status__in=status_values,
        start_at__lt=day_end,
        end_at__gt=day_start,
    )
    if exclude_booking_id:
        bookings = bookings.exclude(pk=exclude_booking_id)
    return [(booking.start_at, booking.end_at) for booking in bookings.order_by("start_at")]


def leftover_start_after_visit(visit_start, visit_end, anchors, gap):
    """Next extra start after a visit, or None to keep the next anchor.

    - Ends before the next anchor, and end+gap still before it → extra at end+gap.
    - Ends before the next anchor, but end+gap would reach/pass it → keep the anchor.
    - Ends on or after the next anchor → extra at end+gap (that anchor is used up).
    - No later anchor → extra at end+gap (must still fit the working day).
    """
    next_anchor = next((anchor for anchor in anchors if anchor > visit_start), None)
    extra = visit_end + gap
    if next_anchor is None:
        return extra
    if visit_end < next_anchor:
        if extra < next_anchor:
            return extra
        return None
    return extra


def consumed_fixed_anchors(visit_spans, anchors):
    """Anchors a visit has already reached or passed (start < anchor <= end)."""
    consumed = set()
    for visit_start, visit_end in visit_spans:
        for anchor in anchors:
            if visit_start < anchor <= visit_end:
                consumed.add(anchor)
    return consumed


def packing_gap_conflict(candidate_start, candidate_end, visit_spans, gap):
    """True when a leftover extra sits closer than ``gap`` to another visit."""
    for visit_start, visit_end in visit_spans:
        if intervals_overlap(visit_start, visit_end, candidate_start, candidate_end):
            return True
        if visit_end <= candidate_start and candidate_start < visit_end + gap:
            return True
        if visit_start >= candidate_end and candidate_end + gap > visit_start:
            return True
    return False


def resolve_fixed_anchor_datetimes(
    selected_date,
    salon,
    time_strings,
    working_start,
    working_end,
):
    salon_tz = get_salon_timezone(salon)
    anchors = []
    seen = set()
    for time_string in time_strings:
        match = FIXED_START_TIME_RE.match(str(time_string).strip())
        if not match:
            continue
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            continue
        anchor = timezone.make_aware(
            datetime.combine(selected_date, time(hour, minute)),
            salon_tz,
        )
        if anchor in seen:
            continue
        if working_start <= anchor < working_end:
            seen.add(anchor)
            anchors.append(anchor)
    anchors.sort()
    return anchors


def fixed_anchor_step(anchors, gap):
    """Spacing between original anchors (2h visit + 30 min gap → 2h30)."""
    if len(anchors) >= 2:
        step = anchors[1] - anchors[0]
        if step.total_seconds() > 0:
            return step
    return timedelta(minutes=120) + gap


def generate_fixed_packing_candidates(
    *,
    selected_date,
    salon,
    working_start,
    working_end,
    duration,
    fixed_time_strings,
    visit_spans,
):
    """Anchor starts plus leftover extras after shorter visits.

    Empty days stay on the configured anchors only. Extra starts appear at
    visit_end + 30 minutes when that hole is still before the next anchor.
    """
    gap = timedelta(minutes=FIXED_START_PACKING_GAP_MINUTES)
    salon_tz = get_salon_timezone(salon)
    visit_spans = [
        (timezone.localtime(start, salon_tz), timezone.localtime(end, salon_tz))
        for start, end in visit_spans
    ]
    anchors = resolve_fixed_anchor_datetimes(
        selected_date,
        salon,
        fixed_time_strings,
        working_start,
        working_end,
    )
    consumed = consumed_fixed_anchors(visit_spans, anchors)
    visit_spans.sort(key=lambda item: item[0])
    step = fixed_anchor_step(anchors, gap)

    rebase_windows = []
    rebased = []

    for visit_start, visit_end in visit_spans:
        extra_start = leftover_start_after_visit(visit_start, visit_end, anchors, gap)
        if extra_start is None:
            continue
        next_visit_start = next(
            (start for start, _end in visit_spans if start > visit_end),
            None,
        )
        window_end = next_visit_start if next_visit_start is not None else working_end
        rebase_windows.append((extra_start, window_end))

        grid_start = extra_start
        while grid_start < window_end:
            grid_end = grid_start + duration
            if grid_end > working_end:
                break
            if (
                grid_start >= working_start
                and not packing_gap_conflict(grid_start, grid_end, visit_spans, gap)
            ):
                rebased.append((grid_start, grid_end))
            grid_start += step

    def in_rebase_window(moment):
        return any(start <= moment < end for start, end in rebase_windows)

    results = []
    seen_starts = set()

    for anchor in anchors:
        if anchor in consumed or in_rebase_window(anchor):
            continue
        candidate_end = anchor + duration
        if candidate_end <= working_end:
            results.append((anchor, candidate_end))
            seen_starts.add(anchor)

    for start, end in rebased:
        if start in seen_starts:
            continue
        results.append((start, end))
        seen_starts.add(start)

    results.sort(key=lambda item: item[0])
    yield from results


def get_busy_intervals_for_date(salon, selected_date, exclude_booking_id=None):
    working_interval = get_working_interval_for_date(salon, selected_date)
    if not working_interval:
        return []

    day_start, day_end = working_interval
    buffer = get_buffer_timedelta(salon)
    status_values = get_blocking_booking_statuses(salon)

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


def parse_fixed_start_times_text(text):
    if not (text or "").strip():
        return []
    parts = re.split(r"[,\n]+", text.strip())
    return normalize_fixed_start_times(parts)


def normalize_fixed_start_times(parts):
    seen = set()
    normalized = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = FIXED_START_TIME_RE.match(part)
        if not match:
            raise ValueError(
                _("Each time must be in HH:MM format (e.g. 08:00).")
            )
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError(
                _("Each time must be a valid clock time (00:00–23:59).")
            )
        value = f"{hour:02d}:{minute:02d}"
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    normalized.sort(key=lambda item: (int(item[:2]), int(item[3:5])))
    return normalized


def get_salon_fixed_start_times(salon):
    if not get_policy_value(salon, "use_fixed_start_times", False):
        return None
    times = get_policy_value(salon, "fixed_start_times", [])
    if not isinstance(times, list):
        return []
    return times


def generate_fixed_candidate_slots(
    *,
    selected_date,
    salon,
    working_start,
    working_end,
    duration,
    fixed_time_strings,
):
    salon_tz = get_salon_timezone(salon)
    for time_string in fixed_time_strings:
        match = FIXED_START_TIME_RE.match(str(time_string).strip())
        if not match:
            continue
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            continue
        candidate_start = timezone.make_aware(
            datetime.combine(selected_date, time(hour, minute)),
            salon_tz,
        )
        if candidate_start < working_start:
            continue
        candidate_end = candidate_start + duration
        if candidate_end <= working_end:
            yield candidate_start, candidate_end


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
    services,
    selected_date,
    start_time_value,
    *,
    for_owner=False,
    exclude_booking_id=None,
    duration_override_minutes=None,
):
    slots = get_available_slots(
        salon,
        services,
        selected_date,
        for_owner=for_owner,
        exclude_booking_id=exclude_booking_id,
        duration_override_minutes=duration_override_minutes,
    )
    return next((slot for slot in slots if slot["value"] == start_time_value), None)


def get_salon_page_hours_rows(salon, working_hours):
    """Build display rows for the public salon page (may differ from booking hours)."""
    override_end = salon.public_hours_end_display
    rows = []
    for row in working_hours:
        display_end = override_end if override_end and row.is_working_day else row.end_time
        rows.append(
            {
                "row": row,
                "display_start_time": row.start_time,
                "display_end_time": display_end,
            }
        )
    return rows


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


def _last_n_months(end_date, n):
    """Return the last ``n`` (year, month) tuples ending at ``end_date`` (oldest first)."""
    months = []
    year, month = end_date.year, end_date.month
    for _i in range(n):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def _month_keys_inclusive(start_date, end_date):
    """Return (year, month) tuples from ``start_date`` through ``end_date`` (oldest first)."""
    keys = []
    year, month = start_date.year, start_date.month
    while (year, month) <= (end_date.year, end_date.month):
        keys.append((year, month))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return keys


def _weekday_labels_for(today):
    this_monday = today - timedelta(days=today.weekday())
    return [date_format(this_monday + timedelta(days=i), "D") for i in range(7)]


def _booking_line_revenue(booking):
    return sum(
        (bs.price_snapshot or Decimal("0")) for bs in booking.booking_services.all()
    )


def _stats_for_bookings(bookings, weekday_labels, trend_spec):
    """Build one range payload from an in-memory booking list.

    ``trend_spec`` is ``("day", [date, ...])`` or ``("month", [(year, month), ...])``.
    """
    Status = Booking.Status
    accepted = {Status.APPROVED, Status.COMPLETED, Status.NO_SHOW}
    granularity, trend_keys = trend_spec
    buckets = {key: {"revenue": 0, "bookings": 0} for key in trend_keys}

    revenue_total = 0
    completed = 0
    no_show = 0
    online = 0
    weekday_counts = [0] * 7
    service_stats = {}

    for booking in bookings:
        local_dt = timezone.localtime(booking.start_at)
        if booking.source == Booking.Source.ONLINE:
            online += 1

        line_revenue = 0
        if booking.status == Status.COMPLETED:
            line_revenue = int(_booking_line_revenue(booking))
            revenue_total += line_revenue
            completed += 1
        elif booking.status == Status.NO_SHOW:
            no_show += 1

        if booking.status in accepted:
            weekday_counts[local_dt.weekday()] += 1
            tkey = local_dt.date() if granularity == "day" else (local_dt.year, local_dt.month)
            if tkey in buckets:
                buckets[tkey]["bookings"] += 1
                if booking.status == Status.COMPLETED:
                    buckets[tkey]["revenue"] += line_revenue

        for line in booking.booking_services.all():
            name = (line.service_name_snapshot or "").strip()
            if not name:
                continue
            entry = service_stats.setdefault(name, {"count": 0, "revenue": 0})
            entry["count"] += 1
            entry["revenue"] += int(line.price_snapshot or 0)

    finished_total = completed + no_show
    real_total = len(bookings)
    top_services = sorted(
        (
            {"name": name, "count": data["count"], "revenue": data["revenue"]}
            for name, data in service_stats.items()
        ),
        key=lambda row: (-row["count"], row["name"]),
    )[:5]

    if granularity == "day":
        trend = [
            {
                "label": str(day.day),
                "revenue": buckets[day]["revenue"],
                "bookings": buckets[day]["bookings"],
            }
            for day in trend_keys
        ]
    else:
        trend = [
            {
                "label": date_format(date(year, month, 1), "M y"),
                "revenue": buckets[(year, month)]["revenue"],
                "bookings": buckets[(year, month)]["bookings"],
            }
            for year, month in trend_keys
        ]

    weekday_distribution = [
        {"label": weekday_labels[i], "count": weekday_counts[i]} for i in range(7)
    ]
    busiest_weekday = None
    if any(weekday_counts):
        busiest_index = max(range(7), key=lambda i: weekday_counts[i])
        busiest_weekday = {
            "label": weekday_labels[busiest_index],
            "count": weekday_counts[busiest_index],
        }

    return {
        "revenue": revenue_total,
        "completed": completed,
        "no_show_rate": round(no_show / finished_total * 100) if finished_total else 0,
        "no_show_total": no_show,
        "online_share": round(online / real_total * 100) if real_total else 0,
        "online_total": online,
        "trend": trend,
        "top_services": top_services,
        "busiest_weekday": busiest_weekday,
        "weekday_distribution": weekday_distribution,
        "has_data": real_total > 0,
    }


def get_owner_statistics(salon, months=6):
    """Aggregate owner-facing statistics for the dashboard.

    Returns three ranges (this month / this year / all time) so the owner can
    toggle without another round-trip. Money comes from completed bookings only
    (no online payments), matching ``get_revenue_stats``. Dates are bucketed in
    the salon's local time.

    ``months`` is kept for callers that still pass it; all-time charts cap at
    the last 24 months when history is longer.
    """
    Status = Booking.Status
    today = timezone.localdate()
    weekday_labels = _weekday_labels_for(today)

    bookings = list(
        salon.bookings.exclude(status=Status.UNVERIFIED)
        .prefetch_related("booking_services")
    )
    dated = [(booking, timezone.localtime(booking.start_at).date()) for booking in bookings]

    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)

    month_bookings = [b for b, d in dated if month_start <= d <= month_end]
    year_bookings = [b for b, d in dated if year_start <= d <= year_end]
    all_bookings = [b for b, _d in dated]

    month_days = [
        date(today.year, today.month, day) for day in range(1, month_end.day + 1)
    ]
    year_months = [(today.year, month) for month in range(1, 13)]
    if dated:
        first_date = min(d for _b, d in dated)
        last_date = max(today, max(d for _b, d in dated))
        all_months = _month_keys_inclusive(first_date, last_date)
        cap = max(int(months or 6), 24)
        if len(all_months) > cap:
            all_months = all_months[-cap:]
    else:
        all_months = _last_n_months(today, months)

    ranges = {
        "month": _stats_for_bookings(
            month_bookings, weekday_labels, ("day", month_days)
        ),
        "year": _stats_for_bookings(
            year_bookings, weekday_labels, ("month", year_months)
        ),
        "all": _stats_for_bookings(
            all_bookings, weekday_labels, ("month", all_months)
        ),
    }
    month_stats = ranges["month"]
    all_stats = ranges["all"]
    return {
        "has_data": all_stats["has_data"],
        "default_range": "month",
        "ranges": ranges,
        # Back-compat aliases used by older overview/KPI callers and tests.
        "revenue_this_month": month_stats["revenue"],
        "revenue_all_time": all_stats["revenue"],
        "completed_this_month": month_stats["completed"],
        "no_show_rate": all_stats["no_show_rate"],
        "no_show_total": all_stats["no_show_total"],
        "online_share": all_stats["online_share"],
        "online_total": all_stats["online_total"],
        "monthly": all_stats["trend"],
        "top_services": all_stats["top_services"],
        "busiest_weekday": all_stats["busiest_weekday"],
        "weekday_distribution": all_stats["weekday_distribution"],
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


def format_booking_date_label(dt):
    """Localized date for prepared messages, e.g. 9 July / 9 Јули 2026."""
    local_dt = timezone.localtime(dt)
    return date_format(local_dt, "j F Y")


def build_prepared_message(booking, message_type):
    first_name = booking.customer.full_name.split()[0]
    date_label = format_booking_date_label(booking.start_at)
    time_label = timezone.localtime(booking.start_at).strftime("%H:%M")
    salon_name = booking.salon.name

    vars_ = {
        "ime": first_name,
        "datum": date_label,
        "vreme": time_label,
        "salon": salon_name,
        "uslugi": format_services_label(booking),
    }

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


def get_manage_booking_url(booking):
    """Absolute or relative URL for the customer's private manage-booking page."""
    path = reverse("booking:manage_booking", args=[booking.manage_token])
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    return f"{site_url}{path}" if site_url else path


def _ics_escape(text):
    """Escape text for iCalendar property values."""
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def booking_services_label(booking):
    names = [item.service_name_snapshot for item in booking.booking_services.all()]
    return ", ".join(names) if names else booking.salon.name


def build_booking_ics(booking, *, for_customer=True):
    """Return (filename, ics_body) for a booking calendar event."""
    salon = booking.salon
    local_start = timezone.localtime(booking.start_at)
    local_end = timezone.localtime(booking.end_at)
    services = booking_services_label(booking)
    uid = f"booking-{booking.manage_token}@vremio"
    now_stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")

    def fmt(dt):
        return dt.strftime("%Y%m%dT%H%M%S")

    if for_customer:
        summary = f"{salon.name} — {services}"
        description_parts = [
            f"Salon: {salon.name}",
            f"Services: {services}",
            f"Manage: {get_manage_booking_url(booking)}",
        ]
    else:
        summary = f"{booking.customer.full_name} — {services}"
        description_parts = [
            f"Phone: {booking.customer.phone_number or '—'}",
            f"Instagram: {booking.customer.instagram_username or '—'}",
            f"Status: {booking.get_status_display()}",
        ]

    location = salon.name
    if getattr(salon, "address", None):
        city = getattr(salon, "city", "") or ""
        location = ", ".join(p for p in [salon.address, city, salon.name] if p)

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Vremio//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART:{fmt(local_start)}",
        f"DTEND:{fmt(local_end)}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(chr(10).join(description_parts))}",
        f"LOCATION:{_ics_escape(location)}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    body = "\r\n".join(ics_lines) + "\r\n"
    filename = f"vremio-{local_start.strftime('%Y%m%d-%H%M')}.ics"
    return filename, body


def google_calendar_url(booking):
    """One-click Google Calendar template URL with the booking pre-filled."""
    from urllib.parse import urlencode

    salon = booking.salon
    local_start = timezone.localtime(booking.start_at)
    local_end = timezone.localtime(booking.end_at)
    services = booking_services_label(booking)

    def fmt(dt):
        return dt.strftime("%Y%m%dT%H%M%S")

    dates = f"{fmt(local_start)}/{fmt(local_end)}"
    details = "\n".join(
        [
            f"{salon.name}",
            f"{services}",
            get_manage_booking_url(booking),
        ]
    )
    location = salon.name
    if getattr(salon, "address", None):
        city = getattr(salon, "city", "") or ""
        location = ", ".join(p for p in [salon.address, city] if p) or salon.name

    params = {
        "action": "TEMPLATE",
        "text": f"{salon.name} — {services}",
        "dates": dates,
        "details": details,
        "location": location,
    }
    return f"https://calendar.google.com/calendar/render?{urlencode(params)}"


def can_customer_cancel_booking(booking, now=None):
    """
    Return (allowed: bool, reason: str).
    reason is one of: pending, approved, past, too_close, rejected, cancelled, completed, no_show
    """
    if now is None:
        now = timezone.now()

    if booking.start_at <= now:
        return False, "past"

    if booking.status == Booking.Status.PENDING:
        return True, "pending"

    if booking.status == Booking.Status.APPROVED:
        notice_hours = get_policy_value(booking.salon, "customer_cancellation_notice_hours", 24)
        hours_until = (booking.start_at - now).total_seconds() / 3600
        if hours_until >= notice_hours:
            return True, "approved"
        return False, "too_close"

    if booking.status == Booking.Status.REJECTED:
        return False, "rejected"
    if booking.status == Booking.Status.CANCELLED:
        return False, "cancelled"
    if booking.status == Booking.Status.COMPLETED:
        return False, "completed"
    if booking.status == Booking.Status.NO_SHOW:
        return False, "no_show"

    return False, booking.status


def send_booking_notification(booking, action, request=None):
    """
    Notify the customer by email and/or SMS based on salon policy.
    Returns (sent: bool, reason: str).
    """
    from . import email_utils
    from . import sms_utils

    policy = getattr(booking.salon, "booking_policy", None)
    sms_enabled = bool(policy and policy.sms_notifications_enabled)

    send_map = {
        "approved": email_utils.send_booking_approved_email,
        "rejected": email_utils.send_booking_rejected_email,
        "edited": email_utils.send_booking_updated_email,
        "cancelled": email_utils.send_booking_cancelled_email,
        "no_show": lambda b: email_utils.send_customer_booking_email(b, "no_show"),
        "pending": lambda b: email_utils.send_customer_booking_email(b, "pending"),
        "request_received": email_utils.send_booking_request_received_email,
        "customer_cancelled": email_utils.send_customer_cancellation_confirmation_email,
        "reminder": email_utils.send_booking_reminder_email,
    }
    sender = send_map.get(action)
    if not sender and not sms_enabled:
        return False, "unknown_action"

    email_sent = False
    email_reason = "skipped"
    if sender:
        email_sent, email_reason = sender(booking)

    sms_sent = False
    sms_reason = "skipped"
    if sms_enabled and (booking.customer.phone_number or "").strip():
        sms_sent, sms_reason = sms_utils.send_booking_status_sms(booking, action)

    if email_sent or sms_sent:
        return True, "sent"
    if email_reason == "no_email" and sms_reason in ("skipped", "no_api_key", "no_sender"):
        return False, email_reason
    return False, email_reason or sms_reason


def send_owner_new_booking_notification(booking):
    """
    Notify the salon owner when a new online booking request arrives.
    Returns (sent: bool, reason: str). Never raises — booking must always succeed.
    """
    from . import email_utils

    return email_utils.send_owner_new_booking_email(booking)


def send_owner_customer_cancelled_notification(booking):
    """Notify owner when a customer cancels via the manage link."""
    from . import email_utils

    return email_utils.send_owner_customer_cancelled_email(booking)


def defer_after_commit(func, *args, **kwargs):
    """Run a task in a background thread after the DB transaction commits."""

    def _run():
        from django.db import close_old_connections

        close_old_connections()
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception("Deferred booking task failed: %s", getattr(func, "__name__", func))
        finally:
            close_old_connections()

    transaction.on_commit(
        lambda: threading.Thread(target=_run, daemon=True).start()
    )


def send_verification_sms_for_booking(booking):
    """Generate OTP, send SMS, and log activity. Returns (sent, reason)."""
    from . import sms_utils

    policy = getattr(booking.salon, "booking_policy", None)
    if not policy or not policy.sms_verification_required:
        return False, "sms_verification_disabled"

    code = sms_utils.generate_otp_code()
    sms_utils.set_booking_sms_otp(booking, code)
    booking.verification_expires_at = timezone.now() + timedelta(
        minutes=policy.sms_verification_expiration_minutes
    )
    booking.save(update_fields=["verification_expires_at"])

    log_booking_activity(
        booking,
        BookingActivityLog.Action.VERIFICATION_SENT,
        note="SMS verification sent",
    )
    sent, reason = sms_utils.send_otp_sms(booking, code)
    if sent:
        log_booking_activity(
            booking,
            BookingActivityLog.Action.SMS_SENT,
            note="Verification SMS sent to customer",
        )
        logger.info(
            "Verification SMS sent for booking %s to %s",
            booking.pk,
            booking.customer.phone_number,
        )
    else:
        logger.warning(
            "Verification SMS not sent for booking %s (%s)",
            booking.pk,
            reason,
        )
    return sent, reason


def send_verification_email_for_booking(booking):
    """Send verification email and log activity. Returns (sent, reason)."""
    from .email_utils import send_booking_verification_email

    log_booking_activity(
        booking,
        BookingActivityLog.Action.VERIFICATION_SENT,
        note="Email verification sent",
    )
    sent, reason = send_booking_verification_email(booking)
    if sent:
        log_booking_activity(
            booking,
            BookingActivityLog.Action.EMAIL_SENT,
            note="Verification email sent to customer",
        )
        logger.info(
            "Verification email sent for booking %s to %s",
            booking.pk,
            booking.customer.email,
        )
    else:
        logger.warning(
            "Verification email not sent for booking %s (%s)",
            booking.pk,
            reason,
        )
    return sent, reason


def process_verification_booking_emails(booking_id):
    """Send verification email for an unverified online booking (runs in background)."""
    booking = (
        Booking.objects.select_related("customer", "salon", "salon__booking_policy")
        .filter(pk=booking_id)
        .first()
    )
    if not booking:
        return

    send_verification_email_for_booking(booking)


def process_new_online_booking_emails(booking_id):
    """Send customer/owner emails for a new online booking (runs in background)."""
    booking = (
        Booking.objects.select_related("customer", "salon", "salon__booking_policy")
        .filter(pk=booking_id)
        .first()
    )
    if not booking:
        return

    log_booking_activity(
        booking,
        BookingActivityLog.Action.REQUESTED,
        note="Online booking request",
    )
    sent, _reason = send_booking_notification(booking, "request_received")
    if sent:
        log_booking_activity(
            booking,
            BookingActivityLog.Action.EMAIL_SENT,
            note="Request received email sent to customer",
        )
    sent, _reason = send_owner_new_booking_notification(booking)
    if sent:
        log_booking_activity(
            booking,
            BookingActivityLog.Action.EMAIL_SENT,
            note="Owner notified of new request",
        )


def resolve_services_from_booking(booking):
    return [
        item.service
        for item in booking.booking_services.select_related("service").order_by("sort_order")
    ]


def delete_unverified_booking(booking):
    """Remove an unverified booking, restore any held last-minute slot, and delete photo."""
    salon = booking.salon
    start_at = booking.start_at
    end_at = booking.end_at
    if booking.reference_photo:
        booking.reference_photo.delete(save=False)
    booking.delete()
    release_timeslot(salon, start_at, end_at)


def cleanup_expired_unverified_bookings(*, salon=None):
    """Delete expired unverified bookings so they cannot hold slots or limits."""
    now = timezone.now()
    qs = Booking.objects.filter(
        status=Booking.Status.UNVERIFIED,
        verification_expires_at__lt=now,
    ).select_related("salon")
    if salon is not None:
        qs = qs.filter(salon=salon)
    for booking in list(qs):
        delete_unverified_booking(booking)


def complete_booking_verification(booking, *, channel="email"):
    """
    Promote UNVERIFIED booking to PENDING/APPROVED after verification.
    channel is 'email' or 'sms'.
    Returns (success: bool, reason: str).
    """
    if booking.status != Booking.Status.UNVERIFIED:
        return False, "invalid_status"

    if booking.verification_expires_at and booking.verification_expires_at < timezone.now():
        return False, "expired"

    services = resolve_services_from_booking(booking)
    if not services:
        return False, "no_services"

    local_start = timezone.localtime(booking.start_at)
    slot = is_slot_available(
        booking.salon,
        services,
        local_start.date(),
        local_start.strftime("%H:%M"),
    )
    if not slot:
        return False, "slot_unavailable"

    policy = getattr(booking.salon, "booking_policy", None)
    status = Booking.Status.PENDING
    if policy and policy.auto_approve_bookings:
        status = Booking.Status.APPROVED

    booking.status = status
    verified_at = timezone.now()
    if channel == "sms":
        booking.phone_verified_at = verified_at
    else:
        booking.email_verified_at = verified_at
    booking.email_verification_token = None
    booking.sms_otp_digest = ""
    booking.verification_expires_at = None
    booking.save()
    consume_released_slot(booking.salon, booking.start_at, booking.end_at)
    return True, "verified"


def complete_email_verification(booking):
    """Backward-compatible wrapper for email verification completion."""
    return complete_booking_verification(booking, channel="email")


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
    encoded_message = quote(message, safe="")
    links = {
        "tel": f"tel:{phone_number}",
        "sms": "",
        "viber": "",
        "whatsapp": "",
    }
    if not digits:
        return links

    links["sms"] = f"sms:+{digits}?body={encoded_message}"
    # WhatsApp: api.whatsapp.com pre-fills reliably on mobile (wa.me often drops ?text=).
    links["whatsapp"] = f"https://api.whatsapp.com/send?phone={digits}&text={encoded_message}"
    # Viber mobile expects draft=, not text=, for a pre-filled message in the chat field.
    links["viber"] = f"viber://chat?number=%2B{digits}&draft={encoded_message}"
    return links


def get_booking_total_price(booking):
    return sum(
        (item.price_snapshot for item in booking.booking_services.all()),
        Decimal("0"),
    )
