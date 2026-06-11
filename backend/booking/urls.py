from django.urls import path

from . import views


app_name = "booking"

urlpatterns = [
    path("", views.home, name="home"),
    path("book/<slug:salon_slug>/", views.book_salon, name="book_salon"),
    path("book/<slug:salon_slug>/slots/", views.available_slots, name="available_slots"),
    path("booking/<int:booking_id>/success/", views.booking_success, name="booking_success"),
    path("owner/dashboard/", views.owner_dashboard, name="owner_dashboard"),
]
