"""Central customer blocking logic for owner actions and public booking checks."""

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .anti_abuse import normalize_email, normalize_instagram, normalize_phone
from .models import Booking, Customer, CustomerBlockEvent, CustomerBlocklist

MSG_REASON_REQUIRED = _("Please choose a reason for blocking this customer.")
MSG_ALREADY_BLOCKED = _("This customer is already blocked.")
MSG_NOT_BLOCKED = _("This customer is not currently blocked.")


def _verified_email_for_customer(customer):
    if not customer.email:
        return "", False
    has_verified = customer.bookings.filter(email_verified_at__isnull=False).exists()
    return customer.email, has_verified


def _latest_online_booking(customer):
    return (
        customer.bookings.filter(source=Booking.Source.ONLINE)
        .exclude(client_device_token="")
        .order_by("-created_at")
        .first()
    )


def collect_customer_block_identifiers(customer, booking=None):
    """Gather layered identifiers used when blocking and matching."""
    phone = normalize_phone(customer.phone_number)
    email, email_verified = _verified_email_for_customer(customer)
    instagram = normalize_instagram(customer.instagram_username)

    device_token = ""
    last_known_ip = None
    source_booking = booking

    if booking:
        device_token = (booking.client_device_token or "").strip()
        last_known_ip = booking.client_ip
    else:
        latest = _latest_online_booking(customer)
        if latest:
            device_token = (latest.client_device_token or "").strip()
            last_known_ip = latest.client_ip
            source_booking = latest

    return {
        "phone": phone,
        "email": email,
        "email_verified": email_verified,
        "instagram": instagram,
        "device_token": device_token,
        "last_known_ip": last_known_ip,
        "source_booking": source_booking,
    }


def is_customer_blocked(
    salon,
    phone="",
    email="",
    instagram="",
    device_token="",
):
    """Return True if any active blocklist entry matches the given identifiers."""
    phone = normalize_phone(phone)
    email = normalize_email(email)
    instagram = normalize_instagram(instagram)
    device_token = (device_token or "").strip()

    if not any([phone, email, instagram, device_token]):
        return False

    match = Q()
    if phone:
        match |= Q(phone_number=phone)
    if email:
        match |= Q(email__iexact=email)
    if device_token:
        match |= Q(device_token=device_token)
    if match and CustomerBlocklist.objects.filter(salon=salon, is_active=True).filter(match).exists():
        return True

    if instagram:
        normalized_instagram = normalize_instagram(instagram)
        for entry in CustomerBlocklist.objects.filter(
            salon=salon,
            is_active=True,
        ).exclude(instagram_username="").only("instagram_username"):
            if normalize_instagram(entry.instagram_username) == normalized_instagram:
                return True
    return False


def get_active_block_entry(salon, customer):
    phone = normalize_phone(customer.phone_number)
    if not phone:
        return None
    return CustomerBlocklist.objects.filter(
        salon=salon,
        is_active=True,
        phone_number=phone,
    ).first()


def _log_block_event(entry, event_type, performed_by, reason_code="", notes="", source_booking=None):
    CustomerBlockEvent.objects.create(
        blocklist_entry=entry,
        event_type=event_type,
        performed_by=performed_by,
        reason_code=reason_code or entry.reason_code,
        notes=notes,
        source_booking=source_booking,
    )


def _validate_reason_code(reason_code):
    valid = {choice.value for choice in CustomerBlocklist.ReasonCode}
    if reason_code not in valid:
        raise ValidationError(str(MSG_REASON_REQUIRED))


