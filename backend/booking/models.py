from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Salon(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="salons",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    phone_number = models.CharField(max_length=30, blank=True)
    instagram_username = models.CharField(max_length=80, blank=True)
    address = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=64, default="Europe/Skopje")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Service(TimeStampedModel):
    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="services",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveSmallIntegerField(
        default=120,
        validators=[MinValueValidator(1)],
    )
    base_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    requires_photo = models.BooleanField(default=False)
    photo_recommended = models.BooleanField(default=False)
    extra_duration_note = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "name"],
                name="unique_service_name_per_salon",
            )
        ]

    def __str__(self):
        return self.name


class Customer(TimeStampedModel):
    class PreferredContactMethod(models.TextChoices):
        PHONE = "phone", "Phone call"
        SMS = "sms", "SMS"
        VIBER = "viber", "Viber"
        WHATSAPP = "whatsapp", "WhatsApp"
        INSTAGRAM = "instagram", "Instagram"
        EMAIL = "email", "Email"

    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="customers",
    )
    full_name = models.CharField(max_length=160)
    phone_number = models.CharField(max_length=30)
    instagram_username = models.CharField(max_length=80)
    email = models.EmailField(blank=True)
    preferred_contact_method = models.CharField(
        max_length=20,
        choices=PreferredContactMethod.choices,
        default=PreferredContactMethod.VIBER,
    )

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "phone_number"],
                name="unique_customer_phone_per_salon",
            )
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"


class BookingPolicy(TimeStampedModel):
    salon = models.OneToOneField(
        Salon,
        on_delete=models.CASCADE,
        related_name="booking_policy",
    )
    minimum_notice_days = models.PositiveSmallIntegerField(default=14)
    maximum_booking_window_days = models.PositiveSmallIntegerField(default=60)
    allow_same_day_booking = models.BooleanField(default=False)
    allow_next_day_booking = models.BooleanField(default=False)
    auto_approve_bookings = models.BooleanField(default=False)
    late_arrival_limit_minutes = models.PositiveSmallIntegerField(default=15)
    reminder_hours_before = models.PositiveSmallIntegerField(default=24)
    pending_holds_slot = models.BooleanField(default=True)
    pending_expiration_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    max_appointments_per_day = models.PositiveSmallIntegerField(default=5)
    slot_interval_minutes = models.PositiveSmallIntegerField(default=30)
    buffer_minutes_between_bookings = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "booking policies"

    def __str__(self):
        return f"Booking policy for {self.salon}"

    def clean(self):
        errors = {}

        if self.maximum_booking_window_days < self.minimum_notice_days:
            errors["maximum_booking_window_days"] = (
                "Maximum booking window must be greater than or equal to minimum notice."
            )

        if self.slot_interval_minutes < 1:
            errors["slot_interval_minutes"] = "Slot interval must be at least 1 minute."

        if errors:
            raise ValidationError(errors)


class WorkingHours(TimeStampedModel):
    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    is_working_day = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["weekday"]
        verbose_name_plural = "working hours"
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "weekday"],
                name="unique_working_hours_weekday_per_salon",
            )
        ]

    def __str__(self):
        return f"{self.salon} - {self.get_weekday_display()}"

    def clean(self):
        errors = {}

        if self.is_working_day and (not self.start_time or not self.end_time):
            errors["start_time"] = "Working days need a start and end time."

        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "End time must be after start time."

        if errors:
            raise ValidationError(errors)


class DateWorkingHoursOverride(TimeStampedModel):
    class Mode(models.TextChoices):
        USE_DEFAULT = "use_default", "Use default working hours"
        CLOSED = "closed", "Closed"
        CUSTOM_HOURS = "custom_hours", "Custom working hours"

    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="date_working_hours_overrides",
    )
    date = models.DateField()
    mode = models.CharField(
        max_length=20,
        choices=Mode.choices,
        default=Mode.USE_DEFAULT,
    )
    custom_start_time = models.TimeField(null=True, blank=True)
    custom_end_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "date"],
                name="unique_date_working_hours_override_per_salon",
            )
        ]

    def __str__(self):
        return f"{self.salon} - {self.date} ({self.get_mode_display()})"

    def clean(self):
        errors = {}

        if self.mode == self.Mode.CUSTOM_HOURS:
            if not self.custom_start_time or not self.custom_end_time:
                errors["custom_start_time"] = "Custom hours need a start and end time."
            elif self.custom_end_time <= self.custom_start_time:
                errors["custom_end_time"] = "Custom end time must be after start time."
        elif self.custom_start_time or self.custom_end_time:
            errors["mode"] = "Custom times should only be set when mode is custom hours."

        if errors:
            raise ValidationError(errors)


