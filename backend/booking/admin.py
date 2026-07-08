"""Django admin for Vremio booking models.

Salon owners use the owner dashboard — do not grant them Django staff access.
Staff users with model permissions can see all salons' data across tenants.
Restrict /admin/ to platform superusers only in production.
"""
from django.contrib import admin

from .models import (
    Booking,
    BookingActivityLog,
    BookingPolicy,
    BookingService,
    Customer,
    CustomerBlocklist,
    CustomerBlockEvent,
    DateWorkingHoursOverride,
    ReleasedSlot,
    Salon,
    Service,
    ServicePriceItem,
    UnavailableTimeBlock,
    WorkingHours,
)


class BookingServiceInline(admin.TabularInline):
    model = BookingService
    extra = 1


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business_category",
        "city",
        "owner",
        "phone_number",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "business_category")
    search_fields = ("name", "phone_number", "instagram_username", "city")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "owner",
                    "name",
                    "slug",
                    "business_category",
                    "short_description",
                    "is_active",
                )
            },
        ),
        (
            "Contact & location",
            {
                "fields": (
                    "phone_number",
                    "instagram_username",
                    "city",
                    "address",
                    "timezone",
                )
            },
        ),
        (
            "Public salon page",
            {
                "fields": ("public_hours_end_display",),
            },
        ),
    )


class ServicePriceItemInline(admin.TabularInline):
    model = ServicePriceItem
    extra = 1
    fields = ("group", "name", "price_display", "photo_required", "sort_order")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "salon",
        "duration_minutes",
        "base_price",
        "requires_photo",
        "is_active",
    )
    list_filter = ("salon", "is_active", "requires_photo", "photo_recommended")
    search_fields = ("name", "description")
    list_editable = ("duration_minutes", "base_price", "is_active")
    inlines = [ServicePriceItemInline]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "salon",
        "phone_number",
        "instagram_username",
        "preferred_contact_method",
        "email",
    )
    list_filter = ("salon", "preferred_contact_method")
    search_fields = ("full_name", "phone_number", "instagram_username", "email")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "salon",
        "status",
        "start_at",
        "end_at",
        "total_duration_minutes",
        "source",
    )
    list_filter = ("salon", "status", "source", "start_at")
    search_fields = (
        "customer__full_name",
        "customer__phone_number",
        "customer__instagram_username",
    )
    date_hierarchy = "start_at"
    inlines = [BookingServiceInline]


@admin.register(BookingPolicy)
class BookingPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "salon",
        "minimum_notice_days",
        "maximum_booking_window_days",
        "auto_approve_bookings",
        "pending_holds_slot",
        "use_fixed_start_times",
        "slot_interval_minutes",
        "buffer_minutes_between_bookings",
    )
    list_filter = (
        "auto_approve_bookings",
        "pending_holds_slot",
        "allow_same_day_booking",
        "allow_next_day_booking",
        "use_fixed_start_times",
    )


@admin.register(WorkingHours)
class WorkingHoursAdmin(admin.ModelAdmin):
    list_display = ("salon", "weekday", "is_working_day", "start_time", "end_time")
    list_filter = ("salon", "weekday", "is_working_day")


@admin.register(DateWorkingHoursOverride)
class DateWorkingHoursOverrideAdmin(admin.ModelAdmin):
    list_display = (
        "salon",
        "date",
        "mode",
        "custom_start_time",
        "custom_end_time",
        "reason",
    )
    list_filter = ("salon", "mode", "date")
    search_fields = ("reason",)


@admin.register(ReleasedSlot)
class ReleasedSlotAdmin(admin.ModelAdmin):
    list_display = ("salon", "start_at", "end_at", "is_active", "source_booking", "released_at")
    list_filter = ("salon", "is_active", "start_at")
    date_hierarchy = "start_at"
    readonly_fields = ("released_at",)


@admin.register(UnavailableTimeBlock)
class UnavailableTimeBlockAdmin(admin.ModelAdmin):
    list_display = ("salon", "date", "start_time", "end_time", "reason")
    list_filter = ("salon", "date")
    search_fields = ("reason",)


@admin.register(BookingActivityLog)
class BookingActivityLogAdmin(admin.ModelAdmin):
    list_display = ("booking", "action", "performed_by", "note", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("booking__customer__full_name", "note")
    readonly_fields = ("booking", "action", "performed_by", "note", "created_at")


@admin.register(CustomerBlocklist)
class CustomerBlocklistAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "salon",
        "customer",
        "reason_code",
        "email",
        "is_active",
        "blocked_at",
        "blocked_by",
    )
    list_filter = ("salon", "is_active", "reason_code")
    search_fields = ("phone_number", "email", "instagram_username", "reason", "notes")
    readonly_fields = ("blocked_at", "unblocked_at", "created_at", "updated_at")


@admin.register(CustomerBlockEvent)
class CustomerBlockEventAdmin(admin.ModelAdmin):
    list_display = ("blocklist_entry", "event_type", "performed_by", "reason_code", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("blocklist_entry__phone_number", "notes")
    readonly_fields = ("blocklist_entry", "event_type", "performed_by", "reason_code", "notes", "created_at")
