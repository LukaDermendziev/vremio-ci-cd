import json
import uuid
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .anti_abuse import (
    DEVICE_COOKIE_MAX_AGE,
    DEVICE_COOKIE_NAME,
    get_client_ip,
    get_device_token,
    record_booking_attempt,
)
from .customer_blocking import (
    block_customer as block_customer_service,
    get_active_block_entry,
    resolve_customer_for_block,
    serialize_blocklist_entry,
    unblock_customer as unblock_customer_service,
    update_customer_block,
)
from .legal_utils import get_vremio_contact_email
from .email_utils import send_plan_interest_email
from .forms import (
    BlockedDateForm,
    BookingPolicyForm,
    normalize_policy_post_data,
    BookingRequestForm,
    BookingSmsOtpForm,
    OwnerBookingForm,
    OwnerCustomerForm,
    PlanInterestForm,
    SalonPublicHoursDisplayForm,
    ServiceForm,
    UnavailableTimeBlockForm,
    WorkingHoursFormSet,
)
from .pricing_plans import PRICING_FAQ, PRICING_PLANS
from .models import (
    Booking,
    BookingActivityLog,
    Customer,
    CustomerBlocklist,
    DateWorkingHoursOverride,
    Service,
    ServicePriceItem,
    Salon,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import (
    booking_visible_on_calendar,
    build_contact_links,
    build_prepared_message,
    build_service_schedule,
    can_customer_cancel_booking,
    complete_email_verification,
    cleanup_expired_unverified_bookings,
    defer_after_commit,
    delete_unverified_booking,
    ensure_default_working_hours,
    format_services_label,
    get_available_slots,
    get_booking_total_price_display,
    get_calendar_history_cutoff_date,
    get_manage_booking_url,
    get_revenue_stats,
    get_salon_local_today,
    get_salon_page_hours_rows,
    get_active_released_intervals,
    get_last_minute_open_dates_for_services,
    get_unbookable_dates_for_customer,
    get_working_window_for_date,
    is_date_allowed,
    log_booking_activity,
    MSG_MULTI_SERVICE_NO_FIT,
    parse_service_ids_param,
    process_new_online_booking_emails,
    send_verification_email_for_booking,
    send_verification_sms_for_booking,
    complete_booking_verification,
    release_booking_slot,
    resolve_services_for_salon,
    send_booking_notification,
    send_owner_customer_cancelled_notification,
    send_owner_new_booking_notification,
)


def _services_from_request(request, salon):
    raw = request.GET.get("services") or request.GET.get("service")
    service_ids = parse_service_ids_param(raw)
    return resolve_services_for_salon(salon, service_ids) or []


def _slots_json(slots, *, last_minute=False, release_unavailable=False):
    return JsonResponse(
        {
            "slots": [
                {
                    "value": slot["value"],
                    "label": slot["label"],
                    "end": slot["end"].strftime("%H:%M"),
                }
                for slot in slots
            ],
            "last_minute": last_minute,
            "release_unavailable": release_unavailable,
        }
    )


def health(request):
    return HttpResponse("ok", content_type="text/plain")


@require_GET
def favicon(request):
    """Serve the salon or platform .ico based on Host (browsers often hit /favicon.ico)."""
    from .domain_utils import is_customer_domain

    name = "salon-favicon.ico" if is_customer_domain(request) else "vremio-favicon.ico"
    path = finders.find(name) or finders.find("favicon.ico")
    if not path:
        raise Http404("favicon not found")
    response = FileResponse(open(path, "rb"), content_type="image/x-icon")
    response["Cache-Control"] = "public, max-age=86400"
    return response


def home(request):
    businesses = Salon.objects.filter(is_active=True).order_by("name")
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip() or "all"

    return render(
        request,
        "booking/home.html",
        {
            "businesses": businesses,
            "q": q,
            "category": category,
            "category_choices": Salon.BusinessCategory,
            "contact_email": get_vremio_contact_email(),
            "pricing_plans": PRICING_PLANS,
            "pricing_faq": PRICING_FAQ,
            "plan_interest_form": PlanInterestForm(),
        },
    )


@require_POST
def plan_interest(request):
    """Receive owner plan-interest leads from the landing page."""
    from django.core.cache import cache

    wants_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )

    ip = get_client_ip(request) or "unknown"
    rate_key = f"plan_interest:{ip}"
    try:
        hits = cache.get(rate_key, 0) or 0
    except Exception:
        hits = 0
    if hits >= 5:
        message = _("You have sent too many requests in a short time. Please try again later.")
        if wants_json:
            return JsonResponse({"ok": False, "error": str(message)}, status=429)
        messages.error(request, message)
        return redirect("/#plans")

    form = PlanInterestForm(request.POST)
    if not form.is_valid():
        if wants_json:
            errors = {
                field: [str(e) for e in errs] for field, errs in form.errors.items()
            }
            non_field = [str(e) for e in form.non_field_errors()]
            return JsonResponse(
                {
                    "ok": False,
                    "errors": errors,
                    "error": non_field[0] if non_field else _("Please check the form."),
                },
                status=400,
            )
        messages.error(request, _("Please check the form."))
        return redirect("/#plans")

    data = form.cleaned_data
    plan_label = dict(form.fields["plan"].choices).get(data["plan"], data["plan"])
    sent, reason = send_plan_interest_email(
        name=data["name"],
        plan_label=str(plan_label),
        instagram=data.get("instagram") or "",
        phone=data.get("phone") or "",
    )
    try:
        cache.set(rate_key, hits + 1, timeout=3600)
    except Exception:
        pass

    if not sent:
        message = _(
            "We couldn’t send your request right now. Please email us or try again later."
        )
        if wants_json:
            return JsonResponse({"ok": False, "error": str(message)}, status=503)
        messages.error(request, message)
        return redirect("/#plans")

    success = _("Thanks — we received your request and will contact you soon.")
    if wants_json:
        return JsonResponse({"ok": True, "message": str(success)})
    messages.success(request, success)
    return redirect("/#plans")