def block_customer(
    *,
    salon,
    performed_by,
    reason_code,
    notes="",
    customer=None,
    booking=None,
):
    """Block a customer using layered identifiers. Returns the blocklist entry."""
    _validate_reason_code(reason_code)
    notes = (notes or "").strip()

    if booking and not customer:
        customer = booking.customer
    if not customer:
        raise ValidationError(_("Customer not found."))

    if customer.salon_id != salon.id:
        raise ValidationError(_("Customer does not belong to this salon."))

    ids = collect_customer_block_identifiers(customer, booking)
    if not ids["phone"]:
        raise ValidationError(_("A phone number is required to block this customer."))

    reason_label = CustomerBlocklist.ReasonCode(reason_code).label
    combined_reason = str(reason_label)
    if notes:
        combined_reason = f"{combined_reason} — {notes}"

    now = timezone.now()
    entry, created = CustomerBlocklist.objects.get_or_create(
        salon=salon,
        phone_number=ids["phone"],
        defaults={
            "customer": customer,
            "email": ids["email"],
            "email_verified": ids["email_verified"],
            "instagram_username": customer.instagram_username or "",
            "device_token": ids["device_token"],
            "last_known_ip": ids["last_known_ip"],
            "reason_code": reason_code,
            "reason": combined_reason,
            "notes": notes,
            "source_booking": ids["source_booking"],
            "blocked_by": performed_by,
            "blocked_at": now,
            "is_active": True,
        },
    )

    if not created:
        if entry.is_active:
            raise ValidationError(str(MSG_ALREADY_BLOCKED))
        entry.is_active = True
        entry.customer = customer
        entry.email = ids["email"]
        entry.email_verified = ids["email_verified"]
        entry.instagram_username = customer.instagram_username or ""
        entry.device_token = ids["device_token"] or entry.device_token
        entry.last_known_ip = ids["last_known_ip"] or entry.last_known_ip
        entry.reason_code = reason_code
        entry.reason = combined_reason
        entry.notes = notes
        entry.source_booking = ids["source_booking"]
        entry.blocked_by = performed_by
        entry.blocked_at = now
        entry.unblocked_by = None
        entry.unblocked_at = None
        entry.save()

    _log_block_event(
        entry,
        CustomerBlockEvent.EventType.BLOCKED,
        performed_by,
        reason_code=reason_code,
        notes=notes,
        source_booking=ids["source_booking"],
    )
    return entry


def unblock_customer(*, entry, performed_by):
    if not entry.is_active:
        raise ValidationError(str(MSG_NOT_BLOCKED))

    now = timezone.now()
    entry.is_active = False
    entry.unblocked_by = performed_by
    entry.unblocked_at = now
    entry.save(update_fields=["is_active", "unblocked_by", "unblocked_at", "updated_at"])

    _log_block_event(
        entry,
        CustomerBlockEvent.EventType.UNBLOCKED,
        performed_by,
        reason_code=entry.reason_code,
        notes=entry.notes,
    )
    return entry


def update_customer_block(*, entry, performed_by, reason_code, notes=""):
    _validate_reason_code(reason_code)
    notes = (notes or "").strip()
    reason_label = CustomerBlocklist.ReasonCode(reason_code).label
    combined_reason = str(reason_label)
    if notes:
        combined_reason = f"{combined_reason} — {notes}"

    entry.reason_code = reason_code
    entry.notes = notes
    entry.reason = combined_reason
    entry.save(update_fields=["reason_code", "notes", "reason", "updated_at"])

    _log_block_event(
        entry,
        CustomerBlockEvent.EventType.UPDATED,
        performed_by,
        reason_code=reason_code,
        notes=notes,
    )
    return entry


def resolve_customer_for_block(*, salon, customer_id=None, booking_id=None):
    customer = None
    booking = None

    if booking_id:
        booking = Booking.objects.select_related("customer").get(pk=booking_id, salon=salon)
        customer = booking.customer
    elif customer_id:
        customer = Customer.objects.get(pk=customer_id, salon=salon)
    else:
        raise ValidationError(_("Customer or booking is required."))

    return customer, booking


def serialize_blocklist_entry(entry):
    customer = entry.customer
    booking = entry.source_booking
    return {
        "id": entry.id,
        "customer_id": customer.id if customer else None,
        "customer_name": entry.display_name,
        "phone_number": entry.phone_number,
        "email": entry.email or "",
        "instagram_username": entry.instagram_username or "",
        "reason_code": entry.reason_code,
        "reason_label": entry.get_reason_display_label(),
        "notes": entry.notes,
        "is_active": entry.is_active,
        "blocked_at": entry.blocked_at.isoformat() if entry.blocked_at else entry.created_at.isoformat(),
        "blocked_by": (
            entry.blocked_by.get_full_name() or entry.blocked_by.username
            if entry.blocked_by
            else ""
        ),
        "booking_id": booking.id if booking else None,
        "booking_reference": (
            f"#{booking.id} · {timezone.localtime(booking.start_at):%d/%m/%Y %H:%M}"
            if booking
            else ""
        ),
        "status": "active" if entry.is_active else "unblocked",
    }
