from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import (
    BlockedDateForm,
    BookingPolicyForm,
    BookingRequestForm,
    OwnerBookingForm,
    OwnerCustomerForm,
    ServiceForm,
    UnavailableTimeBlockForm,
    WorkingHoursFormSet,
)
from .models import (
    Booking,
    BookingActivityLog,
    Customer,
    DateWorkingHoursOverride,
    Service,
    Salon,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import (
    build_contact_links,
    build_prepared_message,
    ensure_default_working_hours,
    get_available_slots,
    get_revenue_stats,
    get_working_window_for_date,
    log_booking_activity,
    send_booking_notification,
)


def home(request):
    salons = Salon.objects.filter(is_active=True)
    return render(request, "booking/home.html", {"salons": salons})


def _get_owner_salon(user):
    return Salon.objects.filter(owner=user, is_active=True).first()


def _validation_error_to_text(exc):
    if hasattr(exc, "message_dict"):
        return " ".join(
            message
            for messages_for_field in exc.message_dict.values()
            for message in messages_for_field
        )
    return " ".join(exc.messages)


def _owner_dashboard_context(salon):
    now = timezone.now()
    today = timezone.localdate(now)
    ensure_default_working_hours(salon)

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
        .order_by("-start_at")[:50]
    )
    customers = (
        salon.customers.prefetch_related(
            Prefetch(
                "bookings",
                queryset=Booking.objects.order_by("-start_at"),
            )
        )
        .order_by("full_name")
    )
    services = salon.services.all()
    booking_policy = getattr(salon, "booking_policy", None)
    working_hours = salon.working_hours.order_by("weekday")
    blocked_dates = salon.date_working_hours_overrides.filter(
        mode=DateWorkingHoursOverride.Mode.CLOSED
    ).order_by("date")
    unavailable_blocks = salon.unavailable_time_blocks.order_by("date", "start_time")[:30]
    revenue = get_revenue_stats(salon)

    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)
    no_show_count = salon.bookings.filter(status=Booking.Status.NO_SHOW).count()
    completed_week_count = salon.bookings.filter(
        status=Booking.Status.COMPLETED,
        start_at__date__gte=week_start,
        start_at__date__lte=week_end,
    ).count()

    return {
        "salon": salon,
        "pending_bookings": pending_bookings,
        "pending_count": pending_bookings.count(),
        "upcoming_approved_bookings": upcoming_approved_bookings,
        "todays_appointments": todays_appointments,
        "today_count": todays_appointments.count(),
        "no_show_count": no_show_count,
        "completed_week_count": completed_week_count,
        "booking_management_list": booking_management_list,
        "customers": customers,
        "services": services,
        "active_services_count": services.filter(is_active=True).count(),
        "booking_policy": booking_policy,
        "working_hours": working_hours,
        "blocked_dates": blocked_dates,
        "unavailable_blocks": unavailable_blocks,
        "revenue": revenue,
        "policy_form": BookingPolicyForm(instance=booking_policy) if booking_policy else None,
        "blocked_date_form": BlockedDateForm(),
        "unavailable_block_form": UnavailableTimeBlockForm(salon=salon),
        "owner_booking_form": OwnerBookingForm(salon=salon),
        "service_form": ServiceForm(salon=salon),
        "customer_form": OwnerCustomerForm(salon=salon),
    }


def owner_login(request):
    """Custom login page for salon owners."""
    if request.user.is_authenticated:
        return redirect("booking:owner_dashboard")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            return redirect("booking:owner_dashboard")
        error = "Invalid username or password."

    return render(request, "booking/auth/login.html", {"error": error})


def owner_logout(request):
    auth_logout(request)
    return redirect("booking:owner_login")


