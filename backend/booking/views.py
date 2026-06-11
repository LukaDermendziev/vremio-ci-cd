from django.contrib.auth.decorators import login_required
from django.shortcuts import render


def home(request):
    return render(request, "booking/home.html")


@login_required
def owner_dashboard(request):
    return render(request, "booking/owner_dashboard.html")
