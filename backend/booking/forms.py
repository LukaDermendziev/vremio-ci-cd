from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django import forms
from django.forms import modelformset_factory
from django.utils.translation import gettext_lazy as _

from .models import (
    Booking,
    BookingPolicy,
    Customer,
    DateWorkingHoursOverride,
    Service,
    ServicePriceItem,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import is_slot_available


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
    )
    date = forms.DateField(widget=forms.HiddenInput())
    start_time = forms.CharField(widget=forms.HiddenInput())
    full_name = forms.CharField(max_length=160, label=_("Full name"))
    phone_number = forms.CharField(max_length=30, label=_("Phone number"))
    instagram_username = forms.CharField(max_length=80, label=_("Instagram username"))
    email = forms.EmailField(required=True, label=_("Email"))
    preferred_contact_method = forms.ChoiceField(
        choices=Customer.PreferredContactMethod.choices,
        initial=Customer.PreferredContactMethod.VIBER,
        widget=forms.HiddenInput(),
    )
    customer_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Any notes for the salon..."}),
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
        label=_("I accept the salon rules and understand this is only a request."),
        widget=forms.CheckboxInput(attrs={"class": "bk-rules-hidden"}),
    )

    def __init__(self, *args, salon, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
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
        self.fields["instagram_username"].widget.attrs.update(
            {"placeholder": "@username", "required": "required", "autocomplete": "username"}
        )
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "email@example.com",
                "type": "email",
                "required": "required",
                "autocomplete": "email",
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        date = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")
        price_item_id = cleaned_data.get("selected_price_item_id")

        if service and service.salon_id != self.salon.id:
            self.add_error("service", _("Choose a valid service for this salon."))

        # Validate reference photo size (JS guards first, but backend must also check)
        photo = cleaned_data.get("reference_photo")
        if photo and hasattr(photo, "size") and photo.size > 8 * 1024 * 1024:
            self.add_error("reference_photo", _("Image is too large. Maximum allowed size is 8 MB."))

        # Validate selected price item belongs to the chosen service
        if price_item_id and service:
            try:
                price_item = ServicePriceItem.objects.get(pk=price_item_id, service=service)
                cleaned_data["_price_item"] = price_item
            except ServicePriceItem.DoesNotExist:
                cleaned_data["_price_item"] = None
        else:
            cleaned_data["_price_item"] = None

        if service and date and start_time:
            slot = is_slot_available(self.salon, service, date, start_time)
            if not slot:
                self.add_error(
                    "start_time",
                    _("This time is no longer available. Please choose another slot."),
                )
                return cleaned_data

            cleaned_data["start_at"] = slot["start"]
            cleaned_data["end_at"] = slot["end"]
        elif date or service:
            self.add_error("start_time", _("Please choose an available time."))

        return cleaned_data

    def save(self):
        customer, _created = Customer.objects.update_or_create(
            salon=self.salon,
            phone_number=self.cleaned_data["phone_number"],
            defaults={
                "full_name": self.cleaned_data["full_name"],
                "instagram_username": self.cleaned_data["instagram_username"],
                "email": self.cleaned_data["email"],
                "preferred_contact_method": self.cleaned_data["preferred_contact_method"],
            },
        )

        service = self.cleaned_data["service"]
        price_item = self.cleaned_data.get("_price_item")
        start_at = self.cleaned_data["start_at"]
        end_at = self.cleaned_data.get("end_at") or start_at + timedelta(
            minutes=service.duration_minutes
        )
        policy = getattr(self.salon, "booking_policy", None)
        status = Booking.Status.PENDING

        if policy and policy.auto_approve_bookings:
            status = Booking.Status.APPROVED

        # Use the price item name as snapshot so the booking reflects the exact sub-service
        name_snapshot = price_item.name if price_item else service.name

        booking = Booking(
            salon=self.salon,
            customer=customer,
            status=status,
            start_at=start_at,
            end_at=end_at,
            total_duration_minutes=service.duration_minutes,
            source=Booking.Source.ONLINE,
            reference_photo=self.cleaned_data.get("reference_photo") or "",
            rules_accepted=self.cleaned_data["rules_accepted"],
            customer_note=self.cleaned_data.get("customer_note", ""),
        )
        booking.save()
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
        )

        return booking


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
    service = forms.ModelChoiceField(queryset=Service.objects.none(), label=_("Service"))
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label=_("Date"))
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
        self.fields["service"].queryset = salon.services.filter(is_active=True)

        if booking:
            self.fields["booking_id"].initial = booking.pk
            self.fields["full_name"].initial = booking.customer.full_name
            self.fields["phone_number"].initial = booking.customer.phone_number
            self.fields["instagram_username"].initial = booking.customer.instagram_username
            self.fields["email"].initial = booking.customer.email
            self.fields["preferred_contact_method"].initial = (
                booking.customer.preferred_contact_method
            )
            first_service = booking.booking_services.first()
            if first_service:
                self.fields["service"].initial = first_service.service_id
            self.fields["date"].initial = timezone_localdate(booking.start_at)
            self.fields["start_time"].initial = timezone_localtime(booking.start_at).strftime(
                "%H:%M"
            )
            self.fields["status"].initial = booking.status
            self.fields["source"].initial = booking.source
            self.fields["owner_note"].initial = booking.owner_note

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        date = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")
        exclude_id = cleaned_data.get("booking_id") or None

        if service and service.salon_id != self.salon.id:
            self.add_error("service", _("Choose a valid service for this salon."))

        if service and date and start_time:
            from django.utils import timezone as tz
            import datetime as _dt
            if not exclude_id:
                try:
                    hour, minute = [int(x) for x in start_time.split(":")]
                    naive_dt = _dt.datetime.combine(date, _dt.time(hour, minute))
                    aware_dt = tz.make_aware(naive_dt)
                    if aware_dt < tz.now():
                        self.add_error("start_time", _("Cannot create a booking in the past."))
                        return cleaned_data
                except (ValueError, TypeError):
                    pass

            slot = is_slot_available(
                self.salon,
                service,
                date,
                start_time,
                for_owner=True,
                exclude_booking_id=exclude_id,
            )
            if not slot:
                self.add_error(
                    "start_time",
                    _("This time overlaps another booking or is outside working hours."),
                )
                return cleaned_data

            cleaned_data["start_at"] = slot["start"]
            cleaned_data["end_at"] = slot["end"]

        return cleaned_data

    def save(self):
        customer, _created = Customer.objects.update_or_create(
            salon=self.salon,
            phone_number=self.cleaned_data["phone_number"],
            defaults={
                "full_name": self.cleaned_data["full_name"],
                "instagram_username": self.cleaned_data.get("instagram_username", ""),
                "email": self.cleaned_data.get("email", ""),
                "preferred_contact_method": self.cleaned_data["preferred_contact_method"],
            },
        )

        service = self.cleaned_data["service"]
        start_at = self.cleaned_data["start_at"]
        end_at = self.cleaned_data["end_at"]
        booking_id = self.cleaned_data.get("booking_id")

        if booking_id:
            booking = Booking.objects.get(pk=booking_id, salon=self.salon)
            booking.customer = customer
            booking.status = self.cleaned_data["status"]
            booking.start_at = start_at
            booking.end_at = end_at
            booking.total_duration_minutes = service.duration_minutes
            booking.source = self.cleaned_data["source"]
            booking.owner_note = self.cleaned_data.get("owner_note", "")
            booking.rules_accepted = True
            booking.save()
            booking.booking_services.all().delete()
        else:
            booking = Booking(
                salon=self.salon,
                customer=customer,
                status=self.cleaned_data["status"],
                start_at=start_at,
                end_at=end_at,
                total_duration_minutes=service.duration_minutes,
                source=self.cleaned_data["source"],
                owner_note=self.cleaned_data.get("owner_note", ""),
                rules_accepted=True,
            )
            booking.save()

        booking.booking_services.create(
            service=service,
            service_name_snapshot=service.name,
            duration_minutes_snapshot=service.duration_minutes,
            price_snapshot=service.base_price,
        )
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