def _legal_page_context():
    return {
        "contact_email": get_vremio_contact_email(),
        "last_updated": "2026-06-21",
    }


def privacy_policy(request):
    return render(request, "booking/legal/privacy.html", _legal_page_context())


def terms_of_use(request):
    return render(request, "booking/legal/terms.html", _legal_page_context())


def booking_rules(request):
    return render(request, "booking/legal/booking_rules.html", _legal_page_context())


def photo_policy(request):
    return render(request, "booking/legal/photo_policy.html", _legal_page_context())


def contact_data_requests(request):
    return render(request, "booking/legal/contact.html", _legal_page_context())


def owner_pilot_terms(request):
    return render(request, "booking/legal/owner_pilot_terms.html", _legal_page_context())


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
    blocked_customers = (
        salon.customer_blocklist_entries.filter(is_active=True)
        .select_related("customer", "blocked_by", "source_booking")
        .order_by("-blocked_at", "-created_at")
    )
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
        "blocked_customers": blocked_customers,
        "revenue": revenue,
        "policy_form": BookingPolicyForm(instance=booking_policy) if booking_policy else None,
        "blocked_date_form": BlockedDateForm(),
        "unavailable_block_form": UnavailableTimeBlockForm(salon=salon),
        "owner_booking_form": OwnerBookingForm(salon=salon),
        "service_form": ServiceForm(salon=salon),
        "customer_form": OwnerCustomerForm(salon=salon),
        "block_reason_choices": CustomerBlocklist.ReasonCode.choices,
    }


@never_cache
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

    return render(
        request,
        "booking/auth/login.html",
        {
            "error": error,
            "logged_out": request.GET.get("logged_out") == "1",
        },
    )


@never_cache
def owner_logout(request):
    auth_logout(request)
    return render(request, "booking/auth/logout_redirect.html")


