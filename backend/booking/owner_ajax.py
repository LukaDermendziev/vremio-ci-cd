"""JSON payload helpers for owner dashboard Fetch requests."""

from django.utils import timezone

from .models import Booking, Customer, CustomerBlocklist, DateWorkingHoursOverride, Service, ServicePriceItem, UnavailableTimeBlock


def messages_to_list(request):
    from django.contrib import messages as django_messages

    return [(m.level_tag, str(m)) for m in django_messages.get_messages(request)]


def response_is_ok(msg_list):
    return not any(tag in ("error", "danger") for tag, _ in msg_list)


def serialize_booking_card(booking):
    local_start = timezone.localtime(booking.start_at)
    local_end = timezone.localtime(booking.end_at)
    services = list(booking.booking_services.all())
    return {
        "id": booking.id,
        "customer_id": booking.customer_id,
        "status": booking.status,
        "status_display": booking.get_status_display(),
        "full_name": booking.customer.full_name,
        "phone_number": booking.customer.phone_number,
        "instagram_username": booking.customer.instagram_username or "",
        "email": booking.customer.email or "",
        "contact": booking.customer.preferred_contact_method,
        "service_ids": [bs.service_id for bs in services],
        "date": local_start.strftime("%Y-%m-%d"),
        "start_time": local_start.strftime("%H:%M"),
        "source": booking.source,
        "owner_note": booking.owner_note or "",
        "customer_note": booking.customer_note or "",
        "has_reference_photo": bool(booking.reference_photo),
        "photo_url": (
            f"/owner/booking/{booking.id}/photo/" if booking.reference_photo else ""
        ),
        "services_label": ", ".join(bs.service_name_snapshot for bs in services),
        "end_time": local_end.strftime("%H:%M"),
        "duration": booking.total_duration_minutes,
    }


def serialize_service(service):
    items = list(service.price_items.all().order_by("sort_order", "id"))
    return {
        "id": service.id,
        "name": service.name,
        "description": service.description or "",
        "duration_minutes": service.duration_minutes,
        "base_price": str(service.base_price),
        "sort_order": service.sort_order,
        "extra_duration_note": service.extra_duration_note or "",
        "is_active": service.is_active,
        "requires_photo": service.requires_photo,
        "photo_recommended": service.photo_recommended,
        "price_items": [
            {
                "id": item.id,
                "name": item.name,
                "price_display": item.price_display,
                "group": item.group or "",
                "sort_order": item.sort_order,
                "duration_minutes": item.duration_minutes,
                "photo_required": item.photo_required,
                "is_addon": item.is_addon,
            }
            for item in items
        ],
        "price_items_count": len(items),
    }


def serialize_customer(customer):
    return {
        "id": customer.id,
        "full_name": customer.full_name,
        "phone_number": customer.phone_number,
        "instagram_username": customer.instagram_username or "",
        "email": customer.email or "",
        "contact": customer.preferred_contact_method,
        "contact_display": customer.get_preferred_contact_method_display(),
    }


def serialize_price_item(item):
    return {
        "id": item.id,
        "service_id": item.service_id,
        "name": item.name,
        "price_display": item.price_display,
        "group": item.group or "",
        "sort_order": item.sort_order,
        "duration_minutes": item.duration_minutes,
        "photo_required": item.photo_required,
        "is_addon": item.is_addon,
    }


def serialize_blocked_date(row):
    return {
        "id": row.id,
        "date": row.date.strftime("%d/%m/%Y"),
        "date_iso": row.date.isoformat(),
        "reason": row.reason or "",
    }


def serialize_unavailable_block(block):
    return {
        "id": block.id,
        "date": block.date.strftime("%d/%m/%Y"),
        "date_iso": block.date.isoformat(),
        "start_time": block.start_time.strftime("%H:%M"),
        "end_time": block.end_time.strftime("%H:%M"),
        "reason": block.reason or "",
    }


def serialize_block_entry(entry):
    from .customer_blocking import serialize_blocklist_entry

    return serialize_blocklist_entry(entry)


def build_owner_ajax_payload(salon, action, request, booking_obj=None):
    """Build action-specific payload after POST handling."""
    payload = {}
    booking_id = request.POST.get("booking_id")

    if action in (
        "save_booking",
        "approve",
        "reject",
        "mark_completed",
        "mark_no_show",
        "cancel",
        "cancel_booking",
        "delete_reference_photo",
    ):
        if booking_obj is None and booking_id:
            booking_obj = (
                Booking.objects.filter(pk=booking_id, salon=salon)
                .select_related("customer")
                .prefetch_related("booking_services")
                .first()
            )
        if booking_obj:
            payload["booking"] = serialize_booking_card(booking_obj)
        elif action == "save_booking":
            latest = (
                Booking.objects.filter(salon=salon)
                .select_related("customer")
                .prefetch_related("booking_services")
                .order_by("-id")
                .first()
            )
            if latest:
                payload["booking"] = serialize_booking_card(latest)

    elif action == "delete_booking":
        payload["deleted_booking_id"] = int(booking_id) if booking_id and booking_id.isdigit() else None

    elif action == "save_service":
        service_id = request.POST.get("service_id")
        if service_id:
            service = Service.objects.filter(pk=service_id, salon=salon).prefetch_related("price_items").first()
        else:
            service = salon.services.order_by("-id").prefetch_related("price_items").first()
        if service:
            payload["service"] = serialize_service(service)

    elif action == "delete_service":
        payload["deleted_service_id"] = request.POST.get("service_id")

    elif action == "save_price_item":
        item_id = request.POST.get("item_id")
        if item_id:
            item = ServicePriceItem.objects.filter(pk=item_id, service__salon=salon).first()
        else:
            item = ServicePriceItem.objects.filter(service__salon=salon).order_by("-id").first()
        if item:
            payload["price_item"] = serialize_price_item(item)

    elif action == "delete_price_item":
        payload["deleted_price_item_id"] = request.POST.get("item_id")

    elif action in ("save_customer",):
        customer_id = request.POST.get("customer_id")
        if customer_id:
            customer = Customer.objects.filter(pk=customer_id, salon=salon).first()
        else:
            customer = salon.customers.order_by("-id").first()
        if customer:
            payload["customer"] = serialize_customer(customer)

    elif action == "delete_customer":
        payload["deleted_customer_id"] = request.POST.get("customer_id")

    elif action in ("add_blocked_date", "save_blocked_date"):
        row = (
            salon.date_working_hours_overrides.filter(mode=DateWorkingHoursOverride.Mode.CLOSED)
            .order_by("-date")
            .first()
        )
        if row:
            payload["blocked_date"] = serialize_blocked_date(row)

    elif action == "delete_blocked_date":
        payload["deleted_blocked_date_id"] = request.POST.get("override_id")

    elif action in ("add_unavailable_block", "save_unavailable_block"):
        block_id = request.POST.get("block_id")
        if block_id:
            block = UnavailableTimeBlock.objects.filter(pk=block_id, salon=salon).first()
        else:
            block = salon.unavailable_time_blocks.order_by("-id").first()
        if block:
            payload["unavailable_block"] = serialize_unavailable_block(block)

    elif action == "delete_unavailable_block":
        payload["deleted_unavailable_block_id"] = request.POST.get("block_id")

    today_date = timezone.localdate()
    payload["stats"] = {
        "pending_count": salon.bookings.filter(status=Booking.Status.PENDING).count(),
        "today_count": salon.bookings.filter(
            status=Booking.Status.APPROVED,
            start_at__date=today_date,
        ).count(),
    }
    return payload
