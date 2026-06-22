from datetime import datetime, time, timedelta
import io

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, override

from .forms import BookingRequestForm
from .models import (
    Booking,
    BookingActivityLog,
    BookingPolicy,
    BookingService,
    Customer,
    CustomerBlocklist,
    DateWorkingHoursOverride,
    Salon,
    Service,
    ServicePriceItem,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import build_prepared_message, get_available_slots


class BookingSmokeTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)


class BookingViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="owner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=self.user,
            name="Fancy Fingers",
            slug="fancy-fingers",
        )
        Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        BookingPolicy.objects.create(salon=self.salon)

    def test_booking_page_loads_step_flow(self):
        response = self.client.get("/book/fancy-fingers/request/")

        self.assertContains(response, _("Choose service"))
        self.assertContains(response, "data-slots-url")
        self.assertContains(response, _("Review request"))
        self.assertContains(response, _("Book appointment"))

    def test_owner_dashboard_loads_for_owner(self):
        self.client.login(username="owner", password="password")

        response = self.client.get("/owner/dashboard/")

        self.assertContains(response, _("Owner panel"))
        self.assertContains(response, _("Pending booking requests"))
        self.assertContains(response, _("Booking policy"))

    def test_booking_request_requires_email(self):
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)

        service = self.salon.services.get(name="Manicure")
        response = self.client.post(
            "/book/fancy-fingers/request/",
            {
                "service": service.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "No Email",
                "phone_number": "079999888",
                "instagram_username": "no_email",
                "email": "",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "email")

    def test_salon_page_shows_updated_hero(self):
        response = self.client.get("/book/fancy-fingers/")
        self.assertContains(response, _("Care, style, and an appointment that suits you."))

    def test_booking_request_submission_creates_pending_booking(self):
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)

        service = self.salon.services.get(name="Manicure")
        response = self.client.post(
            "/book/fancy-fingers/request/",
            {
                "service": service.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "New Customer",
                "phone_number": "071111222",
                "instagram_username": "new_customer",
                "email": "customer@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(customer__phone_number="071111222")
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertEqual(booking.booking_services.first().service_name_snapshot, "Manicure")

    def test_booking_with_price_item_uses_item_name_as_snapshot(self):
        """When a ServicePriceItem is selected, its name should become service_name_snapshot."""
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)

        service = self.salon.services.get(name="Manicure")
        price_item = ServicePriceItem.objects.create(
            service=service,
            name="Classic Manicure",
            price_display="600",
            sort_order=1,
        )
        response = self.client.post(
            "/book/fancy-fingers/request/",
            {
                "service": service.id,
                "selected_price_item_id": price_item.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "Price Item Customer",
                "phone_number": "072222333",
                "instagram_username": "price_item_test",
                "email": "customer@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(customer__phone_number="072222333")
        self.assertEqual(
            booking.booking_services.first().service_name_snapshot, "Classic Manicure"
        )

    def test_available_slots_api_returns_json(self):
        """The available_slots endpoint must return JSON with a slots list."""
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)

        service = self.salon.services.get(name="Manicure")
        response = self.client.get(
            f"/book/fancy-fingers/slots/",
            {"service": service.id, "date": selected_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("slots", data)


class AvailabilityTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="owner",
            password="password",
        )
        self.salon = Salon.objects.create(owner=user, name="Nail Studio", slug="nail-studio")
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            maximum_booking_window_days=60,
            allow_same_day_booking=True,
            allow_next_day_booking=True,
            pending_holds_slot=True,
            slot_interval_minutes=30,
            buffer_minutes_between_bookings=0,
        )
        self.selected_date = timezone.localdate() + timedelta(days=7)
        self.now = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(7, 0)),
            timezone.get_current_timezone(),
        )
        WorkingHours.objects.create(
            salon=self.salon,
            weekday=self.selected_date.weekday(),
            is_working_day=True,
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        self.customer = Customer.objects.create(
            salon=self.salon,
            full_name="Test Customer",
            phone_number="070123456",
            instagram_username="test_customer",
        )

    def test_closed_day_returns_no_slots(self):
        sunday = self._next_sunday()
        # setUp may create a Sunday row when selected_date (+7 days) falls on Sunday
        WorkingHours.objects.filter(
            salon=self.salon, weekday=WorkingHours.Weekday.SUNDAY
        ).delete()

        slots = get_available_slots(
            self.salon,
            self.service,
            sunday,
            now=self.now,
        )

        self.assertEqual(slots, [])

    def test_date_working_hours_override_closed_returns_no_slots(self):
        DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=self.selected_date,
            mode=DateWorkingHoursOverride.Mode.CLOSED,
        )

        self.assertEqual(self._slot_values(), set())

    def test_custom_working_hours_are_respected(self):
        DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=self.selected_date,
            mode=DateWorkingHoursOverride.Mode.CUSTOM_HOURS,
            custom_start_time=time(10, 0),
            custom_end_time=time(15, 0),
        )

        values = self._slot_values()

        self.assertIn("10:00", values)
        self.assertIn("13:00", values)
        self.assertNotIn("09:30", values)
        self.assertNotIn("13:30", values)

    def test_unavailable_time_block_removes_overlapping_slots(self):
        UnavailableTimeBlock.objects.create(
            salon=self.salon,
            date=self.selected_date,
            start_time=time(12, 0),
            end_time=time(14, 45),
        )

        values = self._slot_values()

        self.assertIn("10:00", values)
        self.assertNotIn("10:30", values)
        self.assertNotIn("14:30", values)
        self.assertIn("15:00", values)

    def test_approved_booking_blocks_overlapping_slots(self):
        self._create_booking(Booking.Status.APPROVED, 12, 0, 14, 0)

        values = self._slot_values()

        self.assertIn("10:00", values)
        self.assertNotIn("10:30", values)
        self.assertNotIn("12:00", values)
        self.assertIn("14:00", values)

    def test_pending_booking_blocks_slots_when_policy_enabled(self):
        self._create_booking(Booking.Status.PENDING, 10, 0, 12, 0)

        values = self._slot_values()

        self.assertIn("08:00", values)
        self.assertNotIn("08:30", values)
        self.assertNotIn("10:00", values)
        self.assertIn("12:00", values)

    def test_pending_booking_does_not_block_slots_when_policy_disabled(self):
        policy = self.salon.booking_policy
        policy.pending_holds_slot = False
        policy.save()
        self._create_booking(Booking.Status.PENDING, 10, 0, 12, 0)

        values = self._slot_values()

        self.assertIn("10:00", values)

    def test_service_duration_affects_available_slots(self):
        self.service.duration_minutes = 180
        self.service.save()
        DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=self.selected_date,
            mode=DateWorkingHoursOverride.Mode.CUSTOM_HOURS,
            custom_start_time=time(8, 0),
            custom_end_time=time(12, 0),
        )

        values = self._slot_values()

        self.assertEqual(values, {"08:00", "08:30", "09:00"})

    def test_slot_interval_controls_start_times(self):
        policy = self.salon.booking_policy
        policy.slot_interval_minutes = 45
        policy.save()
        self.service.duration_minutes = 30
        self.service.save()
        DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=self.selected_date,
            mode=DateWorkingHoursOverride.Mode.CUSTOM_HOURS,
            custom_start_time=time(8, 0),
            custom_end_time=time(10, 0),
        )

        values = self._slot_values()

        self.assertEqual(values, {"08:00", "08:45", "09:30"})

    def test_buffer_time_between_bookings_is_respected(self):
        policy = self.salon.booking_policy
        policy.buffer_minutes_between_bookings = 15
        policy.save()
        self._create_booking(Booking.Status.APPROVED, 12, 0, 14, 0)

        values = self._slot_values()

        self.assertIn("09:30", values)
        self.assertNotIn("10:00", values)
        self.assertNotIn("14:00", values)
        self.assertIn("14:30", values)

    def test_minimum_booking_notice_is_respected(self):
        policy = self.salon.booking_policy
        policy.minimum_notice_days = 14
        policy.save()
        too_soon = self._next_non_sunday(timezone.localdate() + timedelta(days=1))

        slots = get_available_slots(
            self.salon,
            self.service,
            too_soon,
            now=self.now,
        )

        self.assertEqual(slots, [])

    def test_maximum_booking_window_is_respected(self):
        policy = self.salon.booking_policy
        policy.maximum_booking_window_days = 10
        policy.save()
        too_far = self._next_non_sunday(timezone.localdate() + timedelta(days=11))

        slots = get_available_slots(
            self.salon,
            self.service,
            too_far,
            now=self.now,
        )

        self.assertEqual(slots, [])

    def test_edited_longer_booking_blocks_later_possible_slots_correctly(self):
        self._create_booking(Booking.Status.APPROVED, 12, 0, 14, 45)

        values = self._slot_values()

        self.assertEqual(
            values,
            {
                "08:00",
                "08:30",
                "09:00",
                "09:30",
                "10:00",
                "15:00",
                "15:30",
                "16:00",
            },
        )

    def test_legacy_calculate_available_slots_alias_still_works(self):
        from .services import calculate_available_slots

        slots = calculate_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self.now,
        )

        self.assertTrue(slots)

    def _slot_values(self):
        slots = get_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self.now,
        )
        return {slot["value"] for slot in slots}

    def _create_booking(self, status, start_hour, start_minute, end_hour, end_minute):
        Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=status,
            source=Booking.Source.OWNER_MANUAL,
            start_at=self._aware_at(start_hour, start_minute),
            end_at=self._aware_at(end_hour, end_minute),
            total_duration_minutes=(
                (end_hour * 60 + end_minute) - (start_hour * 60 + start_minute)
            ),
        )

    def _aware_at(self, hour, minute, selected_date=None):
        if selected_date is None:
            selected_date = self.selected_date

        return timezone.make_aware(
            datetime.combine(selected_date, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def _next_sunday(self):
        selected_date = timezone.localdate()
        while selected_date.weekday() != WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        return selected_date

    def _next_non_sunday(self, selected_date):
        while selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        return selected_date


class BetaReadinessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_a = User.objects.create_user(
            username="owner_a", email="owner_a@example.com", password="pass"
        )
        self.owner_b = User.objects.create_user(
            username="owner_b", email="owner_b@example.com", password="pass"
        )
        self.salon_a = Salon.objects.create(
            owner=self.owner_a, name="Salon A", slug="salon-a"
        )
        self.salon_b = Salon.objects.create(
            owner=self.owner_b, name="Salon B", slug="salon-b"
        )
        BookingPolicy.objects.create(salon=self.salon_a, minimum_notice_days=0)
        BookingPolicy.objects.create(salon=self.salon_b, minimum_notice_days=0)
        self.service_a = Service.objects.create(
            salon=self.salon_a, name="Manicure", duration_minutes=120, base_price=600
        )
        WorkingHours.objects.create(
            salon=self.salon_a,
            weekday=0,
            is_working_day=True,
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        self.customer_a = Customer.objects.create(
            salon=self.salon_a,
            full_name="Customer A",
            phone_number="070111222",
            instagram_username="cust_a",
        )
        selected = timezone.localdate() + timedelta(days=1)
        if selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        self.booking_a = Booking.objects.create(
            salon=self.salon_a,
            customer=self.customer_a,
            status=Booking.Status.PENDING,
            source=Booking.Source.ONLINE,
            start_at=timezone.make_aware(
                datetime.combine(selected, time(10, 0)),
                timezone.get_current_timezone(),
            ),
            end_at=timezone.make_aware(
                datetime.combine(selected, time(12, 0)),
                timezone.get_current_timezone(),
            ),
            total_duration_minutes=120,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=self.booking_a,
            service=self.service_a,
            service_name_snapshot="Manicure",
        )

    def test_owner_dashboard_requires_login(self):
        response = self.client.get("/owner/dashboard/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/owner/login/", response.url)

    def test_owner_cannot_access_other_salon_booking_detail(self):
        self.client.login(username="owner_b", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_detail", args=[self.booking_a.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_own_booking_photo(self):
        photo = SimpleUploadedFile(
            "nail.jpg", b"\xff\xd8\xff\xd8fake-jpeg", content_type="image/jpeg"
        )
        self.booking_a.reference_photo = photo
        self.booking_a.save()
        self.client.login(username="owner_a", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_photo", args=[self.booking_a.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response["Content-Type"])

    def test_owner_cannot_view_other_salon_booking_photo(self):
        photo = SimpleUploadedFile(
            "nail.jpg", b"\xff\xd8\xff\xd8fake-jpeg", content_type="image/jpeg"
        )
        self.booking_a.reference_photo = photo
        self.booking_a.save()
        self.client.login(username="owner_b", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_photo", args=[self.booking_a.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_booking_detail_returns_protected_photo_url(self):
        photo = SimpleUploadedFile(
            "nail.jpg", b"\xff\xd8\xff\xd8fake-jpeg", content_type="image/jpeg"
        )
        self.booking_a.reference_photo = photo
        self.booking_a.save()
        self.client.login(username="owner_a", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_detail", args=[self.booking_a.pk])
        )
        data = response.json()
        self.assertTrue(data["has_reference_photo"])
        self.assertIn("/owner/booking/", data["reference_photo_url"])
        self.assertNotIn("/media/", data["reference_photo_url"])

    def test_owner_cannot_approve_other_salon_booking(self):
        self.client.login(username="owner_b", password="pass")
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "approve",
                "booking_id": self.booking_a.pk,
            },
        )
        self.assertEqual(response.status_code, 404)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.PENDING)

    def test_password_reset_urls_resolve(self):
        url = reverse("booking:owner_password_reset")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_photo_upload_rejects_oversized_file(self):
        big = SimpleUploadedFile(
            "big.jpg",
            b"x" * (5 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        WorkingHours.objects.create(
            salon=self.salon_a,
            weekday=selected_date.weekday(),
            is_working_day=True,
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        form = BookingRequestForm(
            {
                "service": self.service_a.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "Test",
                "phone_number": "070999888",
                "instagram_username": "test",
                "email": "test@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": True,
            },
            {"reference_photo": big},
            salon=self.salon_a,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("reference_photo", form.errors)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_new_booking_sends_customer_request_email(self):
        from django.core import mail

        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        WorkingHours.objects.create(
            salon=self.salon_a,
            weekday=selected_date.weekday(),
            is_working_day=True,
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        response = self.client.post(
            "/book/salon-a/request/",
            {
                "service": self.service_a.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "Email Test",
                "phone_number": "071234569",
                "instagram_username": "email_test2",
                "email": "request@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertGreaterEqual(len(mail.outbox), 1)
        customer_messages = [m for m in mail.outbox if "request@example.com" in m.to]
        self.assertEqual(len(customer_messages), 1)
        self.assertIn(_("We received your booking request"), customer_messages[0].subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_new_booking_sends_owner_email_when_configured(self):
        from django.core import mail

        self.owner_a.email = "owner_notify@example.com"
        self.owner_a.save()
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        WorkingHours.objects.create(
            salon=self.salon_a,
            weekday=selected_date.weekday(),
            is_working_day=True,
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        response = self.client.post(
            "/book/salon-a/request/",
            {
                "service": self.service_a.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "Email Test",
                "phone_number": "071234567",
                "instagram_username": "email_test",
                "email": "customer@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertGreaterEqual(len(mail.outbox), 1)
        owner_messages = [m for m in mail.outbox if "owner_notify@example.com" in m.to]
        self.assertEqual(len(owner_messages), 1)
        self.assertIn(_("New booking request"), owner_messages[0].subject)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        OWNER_NOTIFICATION_EMAIL="override_owner@example.com",
    )
    def test_owner_notification_prefers_env_email(self):
        from django.core import mail

        self.owner_a.email = "owner_a@example.com"
        self.owner_a.save()
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        WorkingHours.objects.create(
            salon=self.salon_a,
            weekday=selected_date.weekday(),
            is_working_day=True,
            start_time=time(8, 0),
            end_time=time(18, 0),
        )
        response = self.client.post(
            "/book/salon-a/request/",
            {
                "service": self.service_a.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "Override Test",
                "phone_number": "071234568",
                "instagram_username": "override_test",
                "email": "customer@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        owner_messages = [m for m in mail.outbox if "override_owner@example.com" in m.to]
        self.assertEqual(len(owner_messages), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_approve_sends_customer_email_when_email_exists(self):
        from django.core import mail

        self.customer_a.email = "customer@example.com"
        self.customer_a.save()
        self.client.login(username="owner_a", password="pass")
        response = self.client.post(
            "/owner/dashboard/",
            {"action": "approve", "booking_id": self.booking_a.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.APPROVED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("customer@example.com", mail.outbox[0].to)
        self.assertIn(_("Your appointment is confirmed"), mail.outbox[0].subject)
        self.assertTrue(mail.outbox[0].reply_to)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reject_sends_customer_email_when_email_exists(self):
        from django.core import mail

        self.customer_a.email = "customer@example.com"
        self.customer_a.save()
        self.client.login(username="owner_a", password="pass")
        response = self.client.post(
            "/owner/dashboard/",
            {"action": "reject", "booking_id": self.booking_a.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.REJECTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("customer@example.com", mail.outbox[0].to)
        self.assertIn(_("Your appointment request was declined"), mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_approve_without_customer_email_still_succeeds(self):
        from django.core import mail

        self.client.login(username="owner_a", password="pass")
        response = self.client.post(
            "/owner/dashboard/",
            {"action": "approve", "booking_id": self.booking_a.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.APPROVED)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_approve_email_failure_does_not_undo_approval(self):
        from unittest.mock import patch

        self.customer_a.email = "customer@example.com"
        self.customer_a.save()
        self.client.login(username="owner_a", password="pass")
        with patch("booking.email_utils._send_email", return_value=(False, "error")):
            response = self.client.post(
                "/owner/dashboard/",
                {"action": "approve", "booking_id": self.booking_a.pk},
            )
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.APPROVED)

    def test_manage_booking_page_requires_token(self):
        response = self.client.get(
            reverse("booking:manage_booking", args=["00000000-0000-0000-0000-000000000000"])
        )
        self.assertEqual(response.status_code, 404)

    def test_manage_booking_page_shows_booking(self):
        response = self.client.get(
            reverse("booking:manage_booking", args=[self.booking_a.manage_token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.customer_a.full_name)
        self.assertContains(response, _("Your appointment"))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_customer_can_cancel_pending_booking(self):
        from django.core import mail

        self.customer_a.email = "customer@example.com"
        self.customer_a.save()
        url = reverse("booking:manage_booking_cancel", args=[self.booking_a.manage_token])
        response = self.client.post(url, {"confirm": "yes"})
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.CANCELLED)
        self.assertTrue(self.booking_a.cancelled_by_customer)
        self.assertTrue(
            BookingActivityLog.objects.filter(
                booking=self.booking_a,
                action=BookingActivityLog.Action.CUSTOMER_CANCELLED,
            ).exists()
        )
        self.assertGreaterEqual(len(mail.outbox), 1)

    def test_customer_cannot_cancel_approved_booking_too_close(self):
        self.booking_a.status = Booking.Status.APPROVED
        self.booking_a.start_at = timezone.now() + timedelta(hours=6)
        self.booking_a.end_at = self.booking_a.start_at + timedelta(hours=2)
        self.booking_a.save()
        self.salon_a.booking_policy.customer_cancellation_notice_hours = 24
        self.salon_a.booking_policy.save()

        url = reverse("booking:manage_booking_cancel", args=[self.booking_a.manage_token])
        response = self.client.post(url, {"confirm": "yes"})
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.APPROVED)

    def test_cancelled_booking_does_not_block_availability(self):
        selected_date = timezone.localdate() + timedelta(days=2)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        WorkingHours.objects.get_or_create(
            salon=self.salon_a,
            weekday=selected_date.weekday(),
            defaults={
                "is_working_day": True,
                "start_time": time(8, 0),
                "end_time": time(18, 0),
            },
        )
        self.booking_a.status = Booking.Status.CANCELLED
        self.booking_a.start_at = timezone.make_aware(
            datetime.combine(selected_date, time(10, 0)),
            timezone.get_current_timezone(),
        )
        self.booking_a.end_at = self.booking_a.start_at + timedelta(hours=2)
        self.booking_a.save()

        slots = get_available_slots(self.salon_a, self.service_a, selected_date)
        slot_values = [slot["value"] for slot in slots]
        self.assertIn("10:00", slot_values)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_test_email_command(self):
        from django.core import mail
        from io import StringIO

        out = StringIO()
        call_command("test_email", "cli-test@example.com", stdout=out)
        self.assertIn("cli-test@example.com", out.getvalue())
        self.assertEqual(len(mail.outbox), 1)

    def test_sqlite_used_when_no_postgres_env(self):
        engine = connection.settings_dict["ENGINE"]
        self.assertIn("sqlite", engine)

    def test_setup_beta_salon_command_creates_data(self):
        call_command(
            "setup_beta_salon",
            username="beta_owner",
            email="beta@example.com",
            slug="beta-nails",
            salon_name="Beta Nails",
        )
        User = get_user_model()
        user = User.objects.get(username="beta_owner")
        salon = Salon.objects.get(slug="beta-nails")
        self.assertEqual(salon.owner, user)
        self.assertTrue(hasattr(salon, "booking_policy"))
        self.assertEqual(salon.services.filter(is_active=True).count(), 4)
        self.assertFalse(
            salon.working_hours.get(weekday=WorkingHours.Weekday.SUNDAY).is_working_day
        )


class AntiAbuseTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Salon A", slug="salon-a")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            max_pending_bookings_per_customer=1,
            max_active_future_bookings_per_customer=2,
            booking_rate_limit_per_ip_per_hour=5,
            booking_rate_limit_per_email_per_day=3,
            booking_rate_limit_per_phone_per_day=3,
            max_reference_photo_size_mb=5,
        )
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=600,
        )
        for weekday in range(6):
            WorkingHours.objects.create(
                salon=self.salon,
                weekday=weekday,
                is_working_day=True,
                start_time=time(8, 0),
                end_time=time(18, 0),
            )

    def _future_date(self, days=20):
        selected = timezone.localdate() + timedelta(days=days)
        while selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        return selected

    def _post_data(self, phone, email, date=None, start_time="08:00", **extra):
        return {
            "service": self.service.id,
            "date": (date or self._future_date()).isoformat(),
            "start_time": start_time,
            "full_name": "Test Customer",
            "phone_number": phone,
            "instagram_username": "test_user",
            "email": email,
            "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
            "rules_accepted": "on",
            **extra,
        }

    def _create_booking(self, phone, email, status=Booking.Status.PENDING, start_time=(10, 0)):
        customer, _created = Customer.objects.get_or_create(
            salon=self.salon,
            phone_number=phone,
            defaults={
                "full_name": "Existing",
                "instagram_username": "existing",
                "email": email,
            },
        )
        selected = self._future_date()
        start = timezone.make_aware(
            datetime.combine(selected, time(*start_time)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=status,
            source=Booking.Source.ONLINE,
            start_at=start,
            end_at=start + timedelta(hours=2),
            total_duration_minutes=120,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.service,
            service_name_snapshot="Manicure",
        )
        return booking

    def test_second_pending_blocked_for_same_phone(self):
        self._create_booking("070111222", "first@example.com")
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111222", "other@example.com", start_time="12:00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "барање за термин")

    def test_second_pending_blocked_for_same_email(self):
        self._create_booking("070111222", "shared@example.com")
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070999888", "shared@example.com", start_time="12:00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "барање за термин")

    def test_customer_can_book_after_cancelled(self):
        booking = self._create_booking("070111222", "retry@example.com")
        booking.status = Booking.Status.CANCELLED
        booking.save()
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111222", "retry@example.com", start_time="12:00"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Booking.objects.filter(
                customer__phone_number="070111222",
                status=Booking.Status.PENDING,
            ).count(),
            1,
        )

    def test_active_future_limit_blocks_third_booking(self):
        self._create_booking("070111222", "active@example.com", status=Booking.Status.APPROVED)
        self._create_booking(
            "070111222",
            "active@example.com",
            status=Booking.Status.APPROVED,
            start_time=(14, 0),
        )
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111222", "active@example.com", start_time="16:00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "максималниот број активни")

    def test_blocklisted_customer_cannot_submit(self):
        CustomerBlocklist.objects.create(
            salon=self.salon,
            phone_number="070555444",
            is_active=True,
        )
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070555444", "blocked@example.com"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "не може да биде испратено")

    def test_rate_limit_blocks_repeated_submissions(self):
        self.policy.booking_rate_limit_per_ip_per_hour = 1
        self.policy.save()
        first = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111001", "one@example.com"),
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111002", "two@example.com", start_time="12:00"),
        )
        self.assertEqual(second.status_code, 200)
        self.assertContains(second, "премногу барања")

    def test_owner_manual_booking_not_blocked_with_warning(self):
        self._create_booking("070111222", "owner@example.com")
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Manual Customer",
                "phone_number": "070111222",
                "instagram_username": "manual",
                "email": "owner@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "service": self.service.id,
                "date": selected.isoformat(),
                "start_time": "14:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "активен")


def _make_test_image(fmt="JPEG", name="test.jpg"):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), color="red").save(buffer, format=fmt)
    content_types = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
    }
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_types[fmt])


class PhotoValidationTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Salon A", slug="salon-a")
        BookingPolicy.objects.create(salon=self.salon, minimum_notice_days=0, max_reference_photo_size_mb=5)
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=600,
        )

    def _future_date(self):
        selected = timezone.localdate() + timedelta(days=20)
        while selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        return selected

    def _form(self, files=None, **extra):
        data = {
            "service": self.service.id,
            "date": self._future_date().isoformat(),
            "start_time": "08:00",
            "full_name": "Photo Test",
            "phone_number": "070888777",
            "instagram_username": "photo_test",
            "email": "photo@example.com",
            "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
            "rules_accepted": True,
            **extra,
        }
        return BookingRequestForm(data, files or {}, salon=self.salon)

    def test_oversized_image_rejected(self):
        big = SimpleUploadedFile("big.jpg", b"x" * (5 * 1024 * 1024 + 1), content_type="image/jpeg")
        form = self._form(files={"reference_photo": big})
        self.assertFalse(form.is_valid())
        self.assertIn("reference_photo", form.errors)

    def test_renamed_fake_image_rejected(self):
        fake = SimpleUploadedFile("fake.jpg", b"not-an-image", content_type="image/jpeg")
        form = self._form(files={"reference_photo": fake})
        self.assertFalse(form.is_valid())
        self.assertIn("reference_photo", form.errors)

    def test_valid_jpg_png_webp_accepted(self):
        for index, (fmt, name) in enumerate([("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp")]):
            with self.subTest(fmt=fmt):
                cache.clear()
                form = self._form(
                    files={"reference_photo": _make_test_image(fmt, name)},
                    phone_number=f"07088877{index}",
                    email=f"photo{index}@example.com",
                )
                self.assertTrue(form.is_valid(), form.errors)


class SalonRulesLanguageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Salon A", slug="salon-a")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            salon_rules="MK rule one\nMK rule two",
            salon_rules_en="EN rule one\nEN rule two",
        )

    def test_macedonian_rules_for_mk_language(self):
        with override("mk"):
            self.assertEqual(
                self.policy.get_salon_rules_lines(),
                ["MK rule one", "MK rule two"],
            )

    def test_english_rules_for_en_language(self):
        with override("en"):
            self.assertEqual(
                self.policy.get_salon_rules_lines(),
                ["EN rule one", "EN rule two"],
            )

    def test_english_falls_back_to_macedonian_when_empty(self):
        self.policy.salon_rules_en = ""
        self.policy.save(update_fields=["salon_rules_en"])
        with override("en"):
            self.assertEqual(
                self.policy.get_salon_rules_lines(),
                ["MK rule one", "MK rule two"],
            )


class PreparedMessageDateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Salon A", slug="salon-a")
        BookingPolicy.objects.create(
            salon=self.salon,
            msg_approved="Здраво {ime}, вашиот термин за {datum} во {vreme} е потврден. — {salon}",
        )
        self.customer = Customer.objects.create(
            salon=self.salon,
            full_name="Maria Test",
            phone_number="070111222",
        )
        july_ninth = timezone.make_aware(
            datetime(2026, 7, 9, 10, 0),
            timezone.get_current_timezone(),
        )
        self.booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=july_ninth,
            end_at=july_ninth + timedelta(hours=2),
            total_duration_minutes=120,
            rules_accepted=True,
        )

    def test_macedonian_month_name_in_prepared_message(self):
        with override("mk"):
            message = build_prepared_message(self.booking, "approved")
        self.assertIn("Јули", message)
        self.assertNotIn("July", message)
        self.assertIn("9", message)

    def test_english_month_name_in_prepared_message(self):
        with override("en"):
            message = build_prepared_message(self.booking, "approved")
        self.assertIn("July", message)
        self.assertNotIn("Јули", message)
