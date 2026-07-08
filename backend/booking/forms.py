from datetime import timedelta
from decimal import Decimal, InvalidOperation
import json
import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory
from django.forms.models import construct_instance
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .anti_abuse import (
    MSG_GENERIC_INVALID,
    check_public_booking_allowed,
    get_client_ip,
    get_device_token,
    honeypot_triggered,
    normalize_phone,
)
from .image_moderation import moderate_reference_photo
from .image_utils import FORMAT_TO_EXT, prepare_reference_photo, validate_reference_photo
from .models import (
    Booking,
    BookingPolicy,
    Customer,
    DateWorkingHoursOverride,
    Salon,
    Service,
    ServicePriceItem,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import (
    MSG_MULTI_SERVICE_NO_FIT,
    calculate_combined_duration_minutes,
    consume_released_slot,
    get_salon_timezone,
    is_slot_available,
    parse_fixed_start_times_text,
    release_timeslot,
    resolve_services_for_salon,
)


class LocalizedDateInput(forms.DateInput):
    """Text date field (dd/mm/yyyy) with hidden ISO value for Django."""

    input_type = "text"

    def __init__(self, attrs=None, format=None):
        attrs = dict(attrs or {})
        attrs.setdefault("class", "od-input od-date-display")
        super().__init__(attrs=attrs, format=format)

    def render(self, name, value, attrs=None, renderer=None):
        iso_value = ""
        if value:
            if hasattr(value, "strftime"):
                iso_value = value.strftime("%Y-%m-%d")
            else:
                iso_value = str(value)
        field_id = (attrs or {}).get("id") or f"id_{name}"
        required = "required" in (attrs or {}) or (self.attrs or {}).get("required")
        return format_html(
            '<div class="od-date-wrap" data-od-date-field>'
            '<div class="od-date-input-row">'
            '<input type="text" class="od-input od-date-display" placeholder="{placeholder}" '
            'inputmode="numeric" autocomplete="off" aria-labelledby="{field_id}_label" {req}>'
            '<button type="button" class="od-date-picker-btn" aria-label="{choose}">'
            '<i class="bi bi-calendar3"></i></button>'
            "</div>"
            '<input type="hidden" name="{name}" id="{field_id}" class="od-date-value" value="{iso}">'
            '<input type="date" class="od-date-native" tabindex="-1" aria-hidden="true">'
            "</div>",
            placeholder=_("dd/mm/yyyy"),
            choose=_("Choose date"),
            name=name,
            field_id=field_id,
            iso=iso_value,
            req=format_html("required") if required else "",
        )


def _price_from_display(price_display: str, base_price: Decimal) -> Decimal:
    """
    Derive a numeric price_snapshot from a ServicePriceItem.price_display string.

    Rules:
      "+100"        → base_price + 100   (addon)
      "+100/200"    → base_price + 100   (smallest addon in a range)
      "1000"        → 1000               (fixed price)
      "1500-2000"   → 1500               (lower bound of a range)
      anything else → base_price         (fallback)
    """
    if not price_display:
        return base_price
    p = price_display.strip().replace(",", ".")
    try:
        if p.startswith("+"):
            first = p[1:].split("/")[0].split("-")[0].strip()
            return base_price + Decimal(first)
        first = p.split("/")[0].split("-")[0].strip()
        return Decimal(first)
    except (InvalidOperation, ValueError):
        return base_price


class BookingRequestForm(forms.Form):
    service = forms.ModelChoiceField(
        queryset=Service.objects.none(),
        widget=forms.HiddenInput(),
        required=False,
    )
    service_ids = forms.CharField(required=False, widget=forms.HiddenInput())
    service_price_items = forms.CharField(required=False, widget=forms.HiddenInput())
    date = forms.DateField(widget=forms.HiddenInput())
    start_time = forms.CharField(widget=forms.HiddenInput())
    full_name = forms.CharField(max_length=160, label=_("Full name"))
    phone_number = forms.CharField(max_length=30, label=_("Phone number"))
    email = forms.EmailField(required=False, label=_("Email"))
    preferred_contact_method = forms.ChoiceField(
        choices=Customer.PreferredContactMethod.choices,
        initial=Customer.PreferredContactMethod.VIBER,
        widget=forms.HiddenInput(),
    )
    customer_note = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 2, "placeholder": _("Any notes for the salon...")}
        ),
        required=False,
        label=_("Message to salon (optional)"),
    )
    reference_photo = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/jpg,image/png,image/webp',
        }),
    )
    selected_price_item_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    rules_accepted = forms.BooleanField(
        required=True,
        label=_("I have read, understood, and agree to all rules and policies."),
        widget=forms.CheckboxInput(attrs={"class": "bk-rules-hidden"}),
    )
    company_website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "bk-honeypot",
                "tabindex": "-1",
                "autocomplete": "off",
            }
        ),
    )

    def __init__(self, *args, salon, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.request = request
        self.policy = getattr(salon, "booking_policy", None)
        self.customer_warnings = []
        self.uses_sms_verification = bool(self.policy and self.policy.sms_verification_required)
        self.uses_email_verification = bool(
            self.policy
            and self.policy.email_verification_required
            and not self.uses_sms_verification
        )
        self.fields["service"].queryset = salon.services.filter(is_active=True)

        self.fields["full_name"].widget.attrs.update(
            {"placeholder": "Marija Petrovska", "required": "required", "autocomplete": "name"}
        )
        self.fields["phone_number"].widget.attrs.update(
            {
                "placeholder": "+389 70 123 456",
                "type": "tel",
                "required": "required",
                "autocomplete": "tel",
            }
        )
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "email@example.com",
                "type": "email",
                "autocomplete": "email",
            }
        )
        if self.uses_sms_verification:
            self.fields["email"].required = False
        else:
            self.fields["email"].required = True
            self.fields["email"].widget.attrs["required"] = "required"

    def _parse_service_ids(self, cleaned_data):
        raw = (cleaned_data.get("service_ids") or "").strip()
        if raw:
            ids = []
            for part in raw.split(","):
                part = part.strip()
                if part.isdigit():
                    ids.append(int(part))
            return ids
        service = cleaned_data.get("service")
        if service:
            return [service.pk]
        return []

    def _parse_price_items_map(self, cleaned_data):
        raw = (cleaned_data.get("service_price_items") or "").strip()
        if not raw:
            price_item_id = cleaned_data.get("selected_price_item_id")
            service = cleaned_data.get("service")
            if price_item_id and service:
                return {str(service.pk): int(price_item_id)}
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): v for k, v in data.items() if v}

    def clean(self):
        cleaned_data = super().clean()
        service_ids = self._parse_service_ids(cleaned_data)
        services = resolve_services_for_salon(self.salon, service_ids)
        price_items_map = self._parse_price_items_map(cleaned_data)
        date = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")
        phone = cleaned_data.get("phone_number", "")
        email = (cleaned_data.get("email") or "").strip()
        cleaned_data["email"] = email
        if not self.uses_sms_verification and not email:
            self.add_error("email", _("Please enter your email address."))
            return cleaned_data
        if honeypot_triggered(cleaned_data.get("company_website"), self.policy):
            self.add_error(None, str(MSG_GENERIC_INVALID))
            return cleaned_data

        ip = get_client_ip(self.request)
        device_token = get_device_token(self.request)
        abuse_result = check_public_booking_allowed(
            self.salon,
            self.policy,
            phone=phone,
            email=email,
            instagram="",
            ip=ip,
            device_token=device_token,
            check_rate_limit=True,
        )
        if not abuse_result.ok:
            self.add_error(None, abuse_result.user_message)
            return cleaned_data

        if not services:
            self.add_error(None, _("Please choose at least one service."))
            return cleaned_data

        cleaned_data["_services"] = services
        line_items = []
        photo_required = False
        for service in services:
            price_item = None
            price_item_id = price_items_map.get(str(service.pk))
            if price_item_id:
                try:
                    price_item = ServicePriceItem.objects.get(pk=int(price_item_id), service=service)
                except (ServicePriceItem.DoesNotExist, TypeError, ValueError):
                    self.add_error(None, _("Choose a valid service for this salon."))
                    return cleaned_data
            if service.requires_photo or (price_item and price_item.photo_required):
                photo_required = True
            line_items.append({"service": service, "price_item": price_item})
        cleaned_data["_line_items"] = line_items

        photo = cleaned_data.get("reference_photo")
        if photo_required and not photo:
            self.add_error(
                "reference_photo",
                _("A reference photo is required for this service."),
            )
        elif photo:
            max_size_mb = getattr(self.policy, "max_reference_photo_size_mb", 5) if self.policy else 5
            try:
                image_format = validate_reference_photo(photo, max_size_mb=max_size_mb)
            except ValidationError as exc:
                self.add_error("reference_photo", exc.messages[0])
            else:
                cleaned_data["_photo_format"] = image_format

        if services and date and start_time:
            slot = is_slot_available(self.salon, services, date, start_time)
            if not slot:
                if len(services) > 1:
                    self.add_error("start_time", str(MSG_MULTI_SERVICE_NO_FIT))
                else:
                    self.add_error(
                        "start_time",
                        _("This time is no longer available. Please choose another slot."),
                    )
                return cleaned_data

            cleaned_data["start_at"] = slot["start"]
            cleaned_data["end_at"] = slot["end"]
        elif date or services:
            self.add_error("start_time", _("Please choose an available time."))

        return cleaned_data

    def save(self):
        phone = normalize_phone(self.cleaned_data["phone_number"])
        customer, _created = Customer.objects.update_or_create(
            salon=self.salon,
            phone_number=phone,
            defaults={
                "full_name": self.cleaned_data["full_name"],
                "email": (self.cleaned_data.get("email") or "").strip(),
                "preferred_contact_method": self.cleaned_data["preferred_contact_method"],
            },
        )

        line_items = self.cleaned_data["_line_items"]
        services = self.cleaned_data["_services"]
        start_at = self.cleaned_data["start_at"]
        end_at = self.cleaned_data.get("end_at") or start_at + timedelta(
            minutes=calculate_combined_duration_minutes(services, self.salon)
        )
        policy = self.policy
        needs_sms_verification = bool(policy and policy.sms_verification_required)
        needs_email_verification = bool(
            policy and policy.email_verification_required and not needs_sms_verification
        )
        needs_verification = needs_sms_verification or needs_email_verification
        if needs_verification:
            status = Booking.Status.UNVERIFIED
        else:
            status = Booking.Status.PENDING
            if policy and policy.auto_approve_bookings:
                status = Booking.Status.APPROVED

        booking = Booking(
            salon=self.salon,
            customer=customer,
            status=status,
            start_at=start_at,
            end_at=end_at,
            total_duration_minutes=calculate_combined_duration_minutes(services, self.salon),
            source=Booking.Source.ONLINE,
            rules_accepted=self.cleaned_data["rules_accepted"],
            customer_note=self.cleaned_data.get("customer_note", ""),
            client_device_token=get_device_token(self.request),
            client_ip=get_client_ip(self.request) or None,
        )

        if needs_email_verification:
            booking.email_verification_token = uuid.uuid4()
            booking.verification_expires_at = timezone.now() + timedelta(
                minutes=policy.email_verification_expiration_minutes
            )
        elif needs_sms_verification:
            booking.verification_expires_at = timezone.now() + timedelta(
                minutes=policy.sms_verification_expiration_minutes
            )

        photo = self.cleaned_data.get("reference_photo")
        photo_format = self.cleaned_data.get("_photo_format")
        if photo and photo_format:
            moderation = moderate_reference_photo(photo)
            if not moderation.allowed:
                raise ValidationError({"reference_photo": moderation.message})
            prepared = prepare_reference_photo(photo, photo_format)
            booking._reference_photo_ext = FORMAT_TO_EXT.get(photo_format, "jpg")
            booking.reference_photo = prepared
            booking.reference_photo_status = Booking.ReferencePhotoStatus.UNREVIEWED

        booking.save()
        for sort_order, line in enumerate(line_items):
            service = line["service"]
            price_item = line["price_item"]
            name_snapshot = price_item.name if price_item else service.name
            price_snap = (
                _price_from_display(price_item.price_display, service.base_price)
                if price_item
                else service.base_price
            )
            booking.booking_services.create(
                service=service,
                service_name_snapshot=name_snapshot,
                duration_minutes_snapshot=service.duration_minutes,
                price_snapshot=price_snap,
                sort_order=sort_order,
            )

        if not needs_verification:
            consume_released_slot(self.salon, start_at, end_at)
        self.verification_required = needs_verification
        self.sms_verification_required = needs_sms_verification
        self.email_verification_required = needs_email_verification
        return booking


class BookingSmsOtpForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        label=_("Verification code"),
        widget=forms.TextInput(
            attrs={
                "class": "bk-input bk-otp-input",
                "inputmode": "numeric",
                "pattern": "[0-9]{6}",
                "autocomplete": "one-time-code",
                "placeholder": "000000",
            }
        ),
    )


class OwnerBookingForm(forms.Form):
    booking_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    full_name = forms.CharField(max_length=160, label=_("Full name"))
    phone_number = forms.CharField(max_length=30, label=_("Phone"))
    instagram_username = forms.CharField(max_length=80, required=False, label=_("Instagram"))
    email = forms.EmailField(required=False, label=_("Email"))
    preferred_contact_method = forms.ChoiceField(
        choices=Customer.PreferredContactMethod.choices,
        initial=Customer.PreferredContactMethod.VIBER,
        label=_("Preferred contact"),
    )
    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.none(),
        label=_("Services"),
        widget=forms.CheckboxSelectMultiple(attrs={"class": "od-service-checks"}),
    )
    date = forms.DateField(widget=LocalizedDateInput(), label=_("Date"))
    start_time = forms.CharField(label=_("Start time"))
    status = forms.ChoiceField(choices=Booking.Status.choices, label=_("Status"))
    source = forms.ChoiceField(
        choices=Booking.Source.choices,
        initial=Booking.Source.OWNER_MANUAL,
        label=_("Source"),
    )
    owner_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label=_("Owner note"),
    )

    def __init__(self, *args, salon, booking=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.booking = booking
        self.policy = getattr(salon, "booking_policy", None)
        self.customer_warnings = []
        self.fields["services"].queryset = salon.services.filter(is_active=True)

        if booking:
            self.fields["booking_id"].initial = booking.pk
            self.fields["full_name"].initial = booking.customer.full_name
            self.fields["phone_number"].initial = booking.customer.phone_number
            self.fields["instagram_username"].initial = booking.customer.instagram_username
            self.fields["email"].initial = booking.customer.email
            self.fields["preferred_contact_method"].initial = (
                booking.customer.preferred_contact_method
            )
            self.fields["services"].initial = list(
                booking.booking_services.values_list("service_id", flat=True)
            )
            self.fields["date"].initial = timezone_localdate(booking.start_at)
            self.fields["start_time"].initial = timezone_localtime(booking.start_at).strftime(
                "%H:%M"
            )
            self.fields["status"].initial = booking.status
            self.fields["source"].initial = booking.source
            self.fields["owner_note"].initial = booking.owner_note

    def clean(self):
        cleaned_data = super().clean()
        services = list(cleaned_data.get("services") or [])
        date = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")
        exclude_id = cleaned_data.get("booking_id") or None

        if not services:
            self.add_error("services", _("Please choose at least one service."))
            return cleaned_data

        if any(service.salon_id != self.salon.id for service in services):
            self.add_error("services", _("Choose valid services for this salon."))

        if services and date and start_time:
            import datetime as _dt

            if not exclude_id:
                try:
                    hour, minute = [int(x) for x in start_time.split(":")]
                    salon_tz = get_salon_timezone(self.salon)
                    naive_dt = _dt.datetime.combine(date, _dt.time(hour, minute))
                    aware_dt = timezone.make_aware(naive_dt, salon_tz)
                    if aware_dt < timezone.now():
                        self.add_error("start_time", _("Cannot create a booking in the past."))
                        return cleaned_data
                except (ValueError, TypeError):
                    pass

            slot = is_slot_available(
                self.salon,
                services,
                date,
                start_time,
                for_owner=True,
                exclude_booking_id=exclude_id,
            )
            if not slot:
                if len(services) > 1:
                    self.add_error("start_time", str(MSG_MULTI_SERVICE_NO_FIT))
                else:
                    self.add_error(
                        "start_time",
                        _("This time overlaps another booking or is outside working hours."),
                    )
                return cleaned_data

            cleaned_data["start_at"] = slot["start"]
            cleaned_data["end_at"] = slot["end"]
            cleaned_data["_services"] = services

        phone = cleaned_data.get("phone_number", "")
        email = cleaned_data.get("email", "")
        instagram = cleaned_data.get("instagram_username", "")
        abuse_result = check_public_booking_allowed(
            self.salon,
            self.policy,
            phone=phone,
            email=email,
            instagram=instagram,
            skip_customer_limits=True,
            check_rate_limit=False,
        )
        self.customer_warnings = abuse_result.warnings

        return cleaned_data

    def save(self):
        phone = normalize_phone(self.cleaned_data["phone_number"])
        customer, _created = Customer.objects.update_or_create(
            salon=self.salon,
            phone_number=phone,
            defaults={
                "full_name": self.cleaned_data["full_name"],
                "instagram_username": self.cleaned_data.get("instagram_username", ""),
                "email": self.cleaned_data.get("email", ""),
                "preferred_contact_method": self.cleaned_data["preferred_contact_method"],
            },
        )

        services = self.cleaned_data["_services"]
        start_at = self.cleaned_data["start_at"]
        end_at = self.cleaned_data["end_at"]
        total_duration = calculate_combined_duration_minutes(services, self.salon)
        booking_id = self.cleaned_data.get("booking_id")

        if booking_id:
            booking = Booking.objects.get(pk=booking_id, salon=self.salon)
            old_start = booking.start_at
            old_end = booking.end_at
            booking.customer = customer
            booking.status = self.cleaned_data["status"]
            booking.start_at = start_at
            booking.end_at = end_at
            booking.total_duration_minutes = total_duration
            booking.source = self.cleaned_data["source"]
            booking.owner_note = self.cleaned_data.get("owner_note", "")
            booking.rules_accepted = True
            booking.save()
            booking.booking_services.all().delete()
            if (old_start, old_end) != (start_at, end_at):
                release_timeslot(
                    self.salon,
                    old_start,
                    old_end,
                    source_booking=booking,
                )
        else:
            booking = Booking(
                salon=self.salon,
                customer=customer,
                status=self.cleaned_data["status"],
                start_at=start_at,
                end_at=end_at,
                total_duration_minutes=total_duration,
                source=self.cleaned_data["source"],
                owner_note=self.cleaned_data.get("owner_note", ""),
                rules_accepted=True,
            )
            booking.save()

        for sort_order, service in enumerate(services):
            booking.booking_services.create(
                service=service,
                service_name_snapshot=service.name,
                duration_minutes_snapshot=service.duration_minutes,
                price_snapshot=service.base_price,
                sort_order=sort_order,
            )
        consume_released_slot(self.salon, start_at, end_at)
        return booking


def timezone_localdate(dt):
    from django.utils import timezone

    return timezone.localtime(dt).date()


def timezone_localtime(dt):
    from django.utils import timezone

    return timezone.localtime(dt)


class WorkingHoursRowForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = ["weekday", "is_working_day", "start_time", "end_time"]
        widgets = {
            "weekday": forms.HiddenInput(),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "od-input"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "od-input"}),
        }


