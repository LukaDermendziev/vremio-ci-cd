from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from .models import Booking, Customer, Service


class BookingRequestForm(forms.Form):
    service = forms.ModelChoiceField(queryset=Service.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    full_name = forms.CharField(max_length=160, label="Name and surname")
    phone_number = forms.CharField(max_length=30)
    instagram_username = forms.CharField(max_length=80, label="Instagram")
    email = forms.EmailField(required=False)
    preferred_contact_method = forms.ChoiceField(
        choices=Customer.PreferredContactMethod.choices,
        initial=Customer.PreferredContactMethod.VIBER,
    )
    reference_photo = forms.ImageField(required=False)
    rules_accepted = forms.BooleanField(
        required=True,
        label="I accept the salon rules and understand this is only a request.",
    )

    def __init__(self, *args, salon, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.fields["service"].queryset = salon.services.filter(is_active=True)

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

        self.fields["rules_accepted"].widget.attrs["class"] = "form-check-input"

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get("service")
        date = cleaned_data.get("date")
        time = cleaned_data.get("time")

        if service and service.salon_id != self.salon.id:
            self.add_error("service", "Choose a valid service for this salon.")

        if date and time:
            naive_start = datetime.combine(date, time)
            cleaned_data["start_at"] = timezone.make_aware(
                naive_start,
                timezone.get_current_timezone(),
            )

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
        end_at = start_at + timedelta(minutes=service.duration_minutes)
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
            reference_photo=self.cleaned_data.get("reference_photo"),
            rules_accepted=self.cleaned_data["rules_accepted"],
        )
        booking.save()
        booking.booking_services.create(
            service=service,
            service_name_snapshot=service.name,
            duration_minutes_snapshot=service.duration_minutes,
            price_snapshot=service.base_price,
        )

        return booking
