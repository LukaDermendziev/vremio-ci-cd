from django.urls import path

from . import views


app_name = "booking"

urlpatterns = [
    path("", views.home, name="home"),
    path("book/<slug:salon_slug>/", views.salon_page, name="salon_page"),
    path("book/<slug:salon_slug>/request/", views.book_salon, name="book_salon"),
    path("book/<slug:salon_slug>/slots/", views.available_slots, name="available_slots"),
    path("booking/<int:booking_id>/success/", views.booking_success, name="booking_success"),
    path("owner/dashboard/", views.owner_dashboard, name="owner_dashboard"),
    path("owner/calendar/events/", views.owner_calendar_events, name="owner_calendar_events"),
    path("owner/slots/", views.owner_available_slots, name="owner_available_slots"),
    path(
        "owner/booking/<int:booking_id>/detail/",
        views.owner_booking_detail,
        name="owner_booking_detail",
    ),
    path(
        "owner/booking/<int:booking_id>/message/",
        views.booking_message_links,
        name="booking_message_links",
    ),
    path(
        "owner/customers/<int:customer_id>/",
        views.customer_history,
        name="customer_history",
    ),
]