WorkingHoursFormSet = modelformset_factory(
    WorkingHours,
    form=WorkingHoursRowForm,
    extra=0,
    can_delete=False,
)


class SalonPublicHoursDisplayForm(forms.ModelForm):
    class Meta:
        model = Salon
        fields = ["public_hours_end_display"]
        labels = {
            "public_hours_end_display": _("Public page closing time"),
        }
        help_texts = {
            "public_hours_end_display": _(
                "Leave empty to show the same end time as working hours. "
                "Booking availability is not affected."
            ),
        }
        widgets = {
            "public_hours_end_display": forms.TimeInput(
                attrs={"type": "time", "class": "od-input"},
            ),
        }


class ExplicitBooleanCheckboxInput(forms.CheckboxInput):
    """Always submit a value: hidden false + checkbox on (no JS required)."""

    def render(self, name, value, attrs=None, renderer=None):
        hidden = format_html('<input type="hidden" name="{}" value="false">', name)
        checkbox = super().render(name, value, attrs, renderer)
        return mark_safe(hidden + checkbox)


class BookingPolicyForm(forms.ModelForm):
    POLICY_CHECKBOX_FIELDS = (
        "allow_same_day_booking",
        "allow_next_day_booking",
        "allow_last_minute_reopen",
        "auto_approve_bookings",
        "pending_holds_slot",
        "use_fixed_start_times",
        "enable_honeypot_protection",
        "email_verification_required",
        "sms_verification_required",
        "sms_notifications_enabled",
    )

    fixed_start_times_text = forms.CharField(
        required=False,
        label=_("Fixed start times"),
        help_text=_(
            "Comma-separated HH:MM times (e.g. 08:00, 10:30, 13:00, 15:30). "
            "Used only when fixed start times mode is on; slot interval is ignored."
        ),
        widget=forms.TextInput(
            attrs={
                "class": "od-input",
                "placeholder": "08:00, 10:30, 13:00, 15:30",
            }
        ),
    )

    class Meta:
        model = BookingPolicy
        fields = [
            "minimum_notice_days",
            "maximum_booking_window_days",
            "allow_same_day_booking",
            "allow_next_day_booking",
            "allow_last_minute_reopen",
            "auto_approve_bookings",
            "late_arrival_limit_minutes",
            "reminder_hours_before",
            "pending_holds_slot",
            "max_appointments_per_day",
            "use_fixed_start_times",
            "slot_interval_minutes",
            "buffer_minutes_between_bookings",
            "service_gap_minutes",
            "customer_cancellation_notice_hours",
            "max_pending_bookings_per_customer",
            "max_active_future_bookings_per_customer",
            "booking_rate_limit_per_ip_per_hour",
            "booking_rate_limit_per_email_per_day",
            "booking_rate_limit_per_phone_per_day",
            "enable_honeypot_protection",
            "max_reference_photo_size_mb",
            "email_verification_required",
            "email_verification_expiration_minutes",
            "sms_verification_required",
            "sms_verification_expiration_minutes",
            "sms_notifications_enabled",
            "salon_rules",
            "salon_rules_en",
            "msg_approved",
            "msg_rejected",
            "msg_cancelled",
            "msg_edited",
            "msg_no_show",
            "msg_pending",
            "msg_reminder",
        ]
        labels = {
            "minimum_notice_days": _("Minimum notice days"),
            "maximum_booking_window_days": _("Maximum booking window days"),
            "allow_same_day_booking": _("Allow same day booking"),
            "allow_next_day_booking": _("Allow next day booking"),
            "allow_last_minute_reopen": _("Reopen cancelled slots inside notice window"),
            "auto_approve_bookings": _("Auto approve bookings"),
            "late_arrival_limit_minutes": _("Late arrival limit minutes"),
            "reminder_hours_before": _("Reminder hours before"),
            "pending_holds_slot": _("Pending holds slot"),
            "max_appointments_per_day": _("Max appointments per day"),
            "use_fixed_start_times": _("Use fixed start times"),
            "slot_interval_minutes": _("Slot interval minutes"),
            "buffer_minutes_between_bookings": _("Buffer minutes between bookings"),
            "service_gap_minutes": _("Gap between services in same booking (minutes)"),
            "customer_cancellation_notice_hours": _("Customer cancellation notice (hours)"),
            "max_pending_bookings_per_customer": _("Max pending bookings per customer"),
            "max_active_future_bookings_per_customer": _("Max active future bookings per customer"),
            "booking_rate_limit_per_ip_per_hour": _("Booking rate limit per IP per hour"),
            "booking_rate_limit_per_email_per_day": _("Booking rate limit per email per day"),
            "booking_rate_limit_per_phone_per_day": _("Booking rate limit per phone per day"),
            "enable_honeypot_protection": _("Enable honeypot protection"),
            "max_reference_photo_size_mb": _("Max reference photo size (MB)"),
            "email_verification_required": _("Require email verification for online bookings"),
            "email_verification_expiration_minutes": _("Email verification link expiry (minutes)"),
            "sms_verification_required": _("Require SMS verification for online bookings"),
            "sms_verification_expiration_minutes": _("SMS verification code expiry (minutes)"),
            "sms_notifications_enabled": _("Send transactional SMS to customers"),
            "salon_rules": _("Salon rules (Macedonian)"),
            "salon_rules_en": _("Salon rules (English)"),
            "msg_approved": _("Approved message"),
            "msg_rejected": _("Rejected message"),
            "msg_cancelled": _("Cancelled message"),
            "msg_edited": _("Edited/rescheduled message"),
            "msg_no_show": _("No-show message"),
            "msg_pending": _("Pending/received message"),
            "msg_reminder": _("Reminder message"),
        }
        widgets = {
            "salon_rules":    forms.Textarea(attrs={"rows": 5}),
            "salon_rules_en": forms.Textarea(attrs={"rows": 5}),
            "msg_approved":  forms.Textarea(attrs={"rows": 3}),
            "msg_rejected":  forms.Textarea(attrs={"rows": 3}),
            "msg_cancelled": forms.Textarea(attrs={"rows": 3}),
            "msg_edited":    forms.Textarea(attrs={"rows": 3}),
            "msg_no_show":   forms.Textarea(attrs={"rows": 3}),
            "msg_pending":   forms.Textarea(attrs={"rows": 3}),
            "msg_reminder":  forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.POLICY_CHECKBOX_FIELDS:
            self.fields[field_name].required = False
            self.fields[field_name].widget = ExplicitBooleanCheckboxInput()
        self.fields["email_verification_expiration_minutes"].required = False
        self.fields["sms_verification_expiration_minutes"].required = False
        if self.instance and self.instance.pk:
            times = self.instance.fixed_start_times or []
            if isinstance(times, list) and times:
                joined = ", ".join(times)
                self.fields["fixed_start_times_text"].initial = joined
                if not self.is_bound:
                    self.fields["fixed_start_times_text"].widget.attrs["value"] = joined

    def clean(self):
        cleaned_data = super().clean()
        for field_name in self.POLICY_CHECKBOX_FIELDS:
            cleaned_data[field_name] = coerce_checkbox_value(
                cleaned_data.get(field_name)
            )

        use_fixed = cleaned_data.get("use_fixed_start_times")
        text = cleaned_data.get("fixed_start_times_text", "")
        try:
            parsed_times = parse_fixed_start_times_text(text)
        except ValueError as exc:
            self.add_error("fixed_start_times_text", str(exc))
            parsed_times = []
        if use_fixed and not parsed_times and self.instance and self.instance.pk:
            existing = self.instance.fixed_start_times or []
            if isinstance(existing, list) and existing:
                parsed_times = list(existing)
        if use_fixed and not parsed_times:
            self.add_error(
                "fixed_start_times_text",
                _("Add at least one fixed start time."),
            )
        expiry = cleaned_data.get("email_verification_expiration_minutes")
        if expiry in (None, ""):
            if self.instance and self.instance.pk:
                cleaned_data["email_verification_expiration_minutes"] = (
                    self.instance.email_verification_expiration_minutes
                )
            else:
                cleaned_data["email_verification_expiration_minutes"] = 60
        sms_expiry = cleaned_data.get("sms_verification_expiration_minutes")
        if sms_expiry in (None, ""):
            if self.instance and self.instance.pk:
                cleaned_data["sms_verification_expiration_minutes"] = (
                    self.instance.sms_verification_expiration_minutes
                )
            else:
                cleaned_data["sms_verification_expiration_minutes"] = 10
        if cleaned_data.get("sms_verification_required"):
            cleaned_data["email_verification_required"] = False
        elif cleaned_data.get("email_verification_required"):
            cleaned_data["sms_verification_required"] = False
        cleaned_data["_parsed_fixed_start_times"] = parsed_times
        return cleaned_data

    def _post_clean(self):
        if self.errors:
            return
        opts = self._meta
        exclude = self._get_validation_exclusions()
        self.instance = construct_instance(
            self, self.instance, opts.fields, opts.exclude
        )
        parsed_times = self.cleaned_data.get("_parsed_fixed_start_times", [])
        if self.cleaned_data.get("use_fixed_start_times"):
            self.instance.fixed_start_times = parsed_times
        else:
            self.instance.fixed_start_times = []
        try:
            self.instance.full_clean(exclude=exclude, validate_unique=False)
        except ValidationError as exc:
            error_dict = getattr(exc, "error_dict", None) or {}
            if "fixed_start_times" in error_dict:
                for error in error_dict["fixed_start_times"]:
                    self.add_error("fixed_start_times_text", error)
                other = {
                    key: value
                    for key, value in error_dict.items()
                    if key != "fixed_start_times"
                }
                if other:
                    self.add_error(None, ValidationError(other))
                return
            self._update_errors(exc)

    def save(self, commit=True):
        instance = super().save(commit=False)
        parsed_times = self.cleaned_data.get("_parsed_fixed_start_times", [])
        if self.cleaned_data.get("use_fixed_start_times"):
            instance.fixed_start_times = parsed_times
        else:
            instance.fixed_start_times = []
        if commit:
            instance.save()
        return instance


def coerce_checkbox_value(value):
    if value is True:
        return True
    if value in (False, None, ""):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "on", "yes"}
    return bool(value)


