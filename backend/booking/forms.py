from datetime import timedelta

from django import forms

from .models import Booking, Customer, Service
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
