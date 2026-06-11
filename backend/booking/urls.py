from django.urls import path

from . import views


app_name = "booking"

urlpatterns = [
    path("", views.home, name="home"),
    path("owner/dashboard/", views.owner_dashboard, name="owner_dashboard"),
]
