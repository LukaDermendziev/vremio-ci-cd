from django.contrib.auth import views as auth_views
from django.urls import path
from django.urls import reverse_lazy

from . import views


app_name = "booking"

urlpatterns = [
    path("health/", views.health, name="health"),
    path("", views.home, name="home"),
    path("plan-interest/", views.plan_interest, name="plan_interest"),
    path("privacy/", views.privacy_policy, name="privacy_policy"),
    path("terms/", views.terms_of_use, name="terms_of_use"),
    path("booking-rules/", views.booking_rules, name="booking_rules"),
    path("photo-policy/", views.photo_policy, name="photo_policy"),
    path("contact/", views.contact_data_requests, name="contact"),
    path("owner/pilot-terms/", views.owner_pilot_terms, name="owner_pilot_terms"),
    path("book/<slug:salon_slug>/", views.salon_page, name="salon_page"),
    path("business/<slug:salon_slug>/", views.salon_page, name="business_page"),
    path("book/<slug:salon_slug>/request/", views.book_salon, name="book_salon"),
    path("book/<slug:salon_slug>/slots/", views.available_slots, name="available_slots"),
    path(
        "book/<slug:salon_slug>/last-minute-dates/",
        views.last_minute_dates,
        name="last_minute_dates",
    ),
    path(
        "book/<slug:salon_slug>/full-dates/",
        views.fully_booked_dates,
        name="fully_booked_dates",
    ),
    path(
        "book/<slug:salon_slug>/verify/<uuid:token>/",
        views.verify_booking_email,
        name="verify_booking_email",
    ),
    path("booking/verify/<uuid:token>/", views.verify_booking_email, name="verify_booking_email_legacy"),
    path("booking/verify-email-sent/", views.booking_verify_email_sent, name="booking_verify_email_sent"),
    path(
        "booking/verify-email-sent/resend/",
        views.resend_booking_verification_email,
        name="resend_booking_verification_email",
    ),
    path("booking/verify-sms/", views.booking_verify_sms, name="booking_verify_sms"),
    path(
        "booking/verify-sms/resend/",
        views.resend_booking_verification_sms,
        name="resend_booking_verification_sms",
    ),
    path("booking/success/", views.booking_success, name="booking_success"),
    path(
        "booking/<int:booking_id>/success/",
        views.booking_success_legacy,
        name="booking_success_legacy",
    ),
    path("booking/manage/<uuid:token>/", views.manage_booking, name="manage_booking"),
    path(
        "booking/manage/<uuid:token>/calendar.ics",
        views.manage_booking_ics,
        name="manage_booking_ics",
    ),
    path("booking/manage/<uuid:token>/cancel/", views.manage_booking_cancel, name="manage_booking_cancel"),

    # ── Owner dashboard ─────────────────────────────────────────────────────────
    path("owner/dashboard/", views.owner_dashboard, name="owner_dashboard"),
    path(
        "owner/plan-change/",
        views.owner_request_plan_change,
        name="owner_request_plan_change",
    ),
    path("owner/calendar/events/", views.owner_calendar_events, name="owner_calendar_events"),
    path("owner/slots/", views.owner_available_slots, name="owner_available_slots"),
    path(
        "owner/booking/<int:booking_id>/detail/",
        views.owner_booking_detail,
        name="owner_booking_detail",
    ),
    path(
        "owner/booking/<int:booking_id>/photo/",
        views.owner_booking_photo,
        name="owner_booking_photo",
    ),
    path(
        "owner/booking/<int:booking_id>/message/",
        views.booking_message_links,
        name="booking_message_links",
    ),
    path(
        "owner/booking/<int:booking_id>/ics/",
        views.booking_ics,
        name="booking_ics",
    ),
    path(
        "owner/customers/<int:customer_id>/",
        views.customer_history,
        name="customer_history",
    ),
    path("owner/customers/block/", views.owner_block_customer, name="owner_block_customer"),
    path(
        "owner/customers/block/context/",
        views.owner_customer_block_context,
        name="owner_customer_block_context",
    ),
    path(
        "owner/customers/block/<int:entry_id>/",
        views.owner_customer_block_detail,
        name="owner_customer_block_detail",
    ),
    path(
        "owner/customers/block/<int:entry_id>/unblock/",
        views.owner_unblock_customer,
        name="owner_unblock_customer",
    ),
    path(
        "owner/customers/block/<int:entry_id>/update/",
        views.owner_update_customer_block,
        name="owner_update_customer_block",
    ),

    # ── Owner auth ───────────────────────────────────────────────────────────────
    path("owner/login/", views.owner_login, name="owner_login"),
    path("owner/logout/", views.owner_logout, name="owner_logout"),

    # Password reset flow (Django built-in views, custom templates)
    path(
        "owner/password/reset/",
        auth_views.PasswordResetView.as_view(
            template_name="booking/auth/password_reset.html",
            email_template_name="booking/auth/password_reset_email.html",
            subject_template_name="booking/auth/password_reset_subject.txt",
            success_url=reverse_lazy("booking:owner_password_reset_done"),
        ),
        name="owner_password_reset",
    ),
    path(
        "owner/password/reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="booking/auth/password_reset_done.html",
        ),
        name="owner_password_reset_done",
    ),
    path(
        "owner/password/reset/confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="booking/auth/password_reset_confirm.html",
            success_url=reverse_lazy("booking:owner_password_reset_complete"),
        ),
        name="owner_password_reset_confirm",
    ),
    path(
        "owner/password/reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="booking/auth/password_reset_complete.html",
        ),
        name="owner_password_reset_complete",
    ),
    path(
        "owner/password/change/",
        auth_views.PasswordChangeView.as_view(
            template_name="booking/auth/password_change.html",
            success_url=reverse_lazy("booking:owner_dashboard"),
        ),
        name="owner_password_change",
    ),
]
