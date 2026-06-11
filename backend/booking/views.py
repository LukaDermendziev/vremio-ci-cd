from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import BookingRequestForm
from .models import Booking, Service, Salon
from .services import calculate_available_slots


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
            try:
                booking.save()
            except ValidationError as exc:
                messages.error(request, _validation_error_to_text(exc))
            else:
                messages.success(request, "Booking approved.")
        elif action == "reject":
            booking.status = Booking.Status.REJECTED
            booking.save()
            messages.success(request, "Booking rejected.")
        else:
            messages.error(request, "Unknown booking action.")

        return redirect("booking:owner_dashboard")

    now = timezone.now()
    today = timezone.localdate(now)
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
    todays_appointments = (
        salon.bookings.filter(status=Booking.Status.APPROVED, start_at__date=today)
        .select_related("customer")
        .prefetch_related("booking_services")
        .order_by("start_at")
    )
    booking_management_list = (
        salon.bookings.select_related("customer")
        .prefetch_related("booking_services")
        .order_by("-start_at")[:30]
    )
    services = salon.services.all()
    booking_policy = getattr(salon, "booking_policy", None)

    return render(
        request,
        "booking/owner_dashboard.html",
        {
            "salon": salon,
            "pending_bookings": pending_bookings,
            "pending_count": pending_bookings.count(),
            "upcoming_approved_bookings": upcoming_approved_bookings,
            "todays_appointments": todays_appointments,
            "today_count": todays_appointments.count(),
            "booking_management_list": booking_management_list,
            "services": services,
            "active_services_count": services.filter(is_active=True).count(),
            "booking_policy": booking_policy,
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


@require_GET
def available_slots(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)
    service_id = request.GET.get("service")
    date_value = request.GET.get("date")

    if not service_id or not date_value:
        return JsonResponse({"slots": []})

    service = get_object_or_404(Service, pk=service_id, salon=salon, is_active=True)

    try:
        selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": []})

    slots = calculate_available_slots(salon, service, selected_date)

    return JsonResponse(
        {
            "slots": [
                {
                    "value": slot["value"],
                    "label": slot["label"],
                    "end": slot["end"].strftime("%H:%M"),
                }
                for slot in slots
            ]
        }
    )


def _validation_error_to_text(exc):
    if hasattr(exc, "message_dict"):
        return " ".join(
            message
            for messages_for_field in exc.message_dict.values()
            for message in messages_for_field
        )

    return " ".join(exc.messages)