class UnavailableTimeBlock(TimeStampedModel):
    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="unavailable_time_blocks",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["date", "start_time"]

    def __str__(self):
        return f"{self.salon} - {self.date} {self.start_time}-{self.end_time}"

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "No Show"

    class Source(models.TextChoices):
        ONLINE = "online", "Online"
        OWNER_MANUAL = "owner_manual", "Owner manual"
        INSTAGRAM = "instagram", "Instagram"
        MESSENGER = "messenger", "Messenger"
        VIBER = "viber", "Viber"
        PHONE = "phone", "Phone"
        IN_PERSON = "in_person", "In person"

    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    total_duration_minutes = models.PositiveSmallIntegerField(
        default=120,
        validators=[MinValueValidator(1)],
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.ONLINE,
    )
    customer_note = models.TextField(blank=True)
    owner_note = models.TextField(blank=True)
    reference_photo = models.ImageField(upload_to="booking_photos/", blank=True)
    rules_accepted = models.BooleanField(default=False)
    rules_accepted_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    change_message_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["start_at"]
        indexes = [
            models.Index(fields=["salon", "status", "start_at"]),
            models.Index(fields=["salon", "start_at", "end_at"]),
        ]

    def __str__(self):
        return f"{self.customer.full_name} - {self.start_at:%Y-%m-%d %H:%M}"

    def clean(self):
        errors = {}

        if self.customer_id and self.salon_id and self.customer.salon_id != self.salon_id:
            errors["customer"] = "Customer must belong to the same salon as the booking."

        if self.start_at and self.total_duration_minutes and not self.end_at:
            self.end_at = self.start_at + timedelta(minutes=self.total_duration_minutes)

        if self.start_at and self.end_at:
            if self.end_at <= self.start_at:
                errors["end_at"] = "End time must be after start time."
            else:
                conflicting_booking = self._find_conflicting_booking()
                if conflicting_booking:
                    errors["start_at"] = (
                        "This booking overlaps another active booking. "
                        "Choose a different time or duration."
                    )

        if self.source == self.Source.ONLINE and not self.rules_accepted:
            errors["rules_accepted"] = "Online booking requests must accept salon rules."

        if self.rules_accepted and not self.rules_accepted_at:
            self.rules_accepted_at = timezone.now()

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def _find_conflicting_booking(self):
        if not self.salon_id or not self.start_at or not self.end_at:
            return None

        statuses = [self.Status.APPROVED]
        if self._pending_holds_slot():
            statuses.append(self.Status.PENDING)

        if self.status not in statuses:
            return None

        query = Booking.objects.filter(
            salon_id=self.salon_id,
            status__in=statuses,
            start_at__lt=self.end_at,
            end_at__gt=self.start_at,
        )

        if self.pk:
            query = query.exclude(pk=self.pk)

        return query.first()

    def _pending_holds_slot(self):
        try:
            return self.salon.booking_policy.pending_holds_slot
        except BookingPolicy.DoesNotExist:
            return True


class BookingService(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="booking_services",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="booking_services",
    )
    service_name_snapshot = models.CharField(max_length=120, blank=True)
    duration_minutes_snapshot = models.PositiveSmallIntegerField(default=0)
    price_snapshot = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.service_name_snapshot

    def save(self, *args, **kwargs):
        if self.service_id:
            if not self.service_name_snapshot:
                self.service_name_snapshot = self.service.name
            if not self.duration_minutes_snapshot:
                self.duration_minutes_snapshot = self.service.duration_minutes
            if self.price_snapshot is None:
                self.price_snapshot = self.service.base_price

        super().save(*args, **kwargs)


class BookingActivityLog(models.Model):
    class Action(models.TextChoices):
        REQUESTED  = "requested",  "Requested"
        APPROVED   = "approved",   "Approved"
        REJECTED   = "rejected",   "Rejected"
        CANCELLED  = "cancelled",  "Cancelled"
        EDITED     = "edited",     "Edited"
        COMPLETED  = "completed",  "Completed"
        NO_SHOW    = "no_show",    "No Show"
        EMAIL_SENT = "email_sent", "Email sent"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="activity_log",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.booking} — {self.action}"


class CustomerBlocklist(TimeStampedModel):
    salon = models.ForeignKey(
        Salon,
        on_delete=models.CASCADE,
        related_name="customer_blocklist_entries",
    )
    phone_number = models.CharField(max_length=30)
    instagram_username = models.CharField(max_length=80, blank=True)
    reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["salon", "phone_number"],
                condition=Q(is_active=True),
                name="unique_active_blocked_phone_per_salon",
            )
        ]

    def __str__(self):
        return f"{self.phone_number} blocked for {self.salon}"