@never_cache
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
        policy_form_errors = None

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
                release_booking_slot(booking)
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

        elif action == "save_public_hours_display":
            form = SalonPublicHoursDisplayForm(request.POST, instance=salon)
            if form.is_valid():
                form.save()
                messages.success(request, _("Public salon page hours saved."))
            else:
                messages.error(request, _("Could not save public salon page hours."))

        elif action == "save_policy":
            policy = getattr(salon, "booking_policy", None)
            if not policy:
                messages.error(request, _("No booking policy found for this salon."))
            else:
                form = BookingPolicyForm(
                    normalize_policy_post_data(request.POST),
                    instance=policy,
                )
                if form.is_valid():
                    form.save()
                    messages.success(request, _("Booking policy saved."))
                else:
                    messages.error(request, _("Could not save booking policy."))
                    policy_form_errors = {
                        field: [str(error) for error in errors]
                        for field, errors in form.errors.items()
                    }
                    for field_name, errors in form.errors.items():
                        if field_name == "__all__":
                            field_label = _("General")
                        else:
                            field_label = form.fields.get(field_name).label if form.fields.get(field_name) else field_name
                        for error in errors:
                            messages.error(
                                request,
                                _("%(field)s: %(error)s")
                                % {"field": field_label, "error": error},
                            )

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
                release_booking_slot(booking)
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
            release_booking_slot(booking)
            booking.delete()
            messages.success(request, _("Booking deleted."))

        elif action == "delete_reference_photo":
            booking = get_object_or_404(
                Booking, pk=request.POST.get("booking_id"), salon=salon
            )
            if booking.reference_photo:
                booking.reference_photo.delete(save=False)
                booking.reference_photo_status = Booking.ReferencePhotoStatus.REMOVED
                booking.save(update_fields=["reference_photo", "reference_photo_status"])
                log_booking_activity(
                    booking,
                    BookingActivityLog.Action.PHOTO_REMOVED,
                    user=request.user,
                )
                messages.success(request, _("Photo removed."))
            else:
                messages.info(request, _("No photo attached to this booking."))

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
            messages.success(request, _("Price list order saved."))

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

        if request.headers.get("X-Requested-With") == "fetch":
            from .owner_ajax import build_owner_ajax_payload, messages_to_list, response_is_ok

            msg_list = messages_to_list(request)
            ok = response_is_ok(msg_list)
            payload = build_owner_ajax_payload(salon, action, request)
            stats = payload.get("stats", {})
            response_data = {
                "ok": ok,
                "action": action,
                "section": request.POST.get("return_section", "dashboard"),
                "messages": msg_list,
                "payload": payload,
                "pending_count": stats.get("pending_count", 0),
                "today_count": stats.get("today_count", 0),
            }
            booking_data = payload.get("booking")
            if booking_data:
                response_data.update(
                    {
                        "booking_id": booking_data["id"],
                        "new_status": booking_data["status"],
                        "new_status_display": booking_data["status_display"],
                        "has_reference_photo": booking_data["has_reference_photo"],
                    }
                )
            if policy_form_errors is not None:
                response_data["form_errors"] = policy_form_errors
            return JsonResponse(response_data, status=200 if ok else 400)

        section = request.POST.get("return_section", "dashboard")
        return redirect(f"{reverse('booking:owner_dashboard')}#{section}")

    context = _owner_dashboard_context(salon)
    context["hours_formset"] = WorkingHoursFormSet(
        queryset=salon.working_hours.order_by("weekday")
    )
    context["public_hours_form"] = SalonPublicHoursDisplayForm(instance=salon)
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
            "customer_block_entry": get_active_block_entry(salon, customer),
            "block_reason_choices": CustomerBlocklist.ReasonCode.choices,
        },
    )


def _json_block_error(exc):
    if isinstance(exc, ValidationError):
        if hasattr(exc, "message_dict"):
            messages_list = []
            for msgs in exc.message_dict.values():
                messages_list.extend(msgs if isinstance(msgs, list) else [msgs])
            return JsonResponse({"ok": False, "error": " ".join(str(m) for m in messages_list)}, status=400)
        if hasattr(exc, "messages"):
            return JsonResponse({"ok": False, "error": " ".join(str(m) for m in exc.messages)}, status=400)
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def owner_block_customer(request):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)

    customer_id = request.POST.get("customer_id")
    booking_id = request.POST.get("booking_id")
    reason_code = (request.POST.get("reason_code") or "").strip()
    notes = (request.POST.get("notes") or "").strip()

    try:
        customer, booking = resolve_customer_for_block(
            salon=salon,
            customer_id=customer_id,
            booking_id=booking_id,
        )
        entry = block_customer_service(
            salon=salon,
            performed_by=request.user,
            reason_code=reason_code,
            notes=notes,
            customer=customer,
            booking=booking,
        )
        if booking:
            log_booking_activity(
                booking,
                BookingActivityLog.Action.CUSTOMER_BLOCKED,
                user=request.user,
                note=entry.get_reason_display_label(),
            )
    except (ValidationError, Booking.DoesNotExist, Customer.DoesNotExist) as exc:
        return _json_block_error(exc)

    return JsonResponse({"ok": True, "entry": serialize_blocklist_entry(entry)})


