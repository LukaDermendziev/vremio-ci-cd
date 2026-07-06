from datetime import datetime, time, timedelta
import io

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, override

from .forms import BookingPolicyForm, BookingRequestForm
from .models import (
    Booking,
    BookingActivityLog,
    BookingPolicy,
    BookingService,
    Customer,
    CustomerBlocklist,
    CustomerBlockEvent,
    DateWorkingHoursOverride,
    ReleasedSlot,
    Salon,
    Service,
    ServicePriceItem,
    UnavailableTimeBlock,
    WorkingHours,
)
from .services import (
    auto_complete_past_bookings,
    booking_visible_on_calendar,
    build_contact_links,
    build_prepared_message,
    build_service_schedule,
    calculate_combined_duration_minutes,
    find_conflicting_booking,
    format_services_for_email,
    get_available_slots,
    get_calendar_history_cutoff_date,
    get_calendar_history_days,
    get_last_minute_open_dates,
    get_last_minute_open_dates_for_services,
    get_salon_local_today,
    is_slot_available,
    release_booking_slot,
    release_interval,
    consume_released_slot,
    ensure_default_working_hours,
)


class BookingSmokeTests(TestCase):
    def test_home_page_loads(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)

    def test_first_visit_uses_macedonian_despite_english_browser(self):
        response = self.client.get(
            "/",
            HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9",
        )
        self.assertContains(response, 'lang="mk"')

    def test_explicit_english_cookie_is_respected(self):
        self.client.cookies["django_language"] = "en"
        response = self.client.get(
            "/",
            HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9",
        )
        self.assertContains(response, 'lang="en"')


class HomePageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="homeowner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=self.user,
            name="Fancy Fingers",
            slug="fancy-fingers",
            city="Скопје",
            short_description="Nail salon",
            business_category=Salon.BusinessCategory.SALON,
            is_active=True,
        )
        Salon.objects.create(
            owner=self.user,
            name="City Barbers",
            slug="city-barbers",
            business_category=Salon.BusinessCategory.BARBER,
            is_active=True,
        )

    def test_home_shows_vremio_branding(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vremio")
        self.assertNotContains(response, "Salon Scheduler")

    def test_home_lists_active_business(self):
        response = self.client.get("/")
        self.assertContains(response, "Fancy Fingers")
        self.assertContains(response, reverse("booking:salon_page", args=["fancy-fingers"]))

    def test_home_search_by_name(self):
        response = self.client.get("/?q=fancy")
        self.assertContains(response, 'id="vm-search-q"')
        self.assertContains(response, 'value="fancy"')
        self.assertContains(response, "Fancy Fingers")
        self.assertContains(response, "City Barbers")
        self.assertContains(response, 'data-search="fancy fingers')

    def test_home_category_filter(self):
        response = self.client.get("/?category=barber")
        self.assertContains(response, 'data-category="barber"')
        self.assertContains(response, "Fancy Fingers")
        self.assertContains(response, "City Barbers")
        self.assertContains(response, 'data-category="salon"')

    def test_home_empty_search_message(self):
        response = self.client.get("/?q=nonexistent-xyz")
        self.assertContains(response, 'id="vm-business-empty"')
        self.assertContains(response, _("We couldn't find a business matching your search."))

    @override_settings(VREMIO_CONTACT_EMAIL="hello@vremio.test")
    def test_home_contact_email_from_settings(self):
        response = self.client.get("/")
        self.assertContains(response, "hello@vremio.test")


class CustomerDomainTests(TestCase):
    @override_settings(
        ALLOWED_HOSTS=["www.fancyfingers.mk", "fancyfingers.mk", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk", "fancyfingers.mk"],
        CUSTOMER_DOMAIN_SALON_SLUG="fancy-fingers",
    )
    def test_customer_domain_root_redirects_to_salon_page(self):
        response = self.client.get("/", HTTP_HOST="www.fancyfingers.mk")
        self.assertRedirects(
            response,
            "/book/fancy-fingers/",
            fetch_redirect_response=False,
        )

    @override_settings(
        ALLOWED_HOSTS=["vremio-production.up.railway.app", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk"],
        CUSTOMER_DOMAIN_SALON_SLUG="fancy-fingers",
    )
    def test_railway_domain_still_shows_vremio_home(self):
        response = self.client.get("/", HTTP_HOST="vremio-production.up.railway.app")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vremio")


class HealthCheckTests(TestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "ok")


class LegalComplianceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="legalowner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=self.user,
            name="Legal Test Salon",
            slug="legal-test",
        )
        Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)

    def test_privacy_page_loads(self):
        self.assertEqual(self.client.get("/privacy/").status_code, 200)

    def test_terms_page_loads(self):
        self.assertEqual(self.client.get("/terms/").status_code, 200)

    def test_booking_rules_page_loads(self):
        self.assertEqual(self.client.get("/booking-rules/").status_code, 200)

    def test_photo_policy_page_loads(self):
        response = self.client.get("/photo-policy/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Дозволено е")

    def test_privacy_page_has_mk_intro(self):
        response = self.client.get("/privacy/")
        self.assertContains(response, "Добредојдовте на Vremio")

    def test_terms_page_has_mk_acceptance(self):
        response = self.client.get("/terms/")
        self.assertContains(response, "1. Прифаќање")

    def test_booking_rules_page_has_mk_rules(self):
        response = self.client.get("/booking-rules/")
        self.assertContains(response, "автоматски потврден термин")

    def test_salon_page_footer_has_no_owner_login(self):
        response = self.client.get("/book/legal-test/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse("booking:owner_login"))

    def test_contact_page_loads(self):
        self.assertEqual(self.client.get("/contact/").status_code, 200)

    def test_pilot_terms_page_loads(self):
        self.assertEqual(self.client.get("/owner/pilot-terms/").status_code, 200)

    def test_home_footer_has_legal_links(self):
        response = self.client.get("/")
        self.assertContains(response, reverse("booking:privacy_policy"))
        self.assertContains(response, reverse("booking:terms_of_use"))

    def test_booking_form_shows_legal_links(self):
        response = self.client.get("/book/legal-test/request/")
        self.assertContains(response, reverse("booking:privacy_policy"))
        self.assertContains(response, reverse("booking:booking_rules"))
        self.assertContains(response, reverse("booking:photo_policy"))

    def test_booking_requires_rules_accepted(self):
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        service = self.salon.services.get(name="Manicure")
        response = self.client.post(
            "/book/legal-test/request/",
            {
                "service": service.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "No Rules",
                "phone_number": "071000111",
                "instagram_username": "norules",
                "email": "norules@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.filter(customer__phone_number="071000111").exists())

    def test_booking_succeeds_with_rules_accepted(self):
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        service = self.salon.services.get(name="Manicure")
        response = self.client.post(
            "/book/legal-test/request/",
            {
                "service": service.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "With Rules",
                "phone_number": "071000222",
                "instagram_username": "withrules",
                "email": "withrules@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Booking.objects.filter(customer__phone_number="071000222").exists())


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
        BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)

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
            email_verification_required=False,
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

    def test_model_conflict_detection_respects_buffer(self):
        policy = self.salon.booking_policy
        policy.buffer_minutes_between_bookings = 15
        policy.save()
        self._create_booking(Booking.Status.APPROVED, 12, 0, 14, 0)

        candidate = Booking(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.PENDING,
            source=Booking.Source.ONLINE,
            start_at=self._aware_at(10, 0),
            end_at=self._aware_at(12, 0),
            total_duration_minutes=120,
            rules_accepted=True,
        )
        self.assertIsNotNone(find_conflicting_booking(
            self.salon,
            candidate.start_at,
            candidate.end_at,
            booking_status=candidate.status,
        ))
        with self.assertRaises(ValidationError):
            candidate.full_clean()

    def test_max_appointments_per_day_returns_no_slots(self):
        policy = self.salon.booking_policy
        policy.max_appointments_per_day = 2
        policy.save()
        self._create_booking(Booking.Status.APPROVED, 8, 0, 10, 0)
        self._create_booking(Booking.Status.APPROVED, 14, 0, 16, 0)

        values = self._slot_values()

        self.assertEqual(values, set())

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


class FixedStartTimesTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="fixed_owner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=user,
            name="Fixed Salon",
            slug="fixed-salon",
        )
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            maximum_booking_window_days=60,
            allow_same_day_booking=True,
            allow_next_day_booking=True,
            pending_holds_slot=True,
            slot_interval_minutes=30,
            use_fixed_start_times=True,
            fixed_start_times=["08:00", "10:30", "13:00", "15:30"],
            email_verification_required=False,
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
            full_name="Fixed Customer",
            phone_number="070555444",
            instagram_username="fixed_customer",
        )

    def _slot_values(self):
        slots = get_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self.now,
        )
        return {slot["value"] for slot in slots}

    def test_fixed_start_times_return_only_configured_starts(self):
        values = self._slot_values()
        self.assertEqual(values, {"08:00", "10:30", "13:00", "15:30"})
        self.assertNotIn("08:30", values)
        self.assertNotIn("09:00", values)

    def test_fixed_start_times_respect_busy_intervals(self):
        Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=timezone.make_aware(
                datetime.combine(self.selected_date, time(8, 0)),
                timezone.get_current_timezone(),
            ),
            end_at=timezone.make_aware(
                datetime.combine(self.selected_date, time(10, 0)),
                timezone.get_current_timezone(),
            ),
            total_duration_minutes=120,
        )

        values = self._slot_values()
        self.assertNotIn("08:00", values)
        self.assertIn("10:30", values)
        self.assertIn("13:00", values)

    def test_fixed_start_times_outside_custom_hours_are_skipped(self):
        DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=self.selected_date,
            mode=DateWorkingHoursOverride.Mode.CUSTOM_HOURS,
            custom_start_time=time(10, 0),
            custom_end_time=time(16, 0),
        )

        values = self._slot_values()
        self.assertNotIn("08:00", values)
        self.assertIn("10:30", values)
        self.assertIn("13:00", values)
        self.assertNotIn("15:30", values)

    def test_interval_mode_when_fixed_times_disabled(self):
        self.policy.use_fixed_start_times = False
        self.policy.save(update_fields=["use_fixed_start_times"])

        values = self._slot_values()
        self.assertIn("08:00", values)
        self.assertIn("08:30", values)
        self.assertGreater(len(values), 4)

    def test_policy_form_parses_fixed_start_times(self):
        form = BookingPolicyForm(
            data={
                "minimum_notice_days": 14,
                "maximum_booking_window_days": 60,
                "allow_same_day_booking": False,
                "allow_next_day_booking": False,
                "allow_last_minute_reopen": True,
                "auto_approve_bookings": False,
                "late_arrival_limit_minutes": 15,
                "reminder_hours_before": 24,
                "pending_holds_slot": True,
                "max_appointments_per_day": 4,
                "use_fixed_start_times": True,
                "fixed_start_times_text": "15:30, 08:00, 10:30",
                "slot_interval_minutes": 30,
                "buffer_minutes_between_bookings": 0,
                "service_gap_minutes": 30,
                "customer_cancellation_notice_hours": 24,
                "max_pending_bookings_per_customer": 1,
                "max_active_future_bookings_per_customer": 2,
                "booking_rate_limit_per_ip_per_hour": 5,
                "booking_rate_limit_per_email_per_day": 3,
                "booking_rate_limit_per_phone_per_day": 3,
                "enable_honeypot_protection": True,
                "max_reference_photo_size_mb": 5,
                "email_verification_required": True,
                "email_verification_expiration_minutes": 60,
                "salon_rules": "Rule",
                "salon_rules_en": "Rule EN",
                "msg_approved": "ok",
                "msg_rejected": "no",
                "msg_cancelled": "cancel",
                "msg_edited": "edit",
                "msg_no_show": "noshow",
                "msg_pending": "pending",
                "msg_reminder": "reminder",
            },
            instance=self.policy,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(
            saved.fixed_start_times,
            ["08:00", "10:30", "15:30"],
        )


class LastMinuteReopenTests(TestCase):
    def setUp(self):
        cache.clear()
        user = get_user_model().objects.create_user(
            username="lm_owner",
            password="password",
        )
        self.salon = Salon.objects.create(owner=user, name="LM Salon", slug="lm-salon")
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=14,
            maximum_booking_window_days=60,
            allow_last_minute_reopen=True,
            pending_holds_slot=True,
            slot_interval_minutes=30,
            email_verification_required=False,
        )
        self.customer = Customer.objects.create(
            salon=self.salon,
            full_name="LM Customer",
            phone_number="070888777",
            instagram_username="lm_customer",
        )
        self.now = timezone.make_aware(
            datetime.combine(timezone.localdate(), time(7, 0)),
            timezone.get_current_timezone(),
        )
        self.inside_date = timezone.localdate(self.now) + timedelta(days=3)
        while self.inside_date.weekday() == WorkingHours.Weekday.SUNDAY:
            self.inside_date += timedelta(days=1)
        for weekday in range(6):
            WorkingHours.objects.get_or_create(
                salon=self.salon,
                weekday=weekday,
                defaults={
                    "is_working_day": True,
                    "start_time": time(8, 0),
                    "end_time": time(18, 0),
                },
            )

    def _aware_at(self, hour, minute, date=None):
        date = date or self.inside_date
        return timezone.make_aware(
            datetime.combine(date, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def _create_booking(self, status, start_hour=10, end_hour=12):
        booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=status,
            source=Booking.Source.OWNER_MANUAL,
            start_at=self._aware_at(start_hour, 0),
            end_at=self._aware_at(end_hour, 0),
            total_duration_minutes=(end_hour - start_hour) * 60,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.service,
            service_name_snapshot=self.service.name,
            duration_minutes_snapshot=self.service.duration_minutes,
            price_snapshot=self.service.base_price,
            sort_order=0,
        )
        return booking

    def test_cancel_inside_notice_creates_released_slot(self):
        booking = self._create_booking(Booking.Status.APPROVED)
        release_booking_slot(booking)
        booking.status = Booking.Status.CANCELLED
        booking.save()
        self.assertEqual(ReleasedSlot.objects.filter(salon=self.salon, is_active=True).count(), 1)
        release = ReleasedSlot.objects.get(salon=self.salon)
        self.assertEqual(release.start_at, booking.start_at)

    def test_inside_notice_date_shows_only_released_start(self):
        booking = self._create_booking(Booking.Status.APPROVED)
        release_booking_slot(booking)
        booking.status = Booking.Status.CANCELLED
        booking.save()
        slots = get_available_slots(
            self.salon,
            self.service,
            self.inside_date,
            now=self.now,
        )
        self.assertEqual([s["value"] for s in slots], ["10:00"])

    def test_inside_notice_without_release_returns_no_slots(self):
        slots = get_available_slots(
            self.salon,
            self.service,
            self.inside_date,
            now=self.now,
        )
        self.assertEqual(slots, [])

    def test_toggle_off_does_not_release(self):
        self.policy.allow_last_minute_reopen = False
        self.policy.save()
        booking = self._create_booking(Booking.Status.APPROVED)
        result = release_booking_slot(booking)
        self.assertIsNone(result)
        self.assertEqual(ReleasedSlot.objects.count(), 0)

    def test_early_open_dates_listed(self):
        booking = self._create_booking(Booking.Status.APPROVED)
        release_booking_slot(booking)
        today = get_salon_local_today(self.salon)
        notice_cutoff = today + timedelta(days=14)
        dates = get_last_minute_open_dates(self.salon, today, notice_cutoff, now=self.now)
        self.assertIn(self.inside_date.isoformat(), dates)

    def test_booking_consumes_released_slot(self):
        booking = self._create_booking(Booking.Status.APPROVED)
        release_booking_slot(booking)
        booking.status = Booking.Status.CANCELLED
        booking.save()
        outside_date = timezone.localdate(self.now) + timedelta(days=20)
        while outside_date.weekday() == WorkingHours.Weekday.SUNDAY:
            outside_date += timedelta(days=1)
        selected_date = self.inside_date
        response = self.client.post(
            "/book/lm-salon/request/",
            {
                "service": self.service.id,
                "date": selected_date.isoformat(),
                "start_time": "10:00",
                "full_name": "New Client",
                "phone_number": "070888778",
                "instagram_username": "newclient",
                "email": "new@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ReleasedSlot.objects.filter(salon=self.salon, is_active=True).exists()
        )

    def test_normal_window_returns_full_slot_list(self):
        normal_date = timezone.localdate(self.now) + timedelta(days=20)
        while normal_date.weekday() == WorkingHours.Weekday.SUNDAY:
            normal_date += timedelta(days=1)
        slots = get_available_slots(
            self.salon,
            self.service,
            normal_date,
            now=self.now,
        )
        values = {s["value"] for s in slots}
        self.assertIn("08:00", values)
        self.assertIn("10:00", values)

    def test_reject_pending_releases_slot(self):
        booking = self._create_booking(Booking.Status.PENDING)
        release_booking_slot(booking)
        self.assertEqual(ReleasedSlot.objects.filter(is_active=True).count(), 1)

    def test_release_allows_slot_after_overlapping_booking(self):
        """Bookings may start later inside a release when the release start is still busy."""
        Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=self._aware_at(8, 30),
            end_at=self._aware_at(13, 0),
            total_duration_minutes=270,
        )
        release_interval(
            self.salon,
            self._aware_at(12, 0),
            self._aware_at(16, 30),
        )
        slots = get_available_slots(
            self.salon,
            self.service,
            self.inside_date,
            now=self.now,
        )
        values = [s["value"] for s in slots]
        self.assertIn("13:00", values)
        self.assertNotIn("12:00", values)

    def test_short_release_excluded_from_service_aware_dates(self):
        release_interval(
            self.salon,
            self._aware_at(10, 0),
            self._aware_at(11, 0),
        )
        today = get_salon_local_today(self.salon)
        notice_cutoff = today + timedelta(days=14)
        raw_dates = get_last_minute_open_dates(
            self.salon, today, notice_cutoff, now=self.now
        )
        service_dates = get_last_minute_open_dates_for_services(
            self.salon, [self.service], today, notice_cutoff, now=self.now
        )
        self.assertIn(self.inside_date.isoformat(), raw_dates)
        self.assertNotIn(self.inside_date.isoformat(), service_dates)

    def test_consume_released_slot_splits_remaining_intervals(self):
        release = release_interval(
            self.salon,
            self._aware_at(12, 0),
            self._aware_at(16, 30),
        )
        consume_released_slot(
            self.salon,
            self._aware_at(13, 30),
            self._aware_at(15, 30),
        )
        release.refresh_from_db()
        self.assertFalse(release.is_active)
        active = list(
            ReleasedSlot.objects.filter(salon=self.salon, is_active=True).order_by("start_at")
        )
        self.assertEqual(len(active), 2)
        self.assertEqual(active[0].start_at, self._aware_at(12, 0))
        self.assertEqual(active[0].end_at, self._aware_at(13, 30))
        self.assertEqual(active[1].start_at, self._aware_at(15, 30))
        self.assertEqual(active[1].end_at, self._aware_at(16, 30))

    def test_cancel_after_partial_booking_restores_all_start_slots(self):
        release_interval(
            self.salon,
            self._aware_at(12, 0),
            self._aware_at(16, 30),
        )
        booking = self._create_booking(Booking.Status.APPROVED, start_hour=13, end_hour=15)
        booking.start_at = self._aware_at(13, 30)
        booking.end_at = self._aware_at(15, 30)
        booking.save(update_fields=["start_at", "end_at"])
        consume_released_slot(self.salon, booking.start_at, booking.end_at)
        release_booking_slot(booking)
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        slots = get_available_slots(
            self.salon,
            self.service,
            self.inside_date,
            now=self.now,
        )
        values = [s["value"] for s in slots]
        self.assertIn("13:00", values)
        self.assertIn("13:30", values)
        self.assertIn("14:00", values)
        self.assertIn("14:30", values)

    def test_last_minute_dates_api_returns_service_aware_dates(self):
        release_interval(
            self.salon,
            self._aware_at(12, 0),
            self._aware_at(16, 30),
        )
        response = self.client.get(
            f"/book/{self.salon.slug}/last-minute-dates/?services={self.service.id}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(self.inside_date.isoformat(), data["dates"])

    def test_available_slots_api_flags_release_unavailable(self):
        release_interval(
            self.salon,
            self._aware_at(10, 0),
            self._aware_at(11, 0),
        )
        response = self.client.get(
            f"/book/{self.salon.slug}/slots/"
            f"?services={self.service.id}&date={self.inside_date.isoformat()}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots"], [])
        self.assertTrue(data["last_minute"])
        self.assertTrue(data["release_unavailable"])


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
        BookingPolicy.objects.create(salon=self.salon_a, minimum_notice_days=0, email_verification_required=False)
        BookingPolicy.objects.create(salon=self.salon_b, minimum_notice_days=0, email_verification_required=False)
        self.service_a = Service.objects.create(
            salon=self.salon_a, name="Manicure", duration_minutes=120, base_price=600
        )
        for weekday in range(6):
            WorkingHours.objects.create(
                salon=self.salon_a,
                weekday=weekday,
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

    def test_owner_dashboard_is_not_cacheable(self):
        self.client.login(username="owner_a", password="pass")
        response = self.client.get("/owner/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    def test_owner_logout_clears_session_and_uses_replace_redirect(self):
        self.client.login(username="owner_a", password="pass")
        response = self.client.get("/owner/logout/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "location.replace")
        self.assertContains(response, "/owner/login/")
        dashboard = self.client.get("/owner/dashboard/")
        self.assertEqual(dashboard.status_code, 302)
        self.assertIn("/owner/login/", dashboard.url)

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

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_booking_email_failure_does_not_undo_request(self):
        from unittest.mock import patch

        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        before = Booking.objects.count()
        with patch("booking.email_utils._send_email", return_value=(False, "error")):
            response = self.client.post(
                "/book/salon-a/request/",
                {
                    "service": self.service_a.id,
                    "date": selected_date.isoformat(),
                    "start_time": "08:00",
                    "full_name": "Email Fail Test",
                    "phone_number": "079999001",
                    "instagram_username": "email_fail",
                    "email": "fail@example.com",
                    "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                    "rules_accepted": "on",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), before + 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_customer_can_cancel_approved_booking_with_notice(self):
        from django.core import mail

        self.booking_a.status = Booking.Status.APPROVED
        self.booking_a.start_at = timezone.now() + timedelta(hours=48)
        self.booking_a.end_at = self.booking_a.start_at + timedelta(hours=2)
        self.booking_a.save()
        self.customer_a.email = "customer@example.com"
        self.customer_a.save()
        self.salon_a.booking_policy.customer_cancellation_notice_hours = 24
        self.salon_a.booking_policy.save()

        url = reverse("booking:manage_booking_cancel", args=[self.booking_a.manage_token])
        response = self.client.post(url, {"confirm": "yes"})
        self.assertEqual(response.status_code, 302)
        self.booking_a.refresh_from_db()
        self.assertEqual(self.booking_a.status, Booking.Status.CANCELLED)
        self.assertGreaterEqual(len(mail.outbox), 1)

    def test_owner_available_slots_returns_valid_times(self):
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        self.client.login(username="owner_a", password="pass")
        response = self.client.get(
            reverse("booking:owner_available_slots"),
            {
                "service": self.service_a.id,
                "date": selected_date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        values = [slot["value"] for slot in data["slots"]]
        self.assertIn("08:00", values)
        self.assertTrue(all(":" in value for value in values))

    def test_manage_booking_token_is_uuid_not_sequential(self):
        self.assertEqual(len(str(self.booking_a.manage_token)), 36)
        self.assertNotEqual(str(self.booking_a.manage_token), str(self.booking_a.pk))

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
            email_verification_required=False,
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
                "services": [self.service.id],
                "date": selected.isoformat(),
                "start_time": "14:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "активен")

    def test_honeypot_filled_does_not_create_booking(self):
        before = Booking.objects.count()
        response = self.client.post(
            "/book/salon-a/request/",
            {
                **self._post_data("070111003", "honeypot@example.com"),
                "company_website": "https://spam.example",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), before)

    def test_owner_manual_booking_rejects_invalid_slot(self):
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        self._create_booking("070111222", "block@example.com", start_time=(10, 0))
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Manual Customer",
                "phone_number": "070222333",
                "instagram_username": "manual2",
                "email": "manual2@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.service.id],
                "date": selected.isoformat(),
                "start_time": "10:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Booking.objects.filter(customer__phone_number="070222333").exists()
        )


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
        BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            max_reference_photo_size_mb=5,
            email_verification_required=False,
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

    def test_valid_image_upload_creates_booking_with_photo(self):
        response = self.client.post(
            "/book/salon-a/request/",
            {
                "service": self.service.id,
                "date": self._future_date().isoformat(),
                "start_time": "08:00",
                "full_name": "Photo Upload",
                "phone_number": "070888999",
                "instagram_username": "photo_upload",
                "email": "upload@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
                "reference_photo": _make_test_image("JPEG", "nail.jpg"),
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(customer__phone_number="070888999")
        self.assertTrue(booking.reference_photo.name)


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


class ContactLinksTests(TestCase):
    def test_viber_link_uses_draft_parameter(self):
        links = build_contact_links("070123456", "Здраво Maria")
        self.assertIn("draft=", links["viber"])
        self.assertNotIn("&text=", links["viber"])
        self.assertIn("%2B38970123456", links["viber"])

    def test_whatsapp_link_uses_api_send_with_prefilled_text(self):
        links = build_contact_links("070123456", "Hello there")
        self.assertTrue(links["whatsapp"].startswith("https://api.whatsapp.com/send?"))
        self.assertIn("phone=38970123456", links["whatsapp"])
        self.assertIn("text=Hello", links["whatsapp"])


class MultiServiceBookingTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Salon A", slug="salon-a")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            service_gap_minutes=30,
            email_verification_required=False,
        )
        self.manicure = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=600,
        )
        self.pedicure = Service.objects.create(
            salon=self.salon,
            name="Pedicure",
            duration_minutes=120,
            base_price=800,
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

    def test_calculate_combined_duration_minutes(self):
        total = calculate_combined_duration_minutes(
            [self.manicure, self.pedicure],
            self.salon,
        )
        self.assertEqual(total, 270)

    def test_build_service_schedule_example(self):
        selected = self._future_date()
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        schedule = build_service_schedule(
            start,
            [self.manicure, self.pedicure],
            self.salon,
        )
        self.assertEqual(schedule[0]["start_time"], "08:00")
        self.assertEqual(schedule[0]["end_time"], "10:00")
        self.assertEqual(schedule[1]["start_time"], "10:30")
        self.assertEqual(schedule[1]["end_time"], "12:30")

    def test_multi_service_slots_available(self):
        selected = self._future_date()
        slots = get_available_slots(
            self.salon,
            [self.manicure, self.pedicure],
            selected,
        )
        values = {slot["value"] for slot in slots}
        self.assertIn("08:00", values)

    def test_multi_service_no_slots_when_day_full(self):
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Blocked",
            phone_number="070999111",
            instagram_username="blocked",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=start + timedelta(minutes=600),
            total_duration_minutes=600,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Manicure",
        )
        slots = get_available_slots(
            self.salon,
            [self.manicure, self.pedicure],
            selected,
        )
        self.assertEqual(slots, [])

    def test_customer_post_two_services_creates_rows(self):
        selected = self._future_date()
        response = self.client.post(
            "/book/salon-a/request/",
            {
                "service_ids": f"{self.manicure.id},{self.pedicure.id}",
                "date": selected.isoformat(),
                "start_time": "08:00",
                "full_name": "Multi Customer",
                "phone_number": "071222333",
                "instagram_username": "multi",
                "email": "multi@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(customer__phone_number="071222333")
        self.assertEqual(booking.booking_services.count(), 2)
        self.assertEqual(booking.total_duration_minutes, 270)

    def test_invalid_service_id_rejected(self):
        selected = self._future_date()
        response = self.client.post(
            "/book/salon-a/request/",
            {
                "service_ids": f"{self.manicure.id},99999",
                "date": selected.isoformat(),
                "start_time": "08:00",
                "full_name": "Bad Customer",
                "phone_number": "071333444",
                "instagram_username": "bad",
                "email": "bad@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Booking.objects.filter(customer__phone_number="071333444").exists()
        )

    def test_approved_multi_service_blocks_full_range(self):
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Booked",
            phone_number="070888777",
            instagram_username="booked",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.ONLINE,
            start_at=start,
            end_at=start + timedelta(minutes=270),
            total_duration_minutes=270,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Manicure",
            sort_order=0,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.pedicure,
            service_name_snapshot="Pedicure",
            sort_order=1,
        )
        self.assertIsNone(
            is_slot_available(
                self.salon,
                [self.manicure, self.pedicure],
                selected,
                "08:00",
            )
        )
        single_slots = get_available_slots(self.salon, self.manicure, selected)
        values = {slot["value"] for slot in single_slots}
        self.assertTrue(values)
        self.assertNotIn("08:00", values)

    def test_owner_manual_two_services(self):
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Owner Multi",
                "phone_number": "070444555",
                "instagram_username": "owner_multi",
                "email": "owner_multi@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.manicure.id, self.pedicure.id],
                "date": selected.isoformat(),
                "start_time": "08:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get(customer__phone_number="070444555")
        self.assertEqual(booking.booking_services.count(), 2)
        self.assertEqual(booking.total_duration_minutes, 270)

    def test_owner_slots_api_with_services_param(self):
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.get(
            reverse("booking:owner_available_slots"),
            {"services": f"{self.manicure.id},{self.pedicure.id}", "date": selected.isoformat()},
        )
        data = response.json()
        values = {slot["value"] for slot in data["slots"]}
        self.assertIn("08:00", values)

    def test_owner_booking_detail_returns_service_ids(self):
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Detail",
            phone_number="070666777",
            instagram_username="detail",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=start + timedelta(minutes=270),
            total_duration_minutes=270,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Manicure",
            sort_order=0,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.pedicure,
            service_name_snapshot="Pedicure",
            sort_order=1,
        )
        self.client.login(username="owner", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_detail", args=[booking.pk])
        )
        data = response.json()
        self.assertEqual(data["service_ids"], [self.manicure.id, self.pedicure.id])
        self.assertEqual(len(data["service_schedule"]), 2)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="noreply@test.local",
    )
    def test_email_contains_both_service_names(self):
        from django.core import mail

        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Email Customer",
            phone_number="070777888",
            instagram_username="email",
            email="email@example.com",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.ONLINE,
            start_at=start,
            end_at=start + timedelta(minutes=270),
            total_duration_minutes=270,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Manicure",
            sort_order=0,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.pedicure,
            service_name_snapshot="Pedicure",
            sort_order=1,
        )
        from .email_utils import send_booking_approved_email

        sent, reason = send_booking_approved_email(booking)
        self.assertTrue(sent, reason)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Manicure", body)
        self.assertIn("Pedicure", body)

    def test_format_services_for_email_multi(self):
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Format",
            phone_number="070111999",
            instagram_username="format",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=start + timedelta(minutes=270),
            total_duration_minutes=270,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Manicure",
        )
        BookingService.objects.create(
            booking=booking,
            service=self.pedicure,
            service_name_snapshot="Pedicure",
        )
        text = format_services_for_email(booking)
        self.assertIn("Manicure", text)
        self.assertIn("Pedicure", text)
        self.assertIn("•", text)


class EmailVerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner_verify",
            email="owner_verify@example.com",
            password="pass",
        )
        self.salon = Salon.objects.create(owner=self.owner, name="Salon V", slug="salon-v")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            email_verification_required=True,
            email_verification_expiration_minutes=60,
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

    def _future_date(self):
        selected = timezone.localdate() + timedelta(days=20)
        while selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        return selected

    def _booking_post_data(self, **extra):
        data = {
            "service": self.service.id,
            "date": self._future_date().isoformat(),
            "start_time": "08:00",
            "full_name": "Verify Customer",
            "phone_number": "070555111",
            "instagram_username": "verify_me",
            "email": "verify@example.com",
            "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
            "rules_accepted": "on",
        }
        data.update(extra)
        return data

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_post_sends_verification_email_not_owner_email(self):
        from django.core import mail

        response = self.client.post("/book/salon-v/request/", self._booking_post_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("booking:booking_verify_email_sent"))
        booking = Booking.objects.get(customer__email="verify@example.com")
        self.assertEqual(booking.status, Booking.Status.UNVERIFIED)
        customer_messages = [m for m in mail.outbox if "verify@example.com" in m.to]
        owner_messages = [m for m in mail.outbox if "owner_verify@example.com" in m.to]
        self.assertEqual(len(customer_messages), 1)
        self.assertIn("verify", customer_messages[0].body.lower())
        self.assertEqual(len(owner_messages), 0)

    def test_unverified_not_in_owner_pending(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data())
        self.client.login(username="owner_verify", password="pass")
        response = self.client.get("/owner/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Booking.objects.filter(salon=self.salon, status=Booking.Status.PENDING).count(),
            0,
        )

    def test_unverified_does_not_block_slots(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data())
        slots = get_available_slots(self.salon, [self.service], self._future_date())
        values = [slot["value"] for slot in slots]
        self.assertIn("08:00", values)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_valid_token_promotes_to_pending_and_sends_emails(self):
        from django.core import mail

        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555112"))
        booking = Booking.objects.get(customer__phone_number="070555112")
        token = booking.email_verification_token
        self.assertIsNotNone(token)
        response = self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertIsNotNone(booking.email_verified_at)
        self.assertIsNone(booking.email_verification_token)
        customer_messages = [m for m in mail.outbox if "verify@example.com" in m.to]
        self.assertGreaterEqual(len(customer_messages), 2)
        owner_messages = [m for m in mail.outbox if "owner_verify@example.com" in m.to]
        self.assertEqual(len(owner_messages), 1)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verify_skips_owner_email_when_owner_inbox_matches_customer(self):
        from django.core import mail

        self.owner.email = "verify@example.com"
        self.owner.save()
        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555116"))
        booking = Booking.objects.get(customer__phone_number="070555116")
        token = booking.email_verification_token
        response = self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        self.assertEqual(response.status_code, 200)
        customer_messages = [m for m in mail.outbox if "verify@example.com" in m.to]
        self.assertGreaterEqual(len(customer_messages), 2)
        owner_dashboard_messages = [
            m for m in customer_messages if "owner/dashboard" in m.body
        ]
        self.assertEqual(len(owner_dashboard_messages), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_request_received_email_uses_macedonian(self):
        from django.core import mail

        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555117"))
        booking = Booking.objects.get(customer__phone_number="070555117")
        token = booking.email_verification_token
        self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        customer_messages = [m for m in mail.outbox if "verify@example.com" in m.to]
        request_received = next(
            m
            for m in customer_messages
            if str(booking.manage_token) in m.body
        )
        self.assertIn("Го примивме вашето барање за термин", request_received.subject)
        self.assertIn("Го примивме вашето барање за термин", request_received.body)
        self.assertNotIn("You have a new booking request", request_received.body)

    def test_expired_token_shows_message_and_removes_booking(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555113"))
        booking = Booking.objects.get(customer__phone_number="070555113")
        token = booking.email_verification_token
        Booking.objects.filter(pk=booking.pk).update(
            verification_expires_at=timezone.now() - timedelta(minutes=1)
        )
        response = self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        self.assertContains(
            response,
            _("The verification link has expired. Please submit a new booking request."),
        )
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_token_after_slot_taken_shows_unavailable_message(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555114"))
        booking = Booking.objects.get(customer__phone_number="070555114")
        token = booking.email_verification_token
        other = Customer.objects.create(
            salon=self.salon,
            full_name="Other",
            phone_number="070555115",
            instagram_username="other",
        )
        start = booking.start_at
        Booking.objects.create(
            salon=self.salon,
            customer=other,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=start + timedelta(minutes=120),
            total_duration_minutes=120,
            rules_accepted=True,
        )
        response = self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        self.assertContains(
            response,
            _("The selected time slot is no longer available. Please choose another time."),
        )
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_unverified_does_not_consume_released_slot(self):
        self.policy.minimum_notice_days = 14
        self.policy.save()
        inside_date = timezone.localdate() + timedelta(days=3)
        while inside_date.weekday() == WorkingHours.Weekday.SUNDAY:
            inside_date += timedelta(days=1)
        start = timezone.make_aware(
            datetime.combine(inside_date, time(12, 0)),
            timezone.get_current_timezone(),
        )
        end = start + timedelta(hours=4, minutes=30)
        release_interval(self.salon, start, end)
        self.client.post(
            "/book/salon-v/request/",
            self._booking_post_data(
                phone_number="070555118",
                date=inside_date.isoformat(),
                start_time="13:00",
            ),
        )
        self.assertTrue(
            ReleasedSlot.objects.filter(salon=self.salon, is_active=True).exists()
        )

    def test_failed_verify_restores_released_slot(self):
        self.policy.minimum_notice_days = 14
        self.policy.save()
        inside_date = timezone.localdate() + timedelta(days=4)
        while inside_date.weekday() == WorkingHours.Weekday.SUNDAY:
            inside_date += timedelta(days=1)
        start = timezone.make_aware(
            datetime.combine(inside_date, time(12, 0)),
            timezone.get_current_timezone(),
        )
        end = start + timedelta(hours=4, minutes=30)
        release_interval(self.salon, start, end)
        self.client.post(
            "/book/salon-v/request/",
            self._booking_post_data(
                phone_number="070555119",
                date=inside_date.isoformat(),
                start_time="13:00",
            ),
        )
        booking = Booking.objects.get(customer__phone_number="070555119")
        token = booking.email_verification_token
        other = Customer.objects.create(
            salon=self.salon,
            full_name="Blocker",
            phone_number="070555121",
            instagram_username="blocker",
        )
        Booking.objects.create(
            salon=self.salon,
            customer=other,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=booking.start_at,
            end_at=booking.end_at,
            total_duration_minutes=120,
            rules_accepted=True,
        )
        response = self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())
        self.assertTrue(
            ReleasedSlot.objects.filter(salon=self.salon, is_active=True).exists()
        )

    def test_verify_failed_page_links_back_to_salon_booking(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555120"))
        booking = Booking.objects.get(customer__phone_number="070555120")
        booking.verification_expires_at = timezone.now() - timedelta(minutes=1)
        booking.save(update_fields=["verification_expires_at"])
        response = self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, booking.email_verification_token])
        )
        self.assertContains(response, reverse("booking:book_salon", args=[self.salon.slug]))
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_verification_token_is_uuid_not_sequential_id(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555116"))
        booking = Booking.objects.get(customer__phone_number="070555116")
        self.assertIsNotNone(booking.email_verification_token)
        self.assertNotEqual(str(booking.email_verification_token), str(booking.pk))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_photo_preserved_after_successful_verify(self):
        data = self._booking_post_data(phone_number="070555117")
        data["reference_photo"] = _make_test_image("JPEG", "nail.jpg")
        self.client.post("/book/salon-v/request/", data)
        booking = Booking.objects.get(customer__phone_number="070555117")
        photo_name = booking.reference_photo.name
        self.assertTrue(photo_name)
        token = booking.email_verification_token
        self.client.get(
            reverse("booking:verify_booking_email", args=[self.salon.slug, token])
        )
        booking.refresh_from_db()
        self.assertEqual(booking.reference_photo.name, photo_name)

    def test_cleanup_command_removes_expired_unverified_and_photo(self):
        data = self._booking_post_data(phone_number="070555118")
        data["reference_photo"] = _make_test_image("JPEG", "cleanup.jpg")
        self.client.post("/book/salon-v/request/", data)
        booking = Booking.objects.get(customer__phone_number="070555118")
        photo_name = booking.reference_photo.name
        Booking.objects.filter(pk=booking.pk).update(
            verification_expires_at=timezone.now() - timedelta(minutes=5)
        )
        call_command("cleanup_unverified_bookings")
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())
        from django.core.files.storage import default_storage

        self.assertFalse(default_storage.exists(photo_name))

    def test_unverified_counts_toward_pending_limit(self):
        self.client.post("/book/salon-v/request/", self._booking_post_data(phone_number="070555119"))
        response = self.client.post(
            "/book/salon-v/request/",
            self._booking_post_data(phone_number="070555119", email="verify2@example.com"),
        )
        self.assertEqual(response.status_code, 200)


class PhotoSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner_a = User.objects.create_user(username="owner_a_sec", password="pass")
        self.owner_b = User.objects.create_user(username="owner_b_sec", password="pass")
        self.salon_a = Salon.objects.create(owner=self.owner_a, name="Salon A", slug="salon-a-sec")
        self.salon_b = Salon.objects.create(owner=self.owner_b, name="Salon B", slug="salon-b-sec")
        BookingPolicy.objects.create(
            salon=self.salon_a,
            minimum_notice_days=0,
            email_verification_required=False,
        )
        self.service = Service.objects.create(
            salon=self.salon_a,
            name="Manicure",
            duration_minutes=120,
            base_price=600,
        )
        self.customer = Customer.objects.create(
            salon=self.salon_a,
            full_name="Photo Customer",
            phone_number="070444111",
            instagram_username="photo_sec",
            email="photo_sec@example.com",
        )
        selected = timezone.localdate() + timedelta(days=20)
        if selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        start = timezone.make_aware(
            datetime.combine(selected, time(10, 0)),
            timezone.get_current_timezone(),
        )
        self.booking = Booking.objects.create(
            salon=self.salon_a,
            customer=self.customer,
            status=Booking.Status.PENDING,
            source=Booking.Source.ONLINE,
            start_at=start,
            end_at=start + timedelta(minutes=120),
            total_duration_minutes=120,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=self.booking,
            service=self.service,
            service_name_snapshot="Manicure",
        )
        self.booking.reference_photo.save(
            "test.jpg",
            _make_test_image("JPEG", "test.jpg"),
            save=True,
        )

    def test_anonymous_photo_request_redirects_or_forbidden(self):
        response = self.client.get(
            reverse("booking:owner_booking_photo", args=[self.booking.id])
        )
        self.assertIn(response.status_code, (302, 403))

    def test_cross_salon_owner_gets_404(self):
        self.client.login(username="owner_b_sec", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_photo", args=[self.booking.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_can_view_own_booking_photo_with_security_headers(self):
        self.client.login(username="owner_a_sec", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_photo", args=[self.booking.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "private, no-store")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_owner_delete_photo_clears_field_and_file(self):
        from django.core.files.storage import default_storage

        photo_name = self.booking.reference_photo.name
        self.client.login(username="owner_a_sec", password="pass")
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "delete_reference_photo",
                "booking_id": self.booking.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertFalse(self.booking.reference_photo)
        self.assertEqual(
            self.booking.reference_photo_status,
            Booking.ReferencePhotoStatus.REMOVED,
        )
        self.assertFalse(default_storage.exists(photo_name))

    def test_manage_page_does_not_expose_photo_url(self):
        response = self.client.get(
            reverse("booking:manage_booking", args=[self.booking.manage_token])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "owner/booking/")
        self.assertNotContains(response, "booking_photos")

    def test_booking_form_shows_upload_warning(self):
        response = self.client.get("/book/salon-a-sec/request/")
        self.assertContains(
            response,
            _(
                "Upload only a photo related to the service. Inappropriate images will be removed and the customer may be blocked."
            ),
        )


class AutoCompleteAndCalendarHistoryTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner_auto",
            email="owner_auto@example.com",
            password="pass",
        )
        self.client.login(username="owner_auto", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Auto Salon", slug="auto-salon")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            maximum_booking_window_days=60,
            calendar_history_days=365,
            auto_complete_hours_after_end=4,
        )
        self.customer = Customer.objects.create(
            salon=self.salon,
            full_name="Past Client",
            phone_number="070999888",
            instagram_username="past",
            email="past@example.com",
        )
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=600,
        )

    def _make_booking(self, *, days_ago, status=Booking.Status.APPROVED, hours=2):
        start = timezone.now() - timedelta(days=days_ago, hours=4)
        end = start + timedelta(hours=hours)
        booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=status,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=end,
            total_duration_minutes=int(hours * 60),
        )
        BookingService.objects.create(
            booking=booking,
            service=self.service,
            service_name_snapshot=self.service.name,
            duration_minutes_snapshot=self.service.duration_minutes,
            price_snapshot=self.service.base_price,
        )
        return booking

    def test_calendar_history_uses_policy_default(self):
        self.assertEqual(get_calendar_history_days(self.salon), 365)

    def test_auto_complete_marks_past_approved_booking(self):
        booking = self._make_booking(days_ago=1, status=Booking.Status.APPROVED)
        updated = auto_complete_past_bookings(salon=self.salon)
        self.assertEqual(updated, 1)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)
        self.assertTrue(
            BookingActivityLog.objects.filter(
                booking=booking,
                action=BookingActivityLog.Action.COMPLETED,
                note__icontains="Auto-completed",
            ).exists()
        )

    def test_auto_complete_skips_when_grace_not_passed(self):
        start = timezone.now() - timedelta(hours=1)
        booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=start + timedelta(hours=2),
            total_duration_minutes=120,
        )
        updated = auto_complete_past_bookings(salon=self.salon)
        self.assertEqual(updated, 0)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.APPROVED)

    def test_auto_complete_disabled_when_grace_hours_zero(self):
        self.policy.auto_complete_hours_after_end = 0
        self.policy.save()
        booking = self._make_booking(days_ago=2, status=Booking.Status.APPROVED)
        updated = auto_complete_past_bookings(salon=self.salon)
        self.assertEqual(updated, 0)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.APPROVED)

    def test_old_completed_booking_hidden_from_calendar_api(self):
        old = self._make_booking(days_ago=400, status=Booking.Status.COMPLETED)
        recent = self._make_booking(days_ago=130, status=Booking.Status.COMPLETED)
        cutoff = get_calendar_history_cutoff_date(self.salon)
        self.assertFalse(booking_visible_on_calendar(old, cutoff))
        self.assertTrue(booking_visible_on_calendar(recent, cutoff))

        range_start = (timezone.now() - timedelta(days=450)).isoformat()
        range_end = (timezone.now() + timedelta(days=7)).isoformat()
        response = self.client.get(
            reverse("booking:owner_calendar_events"),
            {"start": range_start, "end": range_end},
        )
        self.assertEqual(response.status_code, 200)
        ids = {event["extendedProps"]["bookingId"] for event in response.json()["events"]}
        self.assertNotIn(old.id, ids)
        self.assertIn(recent.id, ids)

    def test_management_command_auto_completes(self):
        self._make_booking(days_ago=1, status=Booking.Status.APPROVED)
        call_command("auto_complete_past_bookings")
        self.assertEqual(
            Booking.objects.filter(salon=self.salon, status=Booking.Status.COMPLETED).count(),
            1,
        )


class CustomerBlockingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="blockowner", password="pass")
        self.salon = Salon.objects.create(name="Block Salon", slug="block-salon", owner=self.owner)
        self.policy = BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)
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
        self.customer = Customer.objects.create(
            salon=self.salon,
            full_name="Blocked Target",
            phone_number="070999888",
            email="target@example.com",
            instagram_username="target",
        )
        start = timezone.make_aware(
            datetime.combine(timezone.localdate() + timedelta(days=20), time(10, 0)),
            timezone.get_current_timezone(),
        )
        self.booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.PENDING,
            source=Booking.Source.ONLINE,
            start_at=start,
            end_at=start + timedelta(hours=2),
            total_duration_minutes=120,
            rules_accepted=True,
            client_device_token="device-abc-123",
        )
        BookingService.objects.create(
            booking=self.booking,
            service=self.service,
            service_name_snapshot="Manicure",
        )
        self.client.login(username="blockowner", password="pass")

    def _future_date(self):
        selected = timezone.localdate() + timedelta(days=20)
        while selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        return selected

    def test_owner_can_block_customer_via_unified_endpoint(self):
        response = self.client.post(
            reverse("booking:owner_block_customer"),
            {
                "booking_id": self.booking.id,
                "reason_code": CustomerBlocklist.ReasonCode.SPAM,
                "notes": "Repeated spam messages",
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        entry = CustomerBlocklist.objects.get(salon=self.salon, phone_number="070999888")
        self.assertTrue(entry.is_active)
        self.assertEqual(entry.reason_code, CustomerBlocklist.ReasonCode.SPAM)
        self.assertEqual(entry.device_token, "device-abc-123")
        self.assertEqual(entry.events.count(), 1)
        self.assertEqual(entry.events.first().event_type, CustomerBlockEvent.EventType.BLOCKED)

    def test_blocked_customer_cannot_submit_and_unblock_restores_access(self):
        self.client.post(
            reverse("booking:owner_block_customer"),
            {
                "customer_id": self.customer.id,
                "reason_code": CustomerBlocklist.ReasonCode.FAKE_BOOKINGS,
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )
        blocked = self.client.post(
            "/book/block-salon/request/",
            {
                "service": self.service.id,
                "date": self._future_date().isoformat(),
                "start_time": "12:00",
                "full_name": "Blocked Target",
                "phone_number": "070999888",
                "instagram_username": "target",
                "email": "target@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "не може да биде испратено")

        entry = CustomerBlocklist.objects.get(salon=self.salon, phone_number="070999888")
        unblock = self.client.post(
            reverse("booking:owner_unblock_customer", args=[entry.id]),
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(unblock.status_code, 200)
        self.assertTrue(unblock.json()["ok"])
        self.assertEqual(entry.events.filter(event_type=CustomerBlockEvent.EventType.UNBLOCKED).count(), 1)

    def test_device_token_blocks_even_with_different_phone(self):
        CustomerBlocklist.objects.create(
            salon=self.salon,
            phone_number="070000001",
            device_token="shared-device-token",
            reason_code=CustomerBlocklist.ReasonCode.OTHER,
            is_active=True,
            blocked_at=timezone.now(),
        )
        from .anti_abuse import is_customer_blocked

        self.assertTrue(
            is_customer_blocked(
                self.salon,
                phone="070111999",
                device_token="shared-device-token",
            )
        )

    def test_block_requires_reason(self):
        response = self.client.post(
            reverse("booking:owner_block_customer"),
            {"customer_id": self.customer.id, "reason_code": ""},
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_owner_block_context_returns_customer_details(self):
        response = self.client.get(
            reverse("booking:owner_customer_block_context"),
            {"booking_id": self.booking.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["customer_name"], "Blocked Target")
        self.assertEqual(data["booking_id"], self.booking.id)
        self.assertIn("reason_choices", data)


class ProductionReadinessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner_a = User.objects.create_user(username="prod_a", password="pass")
        self.owner_b = User.objects.create_user(username="prod_b", password="pass")
        self.salon_a = Salon.objects.create(owner=self.owner_a, name="Prod A", slug="prod-a")
        self.salon_b = Salon.objects.create(owner=self.owner_b, name="Prod B", slug="prod-b")
        BookingPolicy.objects.create(salon=self.salon_a, minimum_notice_days=0, email_verification_required=False)
        BookingPolicy.objects.create(salon=self.salon_b, minimum_notice_days=0, email_verification_required=False)
        self.service_a = Service.objects.create(
            salon=self.salon_a, name="Manicure", duration_minutes=120, base_price=600
        )
        self.service_b = Service.objects.create(
            salon=self.salon_b, name="Pedicure", duration_minutes=120, base_price=700
        )
        self.customer_a = Customer.objects.create(
            salon=self.salon_a,
            full_name="Prod Customer",
            phone_number="070100200",
        )
        self.customer_b = Customer.objects.create(
            salon=self.salon_b,
            full_name="Other Customer",
            phone_number="070300400",
        )
        selected = timezone.localdate() + timedelta(days=1)
        if selected.weekday() == WorkingHours.Weekday.SUNDAY:
            selected += timedelta(days=1)
        start = timezone.make_aware(datetime.combine(selected, time(10, 0)), timezone.get_current_timezone())
        self.booking_a = Booking.objects.create(
            salon=self.salon_a,
            customer=self.customer_a,
            status=Booking.Status.PENDING,
            source=Booking.Source.ONLINE,
            start_at=start,
            end_at=start + timedelta(hours=2),
            total_duration_minutes=120,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=self.booking_a,
            service=self.service_a,
            service_name_snapshot="Manicure",
        )

    def test_legacy_booking_success_url_returns_404(self):
        response = self.client.get(
            reverse("booking:booking_success_legacy", args=[self.booking_a.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_booking_success_without_session_returns_404(self):
        response = self.client.get(reverse("booking:booking_success"))
        self.assertEqual(response.status_code, 404)

    def test_booking_success_with_session_shows_page(self):
        session = self.client.session
        session["booking_success_id"] = self.booking_a.pk
        session.save()
        response = self.client.get(reverse("booking:booking_success"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prod Customer")

    def test_booking_success_session_is_one_time(self):
        session = self.client.session
        session["booking_success_id"] = self.booking_a.pk
        session.save()
        self.client.get(reverse("booking:booking_success"))
        response = self.client.get(reverse("booking:booking_success"))
        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_block_other_salon_customer(self):
        self.client.login(username="prod_a", password="pass")
        response = self.client.post(
            reverse("booking:owner_block_customer"),
            {
                "customer_id": self.customer_b.id,
                "reason_code": CustomerBlocklist.ReasonCode.SPAM,
            },
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 400)

    def test_owner_cannot_unblock_other_salon_entry(self):
        entry = CustomerBlocklist.objects.create(
            salon=self.salon_b,
            phone_number="070300400",
            reason_code=CustomerBlocklist.ReasonCode.OTHER,
            is_active=True,
            blocked_at=timezone.now(),
        )
        self.client.login(username="prod_a", password="pass")
        response = self.client.post(
            reverse("booking:owner_unblock_customer", args=[entry.id]),
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 404)

    def test_booking_service_rejects_cross_salon_service(self):
        item = BookingService(
            booking=self.booking_a,
            service=self.service_b,
            service_name_snapshot="Pedicure",
        )
        with self.assertRaises(ValidationError):
            item.save()


class OwnerDashboardAjaxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="ajaxowner", password="pass")
        self.salon = Salon.objects.create(owner=self.owner, name="Ajax Salon", slug="ajax-salon")
        ensure_default_working_hours(self.salon)
        BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        self.client.login(username="ajaxowner", password="pass")

    def _fetch_post(self, data):
        return self.client.post(
            reverse("booking:owner_dashboard"),
            data,
            HTTP_X_REQUESTED_WITH="fetch",
        )

    def test_save_service_returns_json(self):
        response = self._fetch_post(
            {
                "action": "save_service",
                "name": "Pedicure",
                "duration_minutes": "120",
                "base_price": "1200",
                "sort_order": "1",
                "return_section": "services",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["action"], "save_service")
        self.assertIn("service", data["payload"])
        self.assertTrue(self.salon.services.filter(name="Pedicure").exists())

    def test_save_working_hours_returns_json(self):
        response = self._fetch_post(
            {
                "action": "save_working_hours",
                "return_section": "hours",
                "form-TOTAL_FORMS": "7",
                "form-INITIAL_FORMS": "7",
                "form-MIN_NUM_FORMS": "0",
                "form-MAX_NUM_FORMS": "1000",
                **{
                    f"form-{i}-weekday": str(i)
                    for i in range(7)
                },
                **{
                    f"form-{i}-id": str(
                        self.salon.working_hours.get(weekday=i).pk
                    )
                    for i in range(7)
                },
                **{
                    f"form-{i}-is_working_day": "on"
                    if i != WorkingHours.Weekday.SUNDAY
                    else ""
                    for i in range(7)
                },
                **{
                    f"form-{i}-start_time": "08:00"
                    for i in range(7)
                },
                **{
                    f"form-{i}-end_time": "18:00"
                    for i in range(7)
                },
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_invalid_customer_save_returns_400_json(self):
        response = self._fetch_post(
            {
                "action": "save_customer",
                "full_name": "",
                "phone_number": "",
                "return_section": "customers",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_delete_blocked_date_returns_json(self):
        from booking.models import DateWorkingHoursOverride

        row = DateWorkingHoursOverride.objects.create(
            salon=self.salon,
            date=timezone.localdate() + timedelta(days=30),
            mode=DateWorkingHoursOverride.Mode.CLOSED,
            reason="Holiday",
        )
        response = self._fetch_post(
            {
                "action": "delete_blocked_date",
                "override_id": row.id,
                "return_section": "availability",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(
            self.salon.date_working_hours_overrides.filter(pk=row.id).exists()
        )

    def test_reorder_price_items_returns_json(self):
        item = ServicePriceItem.objects.create(
            service=self.service,
            name="Classic",
            price_display="500",
            sort_order=0,
        )
        response = self._fetch_post(
            {
                "action": "reorder_price_items",
                "item_ids": str(item.id),
                "return_section": "services",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_manage_booking_cancel_fetch_returns_json(self):
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Cancel Me",
            phone_number="070123456",
            preferred_contact_method=Customer.PreferredContactMethod.VIBER,
        )
        start = timezone.now() + timedelta(hours=48)
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
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
        self.salon.booking_policy.customer_cancellation_notice_hours = 24
        self.salon.booking_policy.save()

        response = self.client.post(
            reverse("booking:manage_booking_cancel", args=[booking.manage_token]),
            {"confirm": "yes"},
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["cancelled"])
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