@login_required
def owner_dashboard(request):
    salon = _get_owner_salon(request.user)

    if not salon:
        return render(
            request,
            "booking/owner_dashboard.html",
            {"salon": None, "hide_base_messages": True},
        )

    if request.method == "POST":
        action = request.POST.get("action")

        if action in {"approve", "reject"}:
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            if booking.status != Booking.Status.PENDING:
                messages.warning(
                    request, "Only pending bookings can be approved or rejected here."
                )
            elif action == "approve":
                booking.status = Booking.Status.APPROVED
                try:
                    booking.save()
                except ValidationError as exc:
                    messages.error(request, _validation_error_to_text(exc))
                else:
                    log_booking_activity(booking, BookingActivityLog.Action.APPROVED, user=request.user)
                    sent, reason = send_booking_notification(booking, "approved")
                    if sent:
                        log_booking_activity(booking, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Approval email sent")
                        messages.success(request, "Booking approved. Email sent to customer.")
                    elif reason == "no_email":
                        messages.success(request, "Booking approved. Customer has no email — use prepared message.")
                    else:
                        messages.success(request, "Booking approved. Email could not be sent — use prepared message.")
            else:
                booking.status = Booking.Status.REJECTED
                booking.save()
                log_booking_activity(booking, BookingActivityLog.Action.REJECTED, user=request.user)
                sent, reason = send_booking_notification(booking, "rejected")
                if sent:
                    log_booking_activity(booking, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Rejection email sent")
                    messages.success(request, "Booking rejected. Email sent to customer.")
                elif reason == "no_email":
                    messages.success(request, "Booking rejected. Customer has no email — use prepared message.")
                else:
                    messages.success(request, "Booking rejected. Email could not be sent — use prepared message.")

        elif action == "save_booking":
            is_edit = bool(request.POST.get("booking_id"))
            booking = None
            if is_edit:
                booking = get_object_or_404(Booking, pk=request.POST.get("booking_id"), salon=salon)
            form = OwnerBookingForm(request.POST, salon=salon, booking=booking)
            if form.is_valid():
                try:
                    saved = form.save()
                except ValidationError as exc:
                    messages.error(request, _validation_error_to_text(exc))
                else:
                    if is_edit:
                        log_booking_activity(saved, BookingActivityLog.Action.EDITED, user=request.user)
                        inform = request.POST.get("inform_customer")
                        if inform:
                            sent, reason = send_booking_notification(saved, "edited")
                            if sent:
                                log_booking_activity(saved, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Edit email sent")
                            messages.success(request, "Booking updated." + (" Email sent." if sent else " Use prepared message to notify customer."))
                        else:
                            messages.success(request, "Booking updated successfully.")
                    else:
                        log_booking_activity(saved, BookingActivityLog.Action.REQUESTED, user=request.user, note="Manually added by owner")
                        messages.success(request, "Booking added successfully.")
            else:
                for field, errs in form.errors.items():
                    for err in errs:
                        messages.error(request, f"{field}: {err}")

        elif action == "save_working_hours":
            formset = WorkingHoursFormSet(
                request.POST,
                queryset=salon.working_hours.order_by("weekday"),
            )
            if formset.is_valid():
                instances = formset.save(commit=False)
                for instance in instances:
                    instance.salon = salon
                    instance.save()
                messages.success(request, "Working hours saved.")
            else:
                messages.error(request, "Could not save working hours. Check the times.")

        elif action == "save_policy":
            policy = getattr(salon, "booking_policy", None)
            if not policy:
                messages.error(request, "No booking policy found for this salon.")
            else:
                form = BookingPolicyForm(request.POST, instance=policy)
                if form.is_valid():
                    form.save()
                    messages.success(request, "Booking policy saved.")
                else:
                    messages.error(request, "Could not save booking policy.")

        elif action == "add_blocked_date":
            form = BlockedDateForm(request.POST)
            if form.is_valid():
                DateWorkingHoursOverride.objects.update_or_create(
                    salon=salon,
                    date=form.cleaned_data["date"],
                    defaults={
                        "mode": DateWorkingHoursOverride.Mode.CLOSED,
                        "reason": form.cleaned_data.get("reason", ""),
                    },
                )
                messages.success(request, "Blocked date added.")
            else:
                messages.error(request, "Invalid blocked date.")

        elif action == "delete_blocked_date":
            override_id = request.POST.get("override_id")
            salon.date_working_hours_overrides.filter(
                pk=override_id,
                mode=DateWorkingHoursOverride.Mode.CLOSED,
            ).delete()
            messages.success(request, "Blocked date removed.")

        elif action == "add_unavailable_block":
            form = UnavailableTimeBlockForm(request.POST, salon=salon)
            if form.is_valid():
                try:
                    form.save()
                except ValidationError as exc:
                    messages.error(request, _validation_error_to_text(exc))
                else:
                    messages.success(request, "Unavailable time block added.")
            else:
                messages.error(request, "Could not add unavailable time block.")

        elif action == "delete_unavailable_block":
            block_id = request.POST.get("block_id")
            salon.unavailable_time_blocks.filter(pk=block_id).delete()
            messages.success(request, "Unavailable time block removed.")

        elif action == "mark_completed":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            booking.status = Booking.Status.COMPLETED
            booking.save()
            log_booking_activity(booking, BookingActivityLog.Action.COMPLETED, user=request.user)
            messages.success(request, "Booking marked as completed.")

        elif action == "mark_no_show":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            booking.status = Booking.Status.NO_SHOW
            booking.save()
            log_booking_activity(booking, BookingActivityLog.Action.NO_SHOW, user=request.user)
            sent, reason = send_booking_notification(booking, "no_show")
            if sent:
                log_booking_activity(booking, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="No-show email sent")
            messages.success(request, "Booking marked as no-show.")

        elif action == "cancel_booking":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            if booking.status in {Booking.Status.COMPLETED, Booking.Status.NO_SHOW}:
                messages.warning(request, "Cannot cancel a completed or no-show booking.")
            else:
                booking.status = Booking.Status.CANCELLED
                booking.save()
                log_booking_activity(booking, BookingActivityLog.Action.CANCELLED, user=request.user)
                sent, reason = send_booking_notification(booking, "cancelled")
                if sent:
                    log_booking_activity(booking, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Cancellation email sent")
                    messages.success(request, "Booking cancelled. Email sent to customer.")
                elif reason == "no_email":
                    messages.success(request, "Booking cancelled. Customer has no email — use prepared message.")
                else:
                    messages.success(request, "Booking cancelled.")

        elif action == "delete_booking":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            booking.delete()
            messages.success(request, "Booking deleted.")

        elif action == "save_service":
            service = None
            service_id = request.POST.get("service_id")
            if service_id:
                service = get_object_or_404(Service, pk=service_id, salon=salon)
            post_data = request.POST.copy()
            for field_name in ("is_active", "requires_photo", "photo_recommended"):
                post_data[field_name] = field_name in request.POST
            form = ServiceForm(post_data, instance=service, salon=salon)
            if form.is_valid():
                form.save()
                label = "updated" if service else "added"
                messages.success(request, f"Service {label} successfully.")
            else:
                messages.error(request, "Could not save service. Check the form.")

        elif action == "delete_service":
            service = get_object_or_404(
                Service, pk=request.POST.get("service_id"), salon=salon
            )
            service.delete()
            messages.success(request, "Service deleted.")

        elif action == "save_customer":
            customer = None
            customer_id = request.POST.get("customer_id")
            if customer_id:
                customer = get_object_or_404(Customer, pk=customer_id, salon=salon)
            form = OwnerCustomerForm(request.POST, instance=customer, salon=salon)
            if form.is_valid():
                form.save()
                label = "updated" if customer else "added"
                messages.success(request, f"Customer {label} successfully.")
            else:
                messages.error(request, "Could not save customer.")

        elif action == "delete_customer":
            customer = get_object_or_404(
                Customer, pk=request.POST.get("customer_id"), salon=salon
            )
            if customer.bookings.exists():
                messages.error(
                    request,
                    "Cannot delete a customer with existing bookings. Remove bookings first.",
                )
            else:
                customer.delete()
                messages.success(request, "Customer deleted.")

        elif action == "save_blocked_date":
            form = BlockedDateForm(request.POST)
            if form.is_valid():
                DateWorkingHoursOverride.objects.update_or_create(
                    salon=salon,
                    date=form.cleaned_data["date"],
                    defaults={
                        "mode": DateWorkingHoursOverride.Mode.CLOSED,
                        "reason": form.cleaned_data.get("reason", ""),
                    },
                )
                messages.success(request, "Blocked date saved.")
            else:
                messages.error(request, "Invalid blocked date.")

        elif action == "save_unavailable_block":
            block = None
            block_id = request.POST.get("block_id")
            if block_id:
                block = get_object_or_404(
                    UnavailableTimeBlock, pk=block_id, salon=salon
                )
            form = UnavailableTimeBlockForm(request.POST, instance=block, salon=salon)
            if form.is_valid():
                try:
                    form.save()
                except ValidationError as exc:
                    messages.error(request, _validation_error_to_text(exc))
                else:
                    label = "updated" if block else "added"
                    messages.success(request, f"Time block {label}.")
            else:
                messages.error(request, "Could not save unavailable time block.")

        else:
            messages.error(request, "Unknown action.")

        section = request.POST.get("return_section", "dashboard")
        return redirect(f"{reverse('booking:owner_dashboard')}#{section}")

    context = _owner_dashboard_context(salon)
    context["hours_formset"] = WorkingHoursFormSet(
        queryset=salon.working_hours.order_by("weekday")
    )
    context["hide_base_messages"] = True
    return render(request, "booking/owner_dashboard.html", context)


@login_required
def customer_history(request, customer_id):
    salon = _get_owner_salon(request.user)
    if not salon:
        return redirect("booking:owner_dashboard")

    customer = get_object_or_404(Customer, pk=customer_id, salon=salon)
    bookings = (
        customer.bookings.select_related("salon")
        .prefetch_related("booking_services")
        .order_by("-start_at")
    )

    return render(
        request,
        "booking/customer_history.html",
        {
            "salon": salon,
            "customer": customer,
            "bookings": bookings,
        },
    )


@login_required
@require_GET
def owner_calendar_events(request):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"events": [], "closedDates": [], "closedWeekdays": []})

    start_raw = request.GET.get("start", "")
    end_raw = request.GET.get("end", "")
    try:
        range_start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        range_end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        if timezone.is_naive(range_start):
            range_start = timezone.make_aware(range_start)
        if timezone.is_naive(range_end):
            range_end = timezone.make_aware(range_end)
    except ValueError:
        return JsonResponse({"events": [], "closedDates": [], "closedWeekdays": []})

    status_styles = {
        Booking.Status.PENDING:   {"bg": "#FEF9C3", "border": "#D97706", "text": "#78350F"},
        Booking.Status.APPROVED:  {"bg": "#D1FAE5", "border": "#059669", "text": "#064E3B"},
        Booking.Status.REJECTED:  {"bg": "#FCE7F3", "border": "#DB2777", "text": "#831843"},
        Booking.Status.CANCELLED: {"bg": "#F3F4F6", "border": "#6B7280", "text": "#374151"},
        Booking.Status.COMPLETED: {"bg": "#DBEAFE", "border": "#2563EB", "text": "#1E3A8A"},
        Booking.Status.NO_SHOW:   {"bg": "#FEE0CC", "border": "#C2410C", "text": "#7C2D12"},
    }

    events = []
    bookings = salon.bookings.filter(
        start_at__lt=range_end,
        end_at__gt=range_start,
    ).select_related("customer").prefetch_related("booking_services")

    for booking in bookings:
        services = ", ".join(
            item.service_name_snapshot for item in booking.booking_services.all()
        )
        style = status_styles.get(booking.status, status_styles[Booking.Status.APPROVED])
        events.append(
            {
                "id": f"booking-{booking.id}",
                "title": booking.customer.full_name,
                "start": booking.start_at.isoformat(),
                "end": booking.end_at.isoformat(),
                "backgroundColor": style["bg"],
                "borderColor": style["border"],
                "textColor": style["text"],
                "classNames": [f"fc-event-status-{booking.status}"],
                "extendedProps": {
                    "type": "booking",
                    "bookingId": booking.id,
                    "status": booking.status,
                    "customerName": booking.customer.full_name,
                    "phone": booking.customer.phone_number,
                    "services": services,
                    "duration": booking.total_duration_minutes,
                },
            }
        )

    blocks = salon.unavailable_time_blocks.filter(
        date__gte=range_start.date(),
        date__lte=range_end.date(),
    )
    salon_tz = timezone.get_current_timezone()
    for block in blocks:
        start = timezone.make_aware(
            datetime.combine(block.date, block.start_time), salon_tz
        )
        end = timezone.make_aware(datetime.combine(block.date, block.end_time), salon_tz)
        events.append(
            {
                "id": f"block-{block.id}",
                "title": block.reason or "Blocked",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "backgroundColor": "#EDE9FE",
                "borderColor": "#7C3AED",
                "textColor": "#4C1D95",
                "classNames": ["fc-event-block"],
                "extendedProps": {
                    "type": "block",
                    "blockId": block.id,
                    "reason": block.reason,
                    "date": block.date.isoformat(),
                    "startTime": block.start_time.strftime("%H:%M"),
                    "endTime": block.end_time.strftime("%H:%M"),
                },
            }
        )

    closed_dates = set()
    closed_weekdays = set()
    for row in salon.working_hours.filter(is_working_day=False):
        closed_weekdays.add(row.weekday)

    overrides = salon.date_working_hours_overrides.filter(
        date__gte=range_start.date(),
        date__lte=range_end.date(),
    )
    for override in overrides:
        if override.mode == DateWorkingHoursOverride.Mode.CLOSED:
            closed_dates.add(override.date.isoformat())

    current = range_start.date()
    while current <= range_end.date():
        window = get_working_window_for_date(salon, current)
        if window is None:
            closed_dates.add(current.isoformat())
        current += timedelta(days=1)

    return JsonResponse(
        {
            "events": events,
            "closedDates": sorted(closed_dates),
            "closedWeekdays": sorted(closed_weekdays),
        }
    )


@login_required
@require_GET
def owner_booking_detail(request, booking_id):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    booking = get_object_or_404(
        Booking.objects.select_related("customer").prefetch_related(
            "booking_services__service", "activity_log__performed_by"
        ),
        pk=booking_id,
        salon=salon,
    )
    first_service = booking.booking_services.first()
    local_start = timezone.localtime(booking.start_at)
    local_end   = timezone.localtime(booking.end_at)

    services_list = [
        {
            "name": bs.service_name_snapshot,
            "duration": bs.duration_minutes_snapshot,
            "price": str(bs.price_snapshot),
        }
        for bs in booking.booking_services.all()
    ]

    activity = [
        {
            "action": entry.action,
            "action_label": entry.get_action_display(),
            "by": entry.performed_by.get_full_name() or entry.performed_by.username if entry.performed_by else "System",
            "note": entry.note,
            "at": entry.created_at.isoformat(),
        }
        for entry in booking.activity_log.order_by("created_at")
    ]

    return JsonResponse(
        {
            "id": booking.id,
            "full_name": booking.customer.full_name,
            "phone_number": booking.customer.phone_number,
            "instagram_username": booking.customer.instagram_username,
            "email": booking.customer.email,
            "preferred_contact_method": booking.customer.preferred_contact_method,
            "service_id": first_service.service_id if first_service else None,
            "services": services_list,
            "date": local_start.strftime("%Y-%m-%d"),
            "date_display": local_start.strftime("%d/%m/%Y"),
            "start_time": local_start.strftime("%H:%M"),
            "end_time": local_end.strftime("%H:%M"),
            "duration": booking.total_duration_minutes,
            "status": booking.status,
            "status_label": booking.get_status_display(),
            "source": booking.source,
            "customer_note": booking.customer_note,
            "owner_note": booking.owner_note,
            "has_reference_photo": bool(booking.reference_photo),
            "reference_photo_url": booking.reference_photo.url if booking.reference_photo else None,
            "created_at": booking.created_at.isoformat(),
            "updated_at": booking.updated_at.isoformat(),
            "activity_log": activity,
        }
    )


@login_required
@require_GET
def booking_ics(request, booking_id):
    """Generate an .ics calendar file for an approved booking."""
    from django.http import HttpResponse

    salon = _get_owner_salon(request.user)
    if not salon:
        return HttpResponse(status=403)

    booking = get_object_or_404(
        Booking.objects.select_related("customer").prefetch_related("booking_services"),
        pk=booking_id,
        salon=salon,
    )

    local_start = timezone.localtime(booking.start_at)
    local_end   = timezone.localtime(booking.end_at)
    services    = ", ".join(bs.service_name_snapshot for bs in booking.booking_services.all())
    uid         = f"booking-{booking.id}@salonscheduler"
    now_stamp   = timezone.now().strftime("%Y%m%dT%H%M%SZ")

    def fmt(dt):
        return dt.strftime("%Y%m%dT%H%M%S")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Salon Scheduler//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART:{fmt(local_start)}",
        f"DTEND:{fmt(local_end)}",
        f"SUMMARY:{booking.customer.full_name} — {services}",
        f"DESCRIPTION:Phone: {booking.customer.phone_number}\\nInstagram: {booking.customer.instagram_username}\\nStatus: {booking.get_status_display()}",
        f"LOCATION:{salon.name}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    content = "\r\n".join(ics_lines) + "\r\n"
    response = HttpResponse(content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="booking-{booking.id}.ics"'
    return response


@login_required
@require_GET
def booking_message_links(request, booking_id):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    booking = get_object_or_404(
        Booking.objects.select_related("customer", "salon"),
        pk=booking_id,
        salon=salon,
    )
    message_type = request.GET.get("type", booking.status)
    message = build_prepared_message(booking, message_type)
    links = build_contact_links(booking.customer.phone_number, message)

    return JsonResponse(
        {
            "message": message,
            "links": links,
            "preferred": booking.customer.preferred_contact_method,
        }
    )


@login_required
@require_GET
def owner_available_slots(request):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"slots": []})

    service_id = request.GET.get("service")
    date_value = request.GET.get("date")
    exclude_id = request.GET.get("exclude")

    if not service_id or not date_value:
        return JsonResponse({"slots": []})

    service = get_object_or_404(Service, pk=service_id, salon=salon, is_active=True)
    try:
        selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": []})

    slots = get_available_slots(
        salon,
        service,
        selected_date,
        for_owner=True,
        exclude_booking_id=exclude_id or None,
    )
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


def salon_page(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)
    policy = getattr(salon, "booking_policy", None)
    working_hours = salon.working_hours.order_by("weekday")
    if not working_hours.exists():
        ensure_default_working_hours(salon)
        working_hours = salon.working_hours.order_by("weekday")

    return render(
        request,
        "booking/salon_page.html",
        {
            "salon": salon,
            "services": salon.services.filter(is_active=True),
            "working_hours": working_hours,
            "booking_policy": policy,
        },
    )


def book_salon(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)
    policy = getattr(salon, "booking_policy", None)
    today = date.today()
    min_notice = policy.minimum_notice_days if policy else 14
    max_window = policy.maximum_booking_window_days if policy else 60

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
            "min_date": (today + timedelta(days=min_notice)).isoformat(),
            "max_date": (today + timedelta(days=max_window)).isoformat(),
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

    slots = get_available_slots(salon, service, selected_date)

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