@login_required
@require_GET
def owner_customer_block_detail(request, entry_id):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    entry = get_object_or_404(
        CustomerBlocklist.objects.select_related("customer", "blocked_by", "source_booking"),
        pk=entry_id,
        salon=salon,
    )
    events = [
        {
            "event_type": event.event_type,
            "event_label": event.get_event_type_display(),
            "performed_by": (
                event.performed_by.get_full_name() or event.performed_by.username
                if event.performed_by
                else "System"
            ),
            "reason_code": event.reason_code,
            "notes": event.notes,
            "created_at": event.created_at.isoformat(),
        }
        for event in entry.events.select_related("performed_by").order_by("-created_at")[:20]
    ]
    data = serialize_blocklist_entry(entry)
    data["events"] = events
    return JsonResponse(data)


@login_required
@require_POST
def owner_unblock_customer(request, entry_id):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)

    entry = get_object_or_404(CustomerBlocklist, pk=entry_id, salon=salon)
    try:
        entry = unblock_customer_service(entry=entry, performed_by=request.user)
    except ValidationError as exc:
        return _json_block_error(exc)

    return JsonResponse({"ok": True, "entry": serialize_blocklist_entry(entry)})


@login_required
@require_POST
def owner_update_customer_block(request, entry_id):
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"ok": False, "error": "Unauthorized"}, status=403)

    entry = get_object_or_404(CustomerBlocklist, pk=entry_id, salon=salon)
    reason_code = (request.POST.get("reason_code") or "").strip()
    notes = (request.POST.get("notes") or "").strip()

    try:
        entry = update_customer_block(
            entry=entry,
            performed_by=request.user,
            reason_code=reason_code,
            notes=notes,
        )
    except ValidationError as exc:
        return _json_block_error(exc)

    return JsonResponse({"ok": True, "entry": serialize_blocklist_entry(entry)})