class BookingPolicyForm(forms.ModelForm):
    class Meta:
        model = BookingPolicy
        fields = [
            "minimum_notice_days",
            "maximum_booking_window_days",
            "allow_same_day_booking",
            "allow_next_day_booking",
            "auto_approve_bookings",
            "late_arrival_limit_minutes",
            "reminder_hours_before",
            "pending_holds_slot",
            "max_appointments_per_day",
            "slot_interval_minutes",
            "buffer_minutes_between_bookings",
            "customer_cancellation_notice_hours",
            "salon_rules",
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
            "auto_approve_bookings": _("Auto approve bookings"),
            "late_arrival_limit_minutes": _("Late arrival limit minutes"),
            "reminder_hours_before": _("Reminder hours before"),
            "pending_holds_slot": _("Pending holds slot"),
            "max_appointments_per_day": _("Max appointments per day"),
            "slot_interval_minutes": _("Slot interval minutes"),
            "buffer_minutes_between_bookings": _("Buffer minutes between bookings"),
            "customer_cancellation_notice_hours": _("Customer cancellation notice (hours)"),
            "salon_rules": _("Salon rules"),
            "msg_approved": _("Approved message"),
            "msg_rejected": _("Rejected message"),
            "msg_cancelled": _("Cancelled message"),
            "msg_edited": _("Edited/rescheduled message"),
            "msg_no_show": _("No-show message"),
            "msg_pending": _("Pending/received message"),
            "msg_reminder": _("Reminder message"),
        }
        widgets = {
            "salon_rules":   forms.Textarea(attrs={"rows": 5}),
            "msg_approved":  forms.Textarea(attrs={"rows": 3}),
            "msg_rejected":  forms.Textarea(attrs={"rows": 3}),
            "msg_cancelled": forms.Textarea(attrs={"rows": 3}),
            "msg_edited":    forms.Textarea(attrs={"rows": 3}),
            "msg_no_show":   forms.Textarea(attrs={"rows": 3}),
            "msg_pending":   forms.Textarea(attrs={"rows": 3}),
            "msg_reminder":  forms.Textarea(attrs={"rows": 3}),
        }


class UnavailableTimeBlockForm(forms.ModelForm):
    class Meta:
        model = UnavailableTimeBlock
        fields = ["date", "start_time", "end_time", "reason"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "od-input"}),
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
        widget=forms.DateInput(attrs={"type": "date", "class": "od-input"}),
        label="Date",
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
