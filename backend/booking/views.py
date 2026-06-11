from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import BookingRequestForm
from .models import Booking, Salon


def home(request):
    salons = Salon.objects.filter(is_active=True)
    return render(request, "booking/home.html", {"salons": salons})


@login_required
def owner_dashboard(request):
    salon = Salon.objects.filter(owner=request.user, is_active=True).first()

    if not salon:
        return render(request, "booking/owner_dashboard.html", {"salon": None})

    if request.method == "POST":
        booking = get_object_or_404(Booking, pk=request.POST.get("booking_id"), salon=salon)
        action = request.POST.get("action")

        if booking.status != Booking.Status.PENDING:
            messages.warning(request, "Only pending bookings can be approved or rejected here.")
        elif action == "approve":
            booking.status = Booking.Status.APPROVED
            booking.save()
            messages.success(request, "Booking approved.")
        elif action == "reject":
            booking.status = Booking.Status.REJECTED
            booking.save()
            messages.success(request, "Booking rejected.")
        else:
            messages.error(request, "Unknown booking action.")

        return redirect("booking:owner_dashboard")

    now = timezone.now()
    pending_bookings = (
        salon.bookings.filter(status=Booking.Status.PENDING)
        .select_related("customer")
        .prefetch_related("booking_services")
        .order_by("start_at")
    )
    upcoming_approved_bookings = (
        salon.bookings.filter(status=Booking.Status.APPROVED, start_at__gte=now)
        .select_related("customer")
        .prefetch_related("booking_services")
        .order_by("start_at")[:20]
    )

    return render(
        request,
        "booking/owner_dashboard.html",
        {
            "salon": salon,
            "pending_bookings": pending_bookings,
            "pending_count": pending_bookings.count(),
            "upcoming_approved_bookings": upcoming_approved_bookings,
        },
    )


def book_salon(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)

    if request.method == "POST":
        form = BookingRequestForm(request.POST, request.FILES, salon=salon)
        if form.is_valid():
            booking = form.save()
            return redirect(reverse("booking:booking_success", args=[booking.pk]))
    else:
        form = BookingRequestForm(salon=salon)

    return render(
        request,
        "booking/booking_form.html",
        {
            "salon": salon,
            "form": form,
            "services": salon.services.filter(is_active=True),
        },
    )


def booking_success(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("salon", "customer"),
        pk=booking_id,
    )

    return render(request, "booking/booking_success.html", {"booking": booking})
