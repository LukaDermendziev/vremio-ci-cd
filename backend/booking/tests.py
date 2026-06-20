from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import (
    Booking,
    BookingPolicy,
    Customer,
    DateWorkingHoursOverride,
    Salon,
    Service,
    ServicePriceItem,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import get_available_slots


class BookingSmokeTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)


class BookingViewTests(TestCase):
    def setUp(self):
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

        self.assertContains(response, "Choose service")
        self.assertContains(response, "data-slots-url")
        self.assertContains(response, "Review request")

    def test_owner_dashboard_loads_for_owner(self):
        self.client.login(username="owner", password="password")

        response = self.client.get("/owner/dashboard/")

        self.assertContains(response, "Owner panel")
        self.assertContains(response, "Pending booking requests")
        self.assertContains(response, "Booking policy")

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
                "email": "",
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
                "email": "",
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
