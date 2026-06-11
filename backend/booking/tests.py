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
    WorkingHours,
)
from .services import calculate_available_slots


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
        response = self.client.get("/book/fancy-fingers/")

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
            "/book/fancy-fingers/",
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

    def test_recalculates_slots_after_longer_booking(self):
        Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=self._aware_at(12, 0),
            end_at=self._aware_at(14, 45),
            total_duration_minutes=165,
        )

        slots = calculate_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self._aware_at(7, 0),
        )
        values = {slot["value"] for slot in slots}

        self.assertNotIn("14:30", values)
        self.assertIn("15:00", values)
        self.assertIn("15:30", values)
        self.assertIn("16:00", values)

    def test_pending_booking_holds_slot_when_policy_enabled(self):
        Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.PENDING,
            source=Booking.Source.OWNER_MANUAL,
            start_at=self._aware_at(10, 0),
            end_at=self._aware_at(12, 0),
            total_duration_minutes=120,
        )

        slots = calculate_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self._aware_at(7, 0),
        )
        values = {slot["value"] for slot in slots}

        self.assertNotIn("10:00", values)

    def test_closed_date_override_has_no_slots(self):
        DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=self.selected_date,
            mode=DateWorkingHoursOverride.Mode.CLOSED,
        )

        slots = calculate_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self._aware_at(7, 0),
        )

        self.assertEqual(slots, [])

    def _aware_at(self, hour, minute):
        return timezone.make_aware(
            datetime.combine(self.selected_date, time(hour, minute)),
            timezone.get_current_timezone(),
        )
