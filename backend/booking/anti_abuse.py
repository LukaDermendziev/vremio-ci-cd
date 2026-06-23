from dataclasses import dataclass, field
import re

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Booking, Customer, CustomerBlocklist

ACTIVE_STATUSES = [Booking.Status.PENDING, Booking.Status.APPROVED]

MSG_PENDING_LIMIT = _(
    "You already have a booking request waiting for approval. "
    "Please wait for the salon to respond or cancel your existing request."
)
MSG_ACTIVE_LIMIT = _(
    "You already have the maximum number of active appointments. "
    "To book a new one, please cancel or complete an existing appointment."
)
MSG_RATE_LIMIT = _(
    "You have sent too many requests in a short time. Please try again later."
)
MSG_BLOCKLIST = _(
    "Your request could not be sent. Please contact the salon."
)
MSG_GENERIC_INVALID = _(
    "Something went wrong. Please check your details and choose an available time."
)
MSG_OWNER_ACTIVE_WARNING = _(
    "This customer already has active appointment(s)."
)

DEVICE_COOKIE_NAME = "salon_booking_device"
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


@dataclass
class AntiAbuseResult:
    ok: bool = True
    error_code: str = ""
    user_message: str = ""
    warnings: list = field(default_factory=list)


def normalize_phone(value):
    if not value:
        return ""
    value = value.strip()
    digits = re.sub(r"[^\d+]", "", value)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    return digits


def normalize_email(value):
    if not value:
        return ""
    return value.strip().lower()


def normalize_instagram(value):
    if not value:
        return ""
    return value.strip().lstrip("@").lower()


def get_client_ip(request):
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


def get_device_token(request):
    if request is None:
        return ""
    return (request.COOKIES.get(DEVICE_COOKIE_NAME) or "").strip()


def _policy_value(policy, name, default):
    if policy is None:
        return default
    return getattr(policy, name, default)


def get_matching_customer_ids(salon, phone, email):
    phone = normalize_phone(phone)
    email = normalize_email(email)
    if not phone and not email:
        return set()

    matched = set()
    for customer in Customer.objects.filter(salon=salon).only("id", "phone_number", "email"):
        if email and normalize_email(customer.email) == email:
            matched.add(customer.id)
        if phone and normalize_phone(customer.phone_number) == phone:
            matched.add(customer.id)
    return matched


def _active_future_bookings(salon, phone, email):
    customer_ids = get_matching_customer_ids(salon, phone, email)
    if not customer_ids:
        return Booking.objects.none()

    now = timezone.now()
    return Booking.objects.filter(
        salon=salon,
        customer_id__in=customer_ids,
        status__in=ACTIVE_STATUSES,
        start_at__gte=now,
    )


def is_customer_blocked(salon, phone, email="", instagram=""):
    phone = normalize_phone(phone)
    email = normalize_email(email)
    instagram = normalize_instagram(instagram)

    entries = CustomerBlocklist.objects.filter(salon=salon, is_active=True)
    for entry in entries:
        if phone and normalize_phone(entry.phone_number) == phone:
            return True
        if email and entry.email and normalize_email(entry.email) == email:
            return True
        if instagram and entry.instagram_username:
            if normalize_instagram(entry.instagram_username) == instagram:
                return True
    return False


def _rate_limit_exceeded(salon_id, policy, ip, phone, email):
    now = timezone.now()
    hour_bucket = now.strftime("%Y%m%d%H")
    day_bucket = now.strftime("%Y%m%d")

    ip_limit = _policy_value(policy, "booking_rate_limit_per_ip_per_hour", 5)
    email_limit = _policy_value(policy, "booking_rate_limit_per_email_per_day", 3)
    phone_limit = _policy_value(policy, "booking_rate_limit_per_phone_per_day", 3)

    if ip and ip_limit:
        key = f"booking_rate:ip:{salon_id}:{ip}:{hour_bucket}"
        if cache.get(key, 0) >= ip_limit:
            return True

    email = normalize_email(email)
    if email and email_limit:
        key = f"booking_rate:email:{salon_id}:{email}:{day_bucket}"
        if cache.get(key, 0) >= email_limit:
            return True

    phone = normalize_phone(phone)
    if phone and phone_limit:
        key = f"booking_rate:phone:{salon_id}:{phone}:{day_bucket}"
        if cache.get(key, 0) >= phone_limit:
            return True

    return False


def record_booking_attempt(salon_id, policy, ip, phone, email, device_token=""):
    now = timezone.now()
    hour_bucket = now.strftime("%Y%m%d%H")
    day_bucket = now.strftime("%Y%m%d")
    ttl_hour = 3600
    ttl_day = 86400

    if ip:
        key = f"booking_rate:ip:{salon_id}:{ip}:{hour_bucket}"
        cache.set(key, cache.get(key, 0) + 1, ttl_hour)

    email = normalize_email(email)
    if email:
        key = f"booking_rate:email:{salon_id}:{email}:{day_bucket}"
        cache.set(key, cache.get(key, 0) + 1, ttl_day)

    phone = normalize_phone(phone)
    if phone:
        key = f"booking_rate:phone:{salon_id}:{phone}:{day_bucket}"
        cache.set(key, cache.get(key, 0) + 1, ttl_day)

    if device_token and ip:
        key = f"booking_rate:device:{salon_id}:{device_token}:{ip}:{hour_bucket}"
        cache.set(key, cache.get(key, 0) + 1, ttl_hour)


def check_public_booking_allowed(
    salon,
    policy,
    *,
    phone,
    email,
    instagram="",
    ip="",
    device_token="",
    skip_customer_limits=False,
    check_rate_limit=True,
):
    result = AntiAbuseResult()

    if is_customer_blocked(salon, phone, email, instagram):
        return AntiAbuseResult(
            ok=False,
            error_code="blocklist",
            user_message=str(MSG_BLOCKLIST),
        )

    if check_rate_limit and _rate_limit_exceeded(salon.id, policy, ip, phone, email):
        return AntiAbuseResult(
            ok=False,
            error_code="rate_limit",
            user_message=str(MSG_RATE_LIMIT),
        )

    if skip_customer_limits:
        active_qs = _active_future_bookings(salon, phone, email)
        if active_qs.exists():
            result.warnings.append(str(MSG_OWNER_ACTIVE_WARNING))
        return result

    max_pending = _policy_value(policy, "max_pending_bookings_per_customer", 1)
    max_active = _policy_value(policy, "max_active_future_bookings_per_customer", 2)

    active_qs = _active_future_bookings(salon, phone, email)
    customer_ids = get_matching_customer_ids(salon, phone, email)
    unverified_count = 0
    if customer_ids:
        unverified_count = Booking.objects.filter(
            salon=salon,
            customer_id__in=customer_ids,
            status=Booking.Status.UNVERIFIED,
        ).count()

    pending_count = active_qs.filter(status=Booking.Status.PENDING).count() + unverified_count
    active_count = active_qs.count()

    if max_pending and pending_count >= max_pending:
        return AntiAbuseResult(
            ok=False,
            error_code="pending_limit",
            user_message=str(MSG_PENDING_LIMIT),
        )

    if max_active and active_count >= max_active:
        return AntiAbuseResult(
            ok=False,
            error_code="active_limit",
            user_message=str(MSG_ACTIVE_LIMIT),
        )

    return result


def honeypot_triggered(cleaned_value, policy):
    if not _policy_value(policy, "enable_honeypot_protection", True):
        return False
    return bool(cleaned_value and str(cleaned_value).strip())
