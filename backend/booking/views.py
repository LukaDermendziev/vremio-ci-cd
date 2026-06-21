import json
import uuid
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from .anti_abuse import DEVICE_COOKIE_MAX_AGE, DEVICE_COOKIE_NAME
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
    ServicePriceItem,
    Salon,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import (
    build_contact_links,
    build_prepared_message,
    can_customer_cancel_booking,
    ensure_default_working_hours,
    get_available_slots,
    get_manage_booking_url,
    get_revenue_stats,
    get_working_window_for_date,
    log_booking_activity,
    send_booking_notification,
    send_owner_customer_cancelled_notification,
    send_owner_new_booking_notification,
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
    services = salon.services.prefetch_related("price_items").all()
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
        error = _("Invalid username or password.")

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
                    request, _("Only pending bookings can be approved or rejected here.")
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
                        messages.success(request, _("Appointment approved. Email sent to customer."))
                    elif reason == "no_email":
                        messages.success(request, _("Appointment approved. Customer did not provide an email."))
                    else:
                        messages.success(request, _("Appointment approved."))
                        messages.warning(request, _("Email could not be sent. Prepared message is available."))
            else:
                booking.status = Booking.Status.REJECTED
                booking.save()
                log_booking_activity(booking, BookingActivityLog.Action.REJECTED, user=request.user)
                sent, reason = send_booking_notification(booking, "rejected")
                if sent:
                    log_booking_activity(booking, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Rejection email sent")
                    messages.success(request, _("Request declined. Email sent to customer."))
                elif reason == "no_email":
                    messages.success(request, _("Request declined. Customer did not provide an email."))
                else:
                    messages.success(request, _("Request declined."))
                    messages.warning(request, _("Email could not be sent. Prepared message is available."))

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
                    for warning in form.customer_warnings:
                        messages.warning(request, warning)
                    if is_edit:
                        log_booking_activity(saved, BookingActivityLog.Action.EDITED, user=request.user)
                        inform = request.POST.get("inform_customer")
                        if inform:
                            sent, reason = send_booking_notification(saved, "edited")
                            if sent:
                                log_booking_activity(saved, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Edit email sent")
                                messages.success(request, _("Appointment updated. Email sent to customer."))
                            elif reason == "no_email":
                                messages.success(request, _("Appointment updated. Customer did not provide an email."))
                            else:
                                messages.success(request, _("Appointment updated."))
                                messages.warning(request, _("Email could not be sent. Prepared message is available."))
                        else:
                            messages.success(request, _("Booking updated successfully."))
                    else:
                        log_booking_activity(saved, BookingActivityLog.Action.REQUESTED, user=request.user, note="Manually added by owner")
                        messages.success(request, _("Booking added successfully."))
            else:
                for field, errs in form.errors.items():
                    for err in errs:
                        messages.error(request, _("%(field)s: %(error)s") % {"field": field, "error": err})

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
                messages.success(request, _("Working hours saved."))
            else:
                messages.error(request, _("Could not save working hours. Check the times."))

        elif action == "save_policy":
            policy = getattr(salon, "booking_policy", None)
            if not policy:
                messages.error(request, _("No booking policy found for this salon."))
            else:
                form = BookingPolicyForm(request.POST, instance=policy)
                if form.is_valid():
                    form.save()
                    messages.success(request, _("Booking policy saved."))
                else:
                    messages.error(request, _("Could not save booking policy."))

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
                messages.success(request, _("Blocked date added."))
            else:
                messages.error(request, _("Invalid blocked date."))

        elif action == "delete_blocked_date":
            override_id = request.POST.get("override_id")
            salon.date_working_hours_overrides.filter(
                pk=override_id,
                mode=DateWorkingHoursOverride.Mode.CLOSED,
            ).delete()
            messages.success(request, _("Blocked date removed."))

        elif action == "add_unavailable_block":
            form = UnavailableTimeBlockForm(request.POST, salon=salon)
            if form.is_valid():
                try:
                    form.save()
                except ValidationError as exc:
                    messages.error(request, _validation_error_to_text(exc))
                else:
                    messages.success(request, _("Unavailable time block added."))
            else:
                messages.error(request, _("Could not add unavailable time block."))

        elif action == "delete_unavailable_block":
            block_id = request.POST.get("block_id")
            salon.unavailable_time_blocks.filter(pk=block_id).delete()
            messages.success(request, _("Unavailable time block removed."))

        elif action == "mark_completed":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            booking.status = Booking.Status.COMPLETED
            booking.save()
            log_booking_activity(booking, BookingActivityLog.Action.COMPLETED, user=request.user)
            messages.success(request, _("Booking marked as completed."))

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
            messages.success(request, _("Booking marked as no-show."))

        elif action in ("cancel_booking", "cancel"):
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            if booking.status in {Booking.Status.COMPLETED, Booking.Status.NO_SHOW}:
                messages.warning(request, _("Cannot cancel a completed or no-show booking."))
            else:
                booking.status = Booking.Status.CANCELLED
                booking.save()
                log_booking_activity(booking, BookingActivityLog.Action.CANCELLED, user=request.user)
                sent, reason = send_booking_notification(booking, "cancelled")
                if sent:
                    log_booking_activity(booking, BookingActivityLog.Action.EMAIL_SENT, user=request.user, note="Cancellation email sent")
                    messages.success(request, _("Appointment cancelled. Email sent to customer."))
                elif reason == "no_email":
                    messages.success(request, _("Appointment cancelled. Customer did not provide an email."))
                else:
                    messages.success(request, _("Appointment cancelled."))
                    messages.warning(request, _("Email could not be sent. Prepared message is available."))

        elif action == "delete_booking":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            booking.delete()
            messages.success(request, _("Booking deleted."))

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
                if service:
                    messages.success(request, _("Service updated successfully."))
                else:
                    messages.success(request, _("Service added successfully."))
            else:
                messages.error(request, _("Could not save service. Check the form."))

        elif action == "delete_service":
            service = get_object_or_404(
                Service, pk=request.POST.get("service_id"), salon=salon
            )
            service.delete()
            messages.success(request, _("Service deleted."))

        elif action == "save_price_item":
            service = get_object_or_404(
                Service, pk=request.POST.get("service_id"), salon=salon
            )
            item_id = request.POST.get("item_id")
            item = get_object_or_404(ServicePriceItem, pk=item_id, service__salon=salon) if item_id else None
            name = request.POST.get("item_name", "").strip()
            price = request.POST.get("item_price", "").strip()
            group = request.POST.get("item_group", "").strip()
            sort_order = int(request.POST.get("item_sort", 0) or 0)
            photo_required = request.POST.get("item_photo_required") == "1"
            if name and price:
                if item:
                    item.name = name
                    item.price_display = price
                    item.group = group
                    item.sort_order = sort_order
                    item.photo_required = photo_required
                    item.save()
                else:
                    ServicePriceItem.objects.create(
                        service=service, name=name, price_display=price,
                        group=group, sort_order=sort_order,
                        photo_required=photo_required,
                    )
                messages.success(request, _("Price item saved."))
            else:
                messages.error(request, _("Name and price are required."))

        elif action == "delete_price_item":
            item = get_object_or_404(
                ServicePriceItem, pk=request.POST.get("item_id"), service__salon=salon
            )
            item.delete()
            messages.success(request, _("Price item deleted."))

        elif action == "reorder_price_items":
            raw_ids = request.POST.get("item_ids", "")
            ids = [i.strip() for i in raw_ids.split(",") if i.strip().isdigit()]
            for sort_index, item_id in enumerate(ids):
                ServicePriceItem.objects.filter(
                    pk=item_id, service__salon=salon
                ).update(sort_order=sort_index)
            # AJAX call — return 204 with no redirect
            from django.http import HttpResponse
            return HttpResponse(status=204)

        elif action == "save_customer":
            customer = None
            customer_id = request.POST.get("customer_id")
            if customer_id:
                customer = get_object_or_404(Customer, pk=customer_id, salon=salon)
            form = OwnerCustomerForm(request.POST, instance=customer, salon=salon)
            if form.is_valid():
                form.save()
                if customer:
                    messages.success(request, _("Customer updated successfully."))
                else:
                    messages.success(request, _("Customer added successfully."))
            else:
                messages.error(request, _("Could not save customer."))

        elif action == "delete_customer":
            customer = get_object_or_404(
                Customer, pk=request.POST.get("customer_id"), salon=salon
            )
            if customer.bookings.exists():
                messages.error(
                    request,
                    _("Cannot delete a customer with existing bookings. Remove bookings first."),
                )
            else:
                customer.delete()
                messages.success(request, _("Customer deleted."))

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
                messages.success(request, _("Blocked date saved."))
            else:
                messages.error(request, _("Invalid blocked date."))

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
                    if block:
                        messages.success(request, _("Time block updated."))
                    else:
                        messages.success(request, _("Time block added."))
            else:
                messages.error(request, _("Could not save unavailable time block."))

        else:
            messages.error(request, _("Unknown action."))

        # AJAX path: return JSON so JS can update UI without reload
        if request.headers.get("X-Requested-With") == "fetch":
            booking_obj = None
            if action in ("approve", "reject", "mark_completed", "mark_no_show", "cancel", "cancel_booking"):
                try:
                    booking_obj = Booking.objects.get(
                        pk=request.POST.get("booking_id"), salon=salon
                    )
                except Exception:
                    pass
            response_data = {"ok": True, "action": action}
            if booking_obj:
                response_data.update({
                    "booking_id": booking_obj.id,
                    "new_status": booking_obj.status,
                    "new_status_display": booking_obj.get_status_display(),
                })
            # Fresh counts so the UI can update overview stats without reload
            today_date = timezone.localdate()
            response_data["pending_count"] = salon.bookings.filter(
                status=Booking.Status.PENDING
            ).count()
            response_data["today_count"] = salon.bookings.filter(
                status=Booking.Status.APPROVED,
                start_at__date=today_date,
            ).count()
            # Include any Django messages
            msg_list = [(m.level_tag, str(m)) for m in messages.get_messages(request)]
            response_data["messages"] = msg_list
            return JsonResponse(response_data)

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
        local_start = timezone.localtime(booking.start_at)
        local_end   = timezone.localtime(booking.end_at)
        events.append(
            {
                "id": f"booking-{booking.id}",
                "title": booking.customer.full_name,
                "start": local_start.isoformat(),
                "end": local_end.isoformat(),
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
                    "hasReferencePhoto": bool(booking.reference_photo),
                    "cancelledByCustomer": booking.cancelled_by_customer,
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
            "cancelled_by_customer": booking.cancelled_by_customer,
            "source": booking.source,
            "customer_note": booking.customer_note,
            "owner_note": booking.owner_note,
            "has_reference_photo": bool(booking.reference_photo),
            "reference_photo_url": (
                reverse("booking:owner_booking_photo", args=[booking.id])
                if booking.reference_photo
                else None
            ),
            "created_at": booking.created_at.isoformat(),
            "updated_at": booking.updated_at.isoformat(),
            "activity_log": activity,
        }
    )


@login_required
@require_GET
def owner_booking_photo(request, booking_id):
    """Serve a booking reference photo only to the salon owner."""
    salon = _get_owner_salon(request.user)
    if not salon:
        return HttpResponseForbidden()
    booking = get_object_or_404(Booking, pk=booking_id, salon=salon)
    if not booking.reference_photo:
        raise Http404
    try:
        photo_file = booking.reference_photo.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    content_type = "image/jpeg"
    name = booking.reference_photo.name.lower()
    if name.endswith(".png"):
        content_type = "image/png"
    elif name.endswith(".webp"):
        content_type = "image/webp"
    return FileResponse(photo_file, content_type=content_type)


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

    services = salon.services.filter(is_active=True).prefetch_related("price_items")
    return render(
        request,
        "booking/salon_page.html",
        {
            "salon": salon,
            "services": services,
            "working_hours": working_hours,
            "booking_policy": policy,
        },
    )


def _ensure_booking_device_cookie(response, request):
    if DEVICE_COOKIE_NAME not in request.COOKIES:
        response.set_cookie(
            DEVICE_COOKIE_NAME,
            uuid.uuid4().hex,
            max_age=DEVICE_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
        )
    return response


def book_salon(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)
    policy = getattr(salon, "booking_policy", None)
    today = date.today()
    min_notice = policy.minimum_notice_days if policy else 14
    max_window = policy.maximum_booking_window_days if policy else 60

    # Ensure working hours exist so we can derive closed weekdays
    working_hours = salon.working_hours.order_by("weekday")
    if not working_hours.exists():
        ensure_default_working_hours(salon)
        working_hours = salon.working_hours.order_by("weekday")

    # Convert Django weekday (0=Mon…6=Sun) → JS day (0=Sun, 1=Mon…6=Sat)
    closed_weekdays_js = [(wh.weekday + 1) % 7 for wh in working_hours if not wh.is_working_day]
    # If salon has no Sunday record, add JS Sunday (0) as closed by default
    if not working_hours.filter(weekday=6).exists() and 0 not in closed_weekdays_js:
        closed_weekdays_js.append(0)

    if request.method == "POST":
        form = BookingRequestForm(request.POST, request.FILES, salon=salon, request=request)
        if form.is_valid():
            booking = form.save()
            log_booking_activity(
                booking,
                BookingActivityLog.Action.REQUESTED,
                note="Online booking request",
            )
            sent, _reason = send_booking_notification(booking, "request_received")
            if sent:
                log_booking_activity(
                    booking,
                    BookingActivityLog.Action.EMAIL_SENT,
                    note="Request received email sent to customer",
                )
            sent, _reason = send_owner_new_booking_notification(booking)
            if sent:
                log_booking_activity(
                    booking,
                    BookingActivityLog.Action.EMAIL_SENT,
                    note="Owner notified of new request",
                )
            response = redirect(reverse("booking:booking_success", args=[booking.pk]))
            return _ensure_booking_device_cookie(response, request)
    else:
        form = BookingRequestForm(salon=salon, request=request)

    response = render(
        request,
        "booking/booking_form.html",
        {
            "salon": salon,
            "form": form,
            "services": salon.services.filter(is_active=True).prefetch_related("price_items"),
            "min_date": (today + timedelta(days=min_notice)).isoformat(),
            "max_date": (today + timedelta(days=max_window)).isoformat(),
            "booking_policy": policy,
            "closed_weekdays_js": json.dumps(closed_weekdays_js),
        },
    )
    return _ensure_booking_device_cookie(response, request)


def booking_success(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related("salon", "customer").prefetch_related("booking_services"),
        pk=booking_id,
    )

    return render(
        request,
        "booking/booking_success.html",
        {
            "booking": booking,
            "manage_url": get_manage_booking_url(booking),
        },
    )


def _manage_booking_status_message(booking):
    messages_map = {
        Booking.Status.PENDING: _(
            "Your request is not confirmed yet. The salon will review it and contact you."
        ),
        Booking.Status.APPROVED: _("Your appointment is confirmed."),
        Booking.Status.REJECTED: _("Your booking request was declined."),
        Booking.Status.CANCELLED: _("This appointment was cancelled."),
        Booking.Status.COMPLETED: _("This appointment was completed."),
        Booking.Status.NO_SHOW: _("This appointment was marked as a no-show."),
    }
    return messages_map.get(booking.status, "")


def manage_booking(request, token):
    booking = get_object_or_404(
        Booking.objects.select_related("salon", "customer").prefetch_related("booking_services"),
        manage_token=token,
    )
    policy = getattr(booking.salon, "booking_policy", None)
    salon_rules = []
    if policy and policy.salon_rules:
        salon_rules = [line.strip() for line in policy.salon_rules.splitlines() if line.strip()]

    can_cancel, cancel_reason = can_customer_cancel_booking(booking)
    notice_hours = 24
    if policy:
        notice_hours = policy.customer_cancellation_notice_hours

    return render(
        request,
        "booking/manage_booking.html",
        {
            "booking": booking,
            "status_message": _manage_booking_status_message(booking),
            "can_cancel": can_cancel,
            "cancel_reason": cancel_reason,
            "notice_hours": notice_hours,
            "salon_rules": salon_rules,
            "just_cancelled": request.GET.get("cancelled") == "1",
            "show_confirm": request.GET.get("confirm") == "1",
            "manage_url": get_manage_booking_url(booking),
        },
    )


@require_POST
def manage_booking_cancel(request, token):
    booking = get_object_or_404(
        Booking.objects.select_related("salon", "customer").prefetch_related("booking_services"),
        manage_token=token,
    )

    if request.POST.get("confirm") != "yes":
        return redirect(reverse("booking:manage_booking", args=[token]))

    allowed, reason = can_customer_cancel_booking(booking)
    if not allowed:
        if reason == "too_close":
            messages.error(
                request,
                _(
                    "This appointment is too close for automatic cancellation. "
                    "Please contact the salon."
                ),
            )
        elif reason == "past":
            messages.error(request, _("This appointment has already passed."))
        else:
            messages.error(request, _("This appointment cannot be cancelled."))
        return redirect(reverse("booking:manage_booking", args=[token]))

    booking.status = Booking.Status.CANCELLED
    booking.cancelled_by_customer = True
    try:
        booking.save()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect(reverse("booking:manage_booking", args=[token]))

    log_booking_activity(
        booking,
        BookingActivityLog.Action.CUSTOMER_CANCELLED,
        note="Cancelled by customer via manage link",
    )

    send_booking_notification(booking, "customer_cancelled")
    send_owner_customer_cancelled_notification(booking)

    return redirect(f"{reverse('booking:manage_booking', args=[token])}?cancelled=1")


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