def normalize_policy_post_data(post):
    """Unchecked HTML checkboxes are omitted from POST; make toggles explicit."""
    data = post.copy()
    for field_name in BookingPolicyForm.POLICY_CHECKBOX_FIELDS:
        if field_name not in data:
            data[field_name] = "false"
    return data


class UnavailableTimeBlockForm(forms.ModelForm):
    class Meta:
        model = UnavailableTimeBlock
        fields = ["date", "start_time", "end_time", "reason"]
        widgets = {
            "date": LocalizedDateInput(),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "od-input"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "od-input"}),
            "reason": forms.TextInput(
                attrs={"class": "od-input", "placeholder": "Optional reason"}
            ),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_time")
        end = cleaned_data.get("end_time")
        if start and end and end <= start:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.salon:
            instance.salon = self.salon
        if commit:
            instance.save()
        return instance


class BlockedDateForm(forms.Form):
    override_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    date = forms.DateField(
        widget=LocalizedDateInput(),
        label=_("Date"),
    )
    reason = forms.CharField(
        required=False,
        max_length=255,
        label="Reason",
        widget=forms.TextInput(attrs={"class": "od-input", "placeholder": "Optional reason"}),
    )


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "name",
            "description",
            "duration_minutes",
            "base_price",
            "is_active",
            "requires_photo",
            "photo_recommended",
            "extra_duration_note",
            "sort_order",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "od-input"}),
            "description": forms.Textarea(attrs={"class": "od-input", "rows": 2}),
            "duration_minutes": forms.NumberInput(attrs={"class": "od-input"}),
            "base_price": forms.NumberInput(attrs={"class": "od-input", "step": "0.01"}),
            "extra_duration_note": forms.TextInput(attrs={"class": "od-input"}),
            "sort_order": forms.NumberInput(attrs={"class": "od-input"}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.salon and not instance.salon_id:
            instance.salon = self.salon
        if commit:
            instance.save()
        return instance


class OwnerCustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "full_name",
            "phone_number",
            "instagram_username",
            "email",
            "preferred_contact_method",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "od-input"}),
            "phone_number": forms.TextInput(attrs={"class": "od-input", "type": "tel"}),
            "instagram_username": forms.TextInput(attrs={"class": "od-input"}),
            "email": forms.EmailInput(attrs={"class": "od-input"}),
            "preferred_contact_method": forms.Select(attrs={"class": "od-input"}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.salon:
            instance.salon = self.salon
        if commit:
            instance.save()
        return instance
