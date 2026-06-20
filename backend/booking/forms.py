from datetime import timedelta

from django import forms
from django.forms import modelformset_factory

from .models import (
    Booking,
    BookingPolicy,
    Customer,
    DateWorkingHoursOverride,
    Service,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import is_slot_available


class BookingRequestForm(forms.Form):
    service = forms.ModelChoiceField(
        queryset=Service.objects.none(),
        widget=forms.HiddenInput(),
    )
    date = forms.DateField(widget=forms.HiddenInput())
    start_time = forms.CharField(widget=forms.HiddenInput())
    full_name = forms.CharField(max_length=160, label="Full Name")
    phone_number = forms.CharField(max_length=30, label="Phone Number")
    instagram_username = forms.CharField(max_length=80, label="Instagram Username")
    email = forms.EmailField(required=False, label="Email (optional)")
    preferred_contact_method = forms.ChoiceField(
        choices=Customer.PreferredContactMethod.choices,
        initial=Customer.PreferredContactMethod.VIBER,
        widget=forms.HiddenInput(),
    )
    customer_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Any notes for the salon..."}),
        required=False,
        label="Message to salon (optional)",
    )
    reference_photo = forms.ImageField(required=False)
    rules_accepted = forms.BooleanField(
        required=True,
        label="I accept the salon rules and understand this is only a request.",
        widget=forms.CheckboxInput(attrs={"class": "bk-rules-hidden"}),
    )

    def __init__(self, *args, salon, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.fields["service"].queryset = salon.services.filter(is_active=True)

        self.fields["full_name"].widget.attrs["placeholder"] = "Marija Petrovska"
        self.fields["phone_number"].widget.attrs.update(
            {"placeholder": "+389 70 123 456", "type": "tel"}
        )
        self.fields["instagram_username"].widget.attrs["placeholder"] = "@username"
        self.fields["email"].widget.attrs["placeholder"] = "email@example.com"

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        date = cleaned_data.get("date")
        start_time = cleaned_data.get("start_time")

        if service and service.salon_id != self.salon.id:
            self.add_error("service", "Choose a valid service for this salon.")

        if service and date and start_time:
            slot = is_slot_available(self.salon, service, date, start_time)
            if not slot:
                self.add_error(
                    "start_time",
                    "This time is no longer available. Please choose another slot.",
                )
                return cleaned_data

            cleaned_data["start_at"] = slot["start"]
            cleaned_data["end_at"] = slot["end"]
        elif date or service:
            self.add_error("start_time", "Please choose an available time.")

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
        start_at = self.cleaned_data["start_at"]
        end_at = self.cleaned_data.get("end_at") or start_at + timedelta(
            minutes=service.duration_minutes
        )
        policy = getattr(self.salon, "booking_policy", None)
        status = Booking.Status.PENDING

        if policy and policy.auto_approve_bookings:
            status = Booking.Status.APPROVED

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
        booking.booking_services.create(
            service=service,
            service_name_snapshot=service.name,
            duration_minutes_snapshot=service.duration_minutes,
            price_snapshot=service.base_price,
        )

        return booking


class OwnerBookingForm(forms.Form):
    booking_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    full_name = forms.CharField(max_length=160, label="Full name")
    phone_number = forms.CharField(max_length=30, label="Phone")
    instagram_username = forms.CharField(max_length=80, required=False, label="Instagram")
    email = forms.EmailField(required=False, label="Email")
    preferred_contact_method = forms.ChoiceField(
        choices=Customer.PreferredContactMethod.choices,
        initial=Customer.PreferredContactMethod.VIBER,
        label="Preferred contact",
    )
    service = forms.ModelChoiceField(queryset=Service.objects.none(), label="Service")
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Date")
    start_time = forms.CharField(label="Start time")
    status = forms.ChoiceField(choices=Booking.Status.choices, label="Status")
    source = forms.ChoiceField(
        choices=Booking.Source.choices,
        initial=Booking.Source.OWNER_MANUAL,
        label="Source",
    )
    owner_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        label="Owner note",
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
            self.add_error("service", "Choose a valid service for this salon.")

        if service and date and start_time:
            from django.utils import timezone as tz
            import datetime as _dt
            if not exclude_id:
                try:
                    hour, minute = [int(x) for x in start_time.split(":")]
                    naive_dt = _dt.datetime.combine(date, _dt.time(hour, minute))
                    aware_dt = tz.make_aware(naive_dt)
                    if aware_dt < tz.now():
                        self.add_error("start_time", "Cannot create a booking in the past.")
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
                    "This time overlaps another booking or is outside working hours.",
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
            "salon_rules",
            "msg_approved",
            "msg_rejected",
            "msg_cancelled",
            "msg_edited",
            "msg_no_show",
            "msg_pending",
            "msg_reminder",
        ]
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