@login_required
@require_GET
def owner_customer_block_context(request):
    """Return block modal context for a customer or booking."""
    salon = _get_owner_salon(request.user)
    if not salon:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    customer_id = request.GET.get("customer_id")
    booking_id = request.GET.get("booking_id")
    try:
        customer, booking = resolve_customer_for_block(
            salon=salon,
            customer_id=customer_id,
            booking_id=booking_id,
        )
    except (ValidationError, Booking.DoesNotExist, Customer.DoesNotExist) as exc:
        return _json_block_error(exc)

    entry = get_active_block_entry(salon, customer)
    data = {
        "customer_id": customer.id,
        "customer_name": customer.full_name,
        "phone_number": customer.phone_number,
        "email": customer.email or "",
        "instagram_username": customer.instagram_username or "",
        "is_blocked": bool(entry),
        "block_entry_id": entry.id if entry else None,
        "booking_id": booking.id if booking else None,
        "booking_reference": (
            f"#{booking.id} · {timezone.localtime(booking.start_at):%d/%m/%Y %H:%M}"
            if booking
            else ""
        ),
        "reason_choices": [
            {"value": value, "label": str(label)}
            for value, label in CustomerBlocklist.ReasonCode.choices
        ],
    }
    return JsonResponse(data)


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

    calendar_cutoff = get_calendar_history_cutoff_date(salon)

    events = []
    bookings = salon.bookings.filter(
        start_at__lt=range_end,
        end_at__gt=range_start,
    ).exclude(
        status=Booking.Status.UNVERIFIED,
    ).select_related("customer").prefetch_related("booking_services")

    for booking in bookings:
        if not booking_visible_on_calendar(booking, calendar_cutoff):
            continue
        services = ", ".join(
            item.service_name_snapshot for item in booking.booking_services.all()
        )
        services_label = format_services_label(booking)
        style = status_styles.get(booking.status, status_styles[Booking.Status.APPROVED])
        local_start = timezone.localtime(booking.start_at)
        local_end   = timezone.localtime(booking.end_at)
        title = booking.customer.full_name
        if services_label:
            title = f"{booking.customer.full_name} — {services_label}"
        events.append(
            {
                "id": f"booking-{booking.id}",
                "title": title,
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
                    "servicesLabel": services_label,
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
    booking_service_items = list(booking.booking_services.all())
    schedule = build_service_schedule(booking.start_at, booking_service_items, salon)

    services_list = [
        {
            "service_id": bs.service_id,
            "name": bs.service_name_snapshot,
            "duration": bs.duration_minutes_snapshot,
            "price": str(bs.price_snapshot),
            "start_time": schedule[index]["start_time"] if index < len(schedule) else "",
            "end_time": schedule[index]["end_time"] if index < len(schedule) else "",
        }
        for index, bs in enumerate(booking_service_items)
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

    block_entry = get_active_block_entry(salon, booking.customer)

    return JsonResponse(
        {
            "id": booking.id,
            "customer_id": booking.customer_id,
            "full_name": booking.customer.full_name,
            "phone_number": booking.customer.phone_number,
            "instagram_username": booking.customer.instagram_username,
            "email": booking.customer.email,
            "preferred_contact_method": booking.customer.preferred_contact_method,
            "service_id": first_service.service_id if first_service else None,
            "service_ids": [bs.service_id for bs in booking_service_items],
            "services": services_list,
            "service_schedule": schedule,
            "services_label": format_services_label(booking),
            "total_price_display": get_booking_total_price_display(booking),
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
            "is_customer_blocked": bool(block_entry),
            "booking_reference": f"#{booking.id} · {local_start:%d/%m/%Y %H:%M}",
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
    return FileResponse(
        photo_file,
        content_type=content_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
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
        "PRODID:-//Vremio//EN",
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

    date_value = request.GET.get("date")
    exclude_id = request.GET.get("exclude")
    services = _services_from_request(request, salon)

    if not services or not date_value:
        return JsonResponse({"slots": []})

    try:
        selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": []})

    exclude_booking_id = None
    if exclude_id:
        if Booking.objects.filter(pk=exclude_id, salon=salon).exists():
            exclude_booking_id = exclude_id

    slots = get_available_slots(
        salon,
        services,
        selected_date,
        for_owner=True,
        exclude_booking_id=exclude_booking_id,
    )
    return _slots_json(slots)


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
            "hours_display_rows": get_salon_page_hours_rows(salon, working_hours),
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
    today = get_salon_local_today(salon)
    min_notice = policy.minimum_notice_days if policy else 14
    max_window = policy.maximum_booking_window_days if policy else 60
    min_date_val = today + timedelta(days=min_notice)
    max_date_val = today + timedelta(days=max_window)

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
        cleanup_expired_unverified_bookings(salon=salon)
        form = BookingRequestForm(request.POST, request.FILES, salon=salon, request=request)
        if form.is_valid():
            booking = form.save()
            policy = getattr(salon, "booking_policy", None)
            record_booking_attempt(
                salon.id,
                policy,
                get_client_ip(request),
                form.cleaned_data["phone_number"],
                form.cleaned_data.get("email", ""),
                get_device_token(request),
            )
            if getattr(form, "sms_verification_required", False):
                request.session["booking_verify_id"] = booking.pk
                sent, _reason = send_verification_sms_for_booking(booking)
                request.session["booking_verify_sms_failed"] = not sent
                response = redirect(reverse("booking:booking_verify_sms"))
            elif getattr(form, "verification_required", False):
                request.session["booking_verify_id"] = booking.pk
                sent, _reason = send_verification_email_for_booking(booking)
                request.session["booking_verify_email_failed"] = not sent
                response = redirect(reverse("booking:booking_verify_email_sent"))
            else:
                defer_after_commit(process_new_online_booking_emails, booking.pk)
                request.session["booking_success_id"] = booking.pk
                response = redirect(reverse("booking:booking_success"))
            return _ensure_booking_device_cookie(response, request)
    else:
        cleanup_expired_unverified_bookings(salon=salon)
        form = BookingRequestForm(salon=salon, request=request)

    response = render(
        request,
        "booking/booking_form.html",
        {
            "salon": salon,
            "form": form,
            "services": salon.services.filter(is_active=True).prefetch_related("price_items"),
            "min_date": min_date_val.isoformat(),
            "max_date": max_date_val.isoformat(),
            "booking_policy": policy,
            "closed_weekdays_js": json.dumps(closed_weekdays_js),
            "closed_dates_js": json.dumps(
                get_unbookable_dates_for_customer(salon, min_date_val, max_date_val)
            ),
            "multi_service_no_fit_message": str(MSG_MULTI_SERVICE_NO_FIT),
        },
    )
    return _ensure_booking_device_cookie(response, request)


def booking_success(request):
    """Show booking confirmation only to the browser that just submitted the request."""
    booking_id = request.session.pop("booking_success_id", None)
    if not booking_id:
        raise Http404

    booking = get_object_or_404(
        Booking.objects.select_related("salon", "customer").prefetch_related("booking_services"),
        pk=booking_id,
    )
    if booking.status == Booking.Status.UNVERIFIED:
        raise Http404

    return render(
        request,
        "booking/booking_success.html",
        {
            "booking": booking,
            "manage_url": get_manage_booking_url(booking),
        },
    )


def booking_success_legacy(request, booking_id):
    """Deprecated enumerable URL — always forbidden."""
    raise Http404


def booking_verify_email_sent(request):
    booking_id = request.session.get("booking_verify_id")
    booking = None
    if booking_id:
        booking = (
            Booking.objects.filter(
                pk=booking_id,
                status=Booking.Status.UNVERIFIED,
            )
            .select_related("customer", "salon")
            .first()
        )
    email_failed = request.session.pop("booking_verify_email_failed", False)
    return render(
        request,
        "booking/booking_verify_email_sent.html",
        {
            "booking": booking,
            "can_resend": booking is not None,
            "email_failed": email_failed,
        },
    )


@require_POST
def resend_booking_verification_email(request):
    booking_id = request.session.get("booking_verify_id")
    if not booking_id:
        raise Http404

    booking = get_object_or_404(
        Booking.objects.select_related("customer", "salon"),
        pk=booking_id,
        status=Booking.Status.UNVERIFIED,
    )

    last_resend = request.session.get("booking_verify_resend_at")
    if last_resend and (timezone.now().timestamp() - float(last_resend)) < 60:
        messages.error(
            request,
            _("Please wait a minute before requesting another verification email."),
        )
        return redirect(reverse("booking:booking_verify_email_sent"))

    sent, _reason = send_verification_email_for_booking(booking)
    request.session["booking_verify_resend_at"] = timezone.now().timestamp()
    request.session["booking_verify_email_failed"] = not sent
    if sent:
        messages.success(
            request,
            _("We sent another verification email. Please check your inbox and spam folder."),
        )
    else:
        messages.error(
            request,
            _(
                "We could not send the verification email right now. "
                "Please try again in a few minutes or contact the salon."
            ),
        )
    return redirect(reverse("booking:booking_verify_email_sent"))


def booking_verify_sms(request):
    booking_id = request.session.get("booking_verify_id")
    booking = None
    if booking_id:
        booking = (
            Booking.objects.filter(
                pk=booking_id,
                status=Booking.Status.UNVERIFIED,
            )
            .select_related("customer", "salon")
            .first()
        )

    sms_failed = request.session.pop("booking_verify_sms_failed", False)
    form = BookingSmsOtpForm()
    otp_error = ""

    if request.method == "POST" and booking:
        form = BookingSmsOtpForm(request.POST)
        if form.is_valid():
            from .sms_utils import verify_booking_sms_otp

            if booking.verification_expires_at and booking.verification_expires_at < timezone.now():
                log_booking_activity(
                    booking,
                    BookingActivityLog.Action.VERIFICATION_EXPIRED,
                    note="SMS verification code expired",
                )
                delete_unverified_booking(booking)
                request.session.pop("booking_verify_id", None)
                return render(
                    request,
                    "booking/booking_verify_failed.html",
                    {
                        "reason": "expired",
                        "message": _(
                            "The verification code has expired. Please submit a new booking request."
                        ),
                        "salon": booking.salon,
                    },
                )

            code = form.cleaned_data["otp_code"]
            if not verify_booking_sms_otp(booking, code):
                otp_error = _("The code is incorrect. Please try again.")
            else:
                success, reason = complete_booking_verification(booking, channel="sms")
                if not success:
                    if reason == "slot_unavailable":
                        delete_unverified_booking(booking)
                        request.session.pop("booking_verify_id", None)
                        return render(
                            request,
                            "booking/booking_verify_failed.html",
                            {
                                "reason": "slot_unavailable",
                                "message": _(
                                    "The selected time slot is no longer available. "
                                    "Please choose another time."
                                ),
                                "salon": booking.salon,
                            },
                        )
                    delete_unverified_booking(booking)
                    request.session.pop("booking_verify_id", None)
                    return render(
                        request,
                        "booking/booking_verify_failed.html",
                        {
                            "reason": reason,
                            "message": _(
                                "Something went wrong. Please submit a new booking request."
                            ),
                            "salon": booking.salon,
                        },
                    )

                booking.refresh_from_db()
                request.session.pop("booking_verify_id", None)
                log_booking_activity(
                    booking,
                    BookingActivityLog.Action.PHONE_VERIFIED,
                    note="Phone verified — booking request submitted",
                )
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
                        note="Request received notification sent to customer",
                    )
                sent, _reason = send_owner_new_booking_notification(booking)
                if sent:
                    log_booking_activity(
                        booking,
                        BookingActivityLog.Action.EMAIL_SENT,
                        note="Owner notified of new request",
                    )
                return render(
                    request,
                    "booking/booking_verify_success.html",
                    {
                        "booking": booking,
                        "salon": booking.salon,
                    },
                )

    return render(
        request,
        "booking/booking_verify_sms.html",
        {
            "booking": booking,
            "form": form,
            "can_resend": booking is not None,
            "sms_failed": sms_failed,
            "otp_error": otp_error,
        },
    )


@require_POST
def resend_booking_verification_sms(request):
    booking_id = request.session.get("booking_verify_id")
    if not booking_id:
        raise Http404

    booking = get_object_or_404(
        Booking.objects.select_related("customer", "salon"),
        pk=booking_id,
        status=Booking.Status.UNVERIFIED,
    )

    last_resend = request.session.get("booking_verify_sms_resend_at")
    if last_resend and (timezone.now().timestamp() - float(last_resend)) < 60:
        messages.error(
            request,
            _("Please wait a minute before requesting another verification code."),
        )
        return redirect(reverse("booking:booking_verify_sms"))

    sent, _reason = send_verification_sms_for_booking(booking)
    request.session["booking_verify_sms_resend_at"] = timezone.now().timestamp()
    request.session["booking_verify_sms_failed"] = not sent
    if sent:
        messages.success(
            request,
            _("We sent a new verification code to your phone."),
        )
    else:
        messages.error(
            request,
            _(
                "We could not send the verification SMS right now. "
                "Please try again in a few minutes or contact the salon."
            ),
        )
    return redirect(reverse("booking:booking_verify_sms"))


def _resolve_salon_for_verify(salon_slug):
    if not salon_slug:
        return None
    return Salon.objects.filter(slug=salon_slug, is_active=True).first()


def _verify_failed_response(request, *, salon, reason, message):
    return render(
        request,
        "booking/booking_verify_failed.html",
        {
            "reason": reason,
            "message": message,
            "salon": salon,
        },
    )


def verify_booking_email(request, token, salon_slug=None):
    fallback_salon = _resolve_salon_for_verify(salon_slug)

    booking = (
        Booking.objects.filter(
            email_verification_token=token,
            status=Booking.Status.UNVERIFIED,
        )
        .select_related("salon", "customer")
        .prefetch_related("booking_services")
        .first()
    )

    if not booking:
        return _verify_failed_response(
            request,
            salon=fallback_salon,
            reason="invalid",
            message=_("This verification link is invalid or has already been used."),
        )

    salon = booking.salon

    if booking.verification_expires_at and booking.verification_expires_at < timezone.now():
        log_booking_activity(
            booking,
            BookingActivityLog.Action.VERIFICATION_EXPIRED,
            note="Verification link expired",
        )
        delete_unverified_booking(booking)
        return _verify_failed_response(
            request,
            salon=salon,
            reason="expired",
            message=_(
                "The verification link has expired. Please submit a new booking request."
            ),
        )

    success, reason = complete_email_verification(booking)
    if not success:
        if reason == "slot_unavailable":
            delete_unverified_booking(booking)
            return _verify_failed_response(
                request,
                salon=salon,
                reason="slot_unavailable",
                message=_(
                    "The selected time slot is no longer available. Please choose another time."
                ),
            )
        delete_unverified_booking(booking)
        return _verify_failed_response(
            request,
            salon=salon,
            reason=reason,
            message=_("Something went wrong. Please submit a new booking request."),
        )

    booking.refresh_from_db()
    log_booking_activity(
        booking,
        BookingActivityLog.Action.EMAIL_VERIFIED,
        note="Email verified — booking request submitted",
    )
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

    return render(
        request,
        "booking/booking_verify_success.html",
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
    salon_rules = policy.get_salon_rules_lines() if policy else []

    can_cancel, cancel_reason = can_customer_cancel_booking(booking)
    notice_hours = 24
    if policy:
        notice_hours = policy.customer_cancellation_notice_hours

    booking_service_items = list(booking.booking_services.all())
    service_schedule = build_service_schedule(
        booking.start_at, booking_service_items, booking.salon
    )

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
            "service_schedule": service_schedule,
            "total_duration": booking.total_duration_minutes,
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
        error_msg = _("This appointment cannot be cancelled.")
        if reason == "too_close":
            error_msg = _(
                "This appointment is too close for automatic cancellation. "
                "Please contact the salon."
            )
        elif reason == "past":
            error_msg = _("This appointment has already passed.")
        if request.headers.get("X-Requested-With") == "fetch":
            return JsonResponse({"ok": False, "error": error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect(reverse("booking:manage_booking", args=[token]))

    release_booking_slot(booking)
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

    if request.headers.get("X-Requested-With") == "fetch":
        return JsonResponse(
            {
                "ok": True,
                "cancelled": True,
                "status": booking.status,
                "status_display": booking.get_status_display(),
            }
        )

    return redirect(f"{reverse('booking:manage_booking', args=[token])}?cancelled=1")


@require_GET
def last_minute_dates(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)
    services = _services_from_request(request, salon)
    if not services:
        return JsonResponse({"dates": []})

    today = get_salon_local_today(salon)
    policy = getattr(salon, "booking_policy", None)
    min_notice = policy.minimum_notice_days if policy else 14
    notice_cutoff = today + timedelta(days=min_notice)
    dates = get_last_minute_open_dates_for_services(
        salon, services, today, notice_cutoff
    )
    return JsonResponse({"dates": dates})


@require_GET
def available_slots(request, salon_slug):
    salon = get_object_or_404(Salon, slug=salon_slug, is_active=True)
    date_value = request.GET.get("date")
    services = _services_from_request(request, salon)

    if not services or not date_value:
        return JsonResponse({"slots": [], "last_minute": False, "release_unavailable": False})

    try:
        selected_date = datetime.strptime(date_value, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": [], "last_minute": False, "release_unavailable": False})

    slots = get_available_slots(salon, services, selected_date)
    last_minute = not is_date_allowed(salon, selected_date) and bool(
        get_active_released_intervals(salon, selected_date)
    )
    release_unavailable = last_minute and not slots
    return _slots_json(
        slots,
        last_minute=last_minute,
        release_unavailable=release_unavailable,
    )
