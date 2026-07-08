from dataclasses import dataclass, field
import logging
import re

from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Booking, Customer

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = [Booking.Status.PENDING, Booking.Status.APPROVED]

MSG_PENDING_LIMIT = _(
    "You already have a booking request waiting for approval. "
    "Please wait for the salon to respond or cancel your existing request."
)
MSG_PENDING_VERIFY = _(
    "You already started a booking request. Please check your email inbox "
    "(and spam folder) to confirm it before submitting again."
)
MSG_PENDING_VERIFY_SMS = _(
    "You already started a booking request. Please enter the SMS verification code "
    "we sent to your phone before submitting again."
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


def _safe_cache_get(key, default=0):
    try:
        return cache.get(key, default)
    except Exception:
        logger.warning("Cache read failed for %s; skipping rate limit", key, exc_info=True)
        return default


def _safe_cache_set(key, value, timeout):
    try:
        cache.set(key, value, timeout)
    except Exception:
        logger.warning("Cache write failed for %s; booking continues", key, exc_info=True)


def normalize_phone(value):
    """Normalize phone numbers to a comparable local form (07xxxxxxxx for MK mobiles)."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", value.strip())
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("389"):
        local = digits[3:]
        if len(local) == 8 and local.startswith("7"):
            return f"0{local}"
        if len(local) == 9 and local.startswith("07"):
            return local
    if len(digits) == 8 and digits.startswith("7"):
        return f"0{digits}"
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


def phone_lookup_variants(phone):
    """Common stored forms for the same Macedonian mobile number."""
    phone = normalize_phone(phone)
    if not phone:
        return []
    variants = {phone}
    if phone.startswith("0") and len(phone) == 9:
        local = phone[1:]
        variants.add(f"+389{local}")
        variants.add(f"389{local}")
    return list(variants)


def get_matching_customer_ids(salon, phone, email=None):
    """Match customers by normalized phone only (one pending limit per phone number)."""
    phone = normalize_phone(phone)
    if not phone:
        return set()

    matched = set(
        Customer.objects.filter(
            salon=salon,
            phone_number__in=phone_lookup_variants(phone),
        ).values_list("id", flat=True)
    )
    if matched:
        return matched

    for customer in Customer.objects.filter(salon=salon).only("id", "phone_number"):
        if normalize_phone(customer.phone_number) == phone:
            matched.add(customer.id)
    return matched


def _unverified_booking_count(salon, customer_ids):
    if not customer_ids:
        return 0
    now = timezone.now()
    return Booking.objects.filter(
        salon=salon,
        customer_id__in=customer_ids,
        status=Booking.Status.UNVERIFIED,
        verification_expires_at__gt=now,
    ).count()


def _active_future_bookings(salon, phone, email=None):
    customer_ids = get_matching_customer_ids(salon, phone)
    if not customer_ids:
        return Booking.objects.none()

    now = timezone.now()
    return Booking.objects.filter(
        salon=salon,
        customer_id__in=customer_ids,
        status__in=ACTIVE_STATUSES,
        start_at__gte=now,
    )


def is_customer_blocked(salon, phone, email="", instagram="", device_token=""):
    from .customer_blocking import is_customer_blocked as _is_customer_blocked

    return _is_customer_blocked(
        salon,
        phone=phone,
        email=email,
        instagram=instagram,
        device_token=device_token,
    )


def _rate_limit_exceeded(salon_id, policy, ip, phone, email):
    now = timezone.now()
    hour_bucket = now.strftime("%Y%m%d%H")
    day_bucket = now.strftime("%Y%m%d")

    ip_limit = _policy_value(policy, "booking_rate_limit_per_ip_per_hour", 5)
    email_limit = _policy_value(policy, "booking_rate_limit_per_email_per_day", 3)
    phone_limit = _policy_value(policy, "booking_rate_limit_per_phone_per_day", 3)

    if ip and ip_limit:
        key = f"booking_rate:ip:{salon_id}:{ip}:{hour_bucket}"
        if _safe_cache_get(key, 0) >= ip_limit:
            return True

    email = normalize_email(email)
    if email and email_limit:
        key = f"booking_rate:email:{salon_id}:{email}:{day_bucket}"
        if _safe_cache_get(key, 0) >= email_limit:
            return True

    phone = normalize_phone(phone)
    if phone and phone_limit:
        key = f"booking_rate:phone:{salon_id}:{phone}:{day_bucket}"
        if _safe_cache_get(key, 0) >= phone_limit:
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
        _safe_cache_set(key, _safe_cache_get(key, 0) + 1, ttl_hour)

    email = normalize_email(email)
    if email:
        key = f"booking_rate:email:{salon_id}:{email}:{day_bucket}"
        _safe_cache_set(key, _safe_cache_get(key, 0) + 1, ttl_day)

    phone = normalize_phone(phone)
    if phone:
        key = f"booking_rate:phone:{salon_id}:{phone}:{day_bucket}"
        _safe_cache_set(key, _safe_cache_get(key, 0) + 1, ttl_day)

    if device_token and ip:
        key = f"booking_rate:device:{salon_id}:{device_token}:{ip}:{hour_bucket}"
        _safe_cache_set(key, _safe_cache_get(key, 0) + 1, ttl_hour)


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

    if is_customer_blocked(salon, phone, email, instagram, device_token):
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
    customer_ids = get_matching_customer_ids(salon, phone)
    unverified_count = _unverified_booking_count(salon, customer_ids)

    pending_active = active_qs.filter(status=Booking.Status.PENDING).count()
    pending_count = pending_active + unverified_count
    active_count = active_qs.count()

    if max_pending and pending_count >= max_pending:
        if unverified_count and not pending_active:
            if policy and policy.sms_verification_required:
                user_message = str(MSG_PENDING_VERIFY_SMS)
            else:
                user_message = str(MSG_PENDING_VERIFY)
        else:
            user_message = str(MSG_PENDING_LIMIT)
        return AntiAbuseResult(
            ok=False,
            error_code="pending_limit",
            user_message=user_message,
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
