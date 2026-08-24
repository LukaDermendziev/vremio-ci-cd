from datetime import datetime, time, timedelta
import io
import json
from unittest.mock import patch

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


def _run_deferred_immediately(func, *args, **kwargs):
    """TestCase rolls back transactions, so on_commit callbacks never fire — run inline."""
    return func(*args, **kwargs)

from .forms import BookingPolicyForm, BookingRequestForm
from .email_validation import suggest_email_correction, validate_email_no_common_typos
from .phone_validation import is_valid_mk_mobile, validate_mk_mobile_number
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
    calculate_line_items_duration_minutes,
    find_conflicting_booking,
    format_services_for_email,
    get_available_slots,
    leftover_start_after_visit,
    get_calendar_history_cutoff_date,
    get_calendar_history_days,
    get_last_minute_open_dates,
    get_last_minute_open_dates_for_services,
    get_owner_statistics,
    get_salon_local_today,
    is_slot_available,
    release_booking_slot,
    release_interval,
    consume_released_slot,
    ensure_default_working_hours,
    get_salon_page_hours_rows,
    send_booking_notification,
    send_due_booking_reminders,
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

    @override_settings(VREMIO_INSTAGRAM="vremio.mk")
    def test_home_shows_pricing_plans_for_owners(self):
        response = self.client.get("/")
        self.assertContains(response, 'id="plans"')
        self.assertContains(response, "Starter")
        self.assertContains(response, "990")
        self.assertContains(response, "1,990")
        self.assertContains(response, "2,990")
        self.assertContains(response, "data-plan-interest")
        self.assertContains(response, 'id="vm-lead-form"')
        self.assertContains(response, reverse("booking:plan_interest"))


class StarterWebsiteTemplateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="starter_owner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=self.user,
            name="City Studio",
            slug="city-studio",
            short_description="Modern booking studio",
            business_category=Salon.BusinessCategory.SALON,
            phone_number="070111222",
            plan=Salon.Plan.STARTER,
            is_active=True,
        )
        Service.objects.create(
            salon=self.salon,
            name="Haircut",
            duration_minutes=45,
            base_price=500,
            is_active=True,
        )
        BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)

    def test_starter_template_renders_vremio_style_site(self):
        response = self.client.get(reverse("booking:salon_page", args=[self.salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="st-page')
        self.assertContains(response, "City Studio")
        self.assertContains(response, "Modern booking studio")
        self.assertContains(response, "Haircut")
        self.assertContains(response, "st-footer-powered")
        self.assertContains(response, "Vremio")
        self.assertContains(response, _("Reviews coming soon."))
        self.assertNotContains(
            response, _("Care, style, and an appointment that suits you.")
        )

    def test_business_url_alias_uses_same_starter_page(self):
        response = self.client.get(
            reverse("booking:business_page", args=[self.salon.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="st-page')

    def test_pro_plan_keeps_custom_salon_page(self):
        self.salon.plan = Salon.Plan.PRO
        self.salon.save(update_fields=["plan"])
        self.assertEqual(self.salon.website_template, Salon.WebsiteTemplate.PRO)
        response = self.client.get(reverse("booking:salon_page", args=[self.salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="sp-page')
        self.assertNotContains(response, 'class="st-page')

    def test_premium_plan_uses_pro_website(self):
        self.salon.plan = Salon.Plan.PREMIUM
        self.salon.save(update_fields=["plan"])
        self.assertTrue(self.salon.uses_pro_website)
        self.assertEqual(self.salon.website_template, Salon.WebsiteTemplate.PRO)
        response = self.client.get(reverse("booking:salon_page", args=[self.salon.slug]))
        self.assertContains(response, 'class="sp-page')

    def test_starter_booking_flow_uses_vremio_theme(self):
        response = self.client.get(reverse("booking:book_salon", args=[self.salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bk-theme-starter")
        self.assertContains(response, 'data-step="1"')
        self.assertContains(response, 'id="bk-progress"')

    def test_pro_booking_flow_keeps_salon_theme(self):
        self.salon.plan = Salon.Plan.PRO
        self.salon.save(update_fields=["plan"])
        response = self.client.get(reverse("booking:book_salon", args=[self.salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "bk-theme-starter")

    @override_settings(
        VREMIO_CONTACT_EMAIL="leads@vremio.test",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_plan_interest_sends_email(self):
        from django.core import mail

        response = self.client.post(
            reverse("booking:plan_interest"),
            {
                "name": "Ana Owner",
                "plan": "pro",
                "contact_method": "instagram",
                "contact_value": "ana.nails",
                "website": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Pro", mail.outbox[0].subject)
        self.assertIn("Ana Owner", mail.outbox[0].body)
        self.assertIn("@ana.nails", mail.outbox[0].body)

    def test_plan_interest_requires_contact_value(self):
        response = self.client.post(
            reverse("booking:plan_interest"),
            {
                "name": "Ana Owner",
                "plan": "starter",
                "contact_method": "phone",
                "contact_value": "",
                "website": "",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])


class CustomerDomainTests(TestCase):
    @override_settings(
        ALLOWED_HOSTS=["www.fancyfingers.mk", "fancyfingers.mk", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk", "fancyfingers.mk"],
        CUSTOMER_DOMAIN_SALON_SLUG="fancy-fingers",
    )
    def test_customer_domain_root_serves_salon_page(self):
        owner = get_user_model().objects.create_user(
            username="ff_owner", password="pass"
        )
        Salon.objects.create(
            owner=owner,
            name="Fancy Fingers",
            slug="fancy-fingers",
            is_active=True,
            plan=Salon.Plan.PRO,
        )
        response = self.client.get(
            "/",
            HTTP_HOST="www.fancyfingers.mk",
            HTTP_ACCEPT_LANGUAGE="en-US,en;q=0.9",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fancy Fingers")
        self.assertContains(response, 'lang="mk"')
        self.assertNotEqual(response.status_code, 302)

    @override_settings(
        ALLOWED_HOSTS=["www.fancyfingers.mk", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk"],
        CUSTOMER_DOMAIN_SALON_SLUG="fancy-fingers",
    )
    def test_customer_domain_root_sets_csrf_cookie(self):
        owner = get_user_model().objects.create_user(
            username="ff_owner2", password="pass"
        )
        Salon.objects.create(
            owner=owner,
            name="Fancy Fingers",
            slug="fancy-fingers",
            is_active=True,
            plan=Salon.Plan.PRO,
        )
        response = self.client.get("/", HTTP_HOST="www.fancyfingers.mk")
        self.assertEqual(response.status_code, 200)
        self.assertIn("csrftoken", response.cookies)

    @override_settings(
        ALLOWED_HOSTS=["vremio-production.up.railway.app", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk"],
        CUSTOMER_DOMAIN_SALON_SLUG="fancy-fingers",
    )
    def test_railway_domain_still_shows_vremio_home(self):
        response = self.client.get("/", HTTP_HOST="vremio-production.up.railway.app")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vremio")

    @override_settings(
        ALLOWED_HOSTS=["www.fancyfingers.mk", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk"],
        CUSTOMER_DOMAIN_SALON_SLUG="fancy-fingers",
    )
    def test_customer_domain_html_uses_salon_favicon(self):
        owner = get_user_model().objects.create_user(
            username="ff_owner_fav", password="pass"
        )
        Salon.objects.create(
            owner=owner,
            name="Fancy Fingers",
            slug="fancy-fingers",
            is_active=True,
            plan=Salon.Plan.PRO,
        )
        response = self.client.get("/", HTTP_HOST="www.fancyfingers.mk")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "salon-favicon")
        self.assertNotContains(response, "vremio-favicon.svg")

    @override_settings(
        ALLOWED_HOSTS=["www.fancyfingers.mk", "vremio.up.railway.app", "testserver"],
        CUSTOMER_DOMAINS=["www.fancyfingers.mk"],
    )
    def test_favicon_ico_is_host_aware(self):
        salon_resp = self.client.get("/favicon.ico", HTTP_HOST="www.fancyfingers.mk")
        self.assertEqual(salon_resp.status_code, 200)
        self.assertEqual(salon_resp["Content-Type"], "image/x-icon")
        salon_bytes = b"".join(salon_resp.streaming_content)

        platform_resp = self.client.get(
            "/favicon.ico", HTTP_HOST="vremio.up.railway.app"
        )
        self.assertEqual(platform_resp.status_code, 200)
        self.assertEqual(platform_resp["Content-Type"], "image/x-icon")
        platform_bytes = b"".join(platform_resp.streaming_content)
        self.assertNotEqual(salon_bytes, platform_bytes)
        self.assertTrue(salon_bytes)
        self.assertTrue(platform_bytes)


class HealthCheckTests(TestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "ok")


class PageLoaderAndErrorPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="loaderowner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=self.user,
            name="Loader Salon",
            slug="loader-salon",
            plan=Salon.Plan.PRO,
        )
        Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
            is_active=True,
        )
        BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)

    def test_home_includes_page_loader_markup(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="vm-page-loader"')
        self.assertContains(response, "js/page_loader.js")
        self.assertContains(response, 'data-submit-hold-ms="900"')

    def test_booking_form_includes_page_loader(self):
        response = self.client.get(reverse("booking:book_salon", args=[self.salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="vm-page-loader"')
        self.assertContains(response, 'id="bk-submit"')

    @override_settings(DEBUG=False)
    def test_missing_url_uses_branded_404(self):
        response = self.client.get("/this-page-definitely-does-not-exist-xyz/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "404", status_code=404)
        self.assertContains(response, _("Page not found"), status_code=404)

    def test_custom_500_handler_renders_branded_page(self):
        from django.test import RequestFactory

        from .views import custom_server_error

        request = RequestFactory().get("/boom/")
        response = custom_server_error(request)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "500", status_code=500)
        self.assertContains(response, _("Something went wrong"), status_code=500)


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


class EmailValidationTests(TestCase):
    def test_suggests_gmail_typo_gmai(self):
        self.assertEqual(
            suggest_email_correction("marija@gmai.com"),
            "marija@gmail.com",
        )

    def test_suggests_gmail_typo_con(self):
        self.assertEqual(
            suggest_email_correction("user@gmail.con"),
            "user@gmail.com",
        )

    def test_accepts_valid_gmail(self):
        self.assertIsNone(suggest_email_correction("marija@gmail.com"))
        self.assertEqual(
            validate_email_no_common_typos("marija@gmail.com"),
            "marija@gmail.com",
        )

    def test_accepts_example_and_empty(self):
        self.assertIsNone(suggest_email_correction("customer@example.com"))
        self.assertEqual(validate_email_no_common_typos(""), "")

    def test_validate_raises_with_suggestion(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_email_no_common_typos("client@gmial.com")
        self.assertIn("gmail.com", str(ctx.exception))


class PhoneValidationTests(TestCase):
    def test_accepts_national_form(self):
        self.assertTrue(is_valid_mk_mobile("070123456"))
        self.assertEqual(validate_mk_mobile_number("070123456"), "070123456")

    def test_accepts_national_with_separators(self):
        self.assertEqual(validate_mk_mobile_number("070 123 456"), "070123456")
        self.assertEqual(validate_mk_mobile_number("070-123-456"), "070123456")

    def test_accepts_international_forms(self):
        self.assertEqual(validate_mk_mobile_number("+38970123456"), "070123456")
        self.assertEqual(validate_mk_mobile_number("38970123456"), "070123456")
        self.assertEqual(validate_mk_mobile_number("0038970123456"), "070123456")
        self.assertEqual(validate_mk_mobile_number("+389 70 123 456"), "070123456")

    def test_empty_passes_through(self):
        self.assertEqual(validate_mk_mobile_number(""), "")

    def test_rejects_too_short(self):
        self.assertFalse(is_valid_mk_mobile("0701234"))
        with self.assertRaises(ValidationError):
            validate_mk_mobile_number("0701234")

    def test_rejects_too_long(self):
        with self.assertRaises(ValidationError):
            validate_mk_mobile_number("07012345678")

    def test_rejects_wrong_prefix(self):
        # Landline-style / non-07 numbers and random digits.
        with self.assertRaises(ValidationError):
            validate_mk_mobile_number("021123456")
        with self.assertRaises(ValidationError):
            validate_mk_mobile_number("123456789")

    def test_rejects_international_non_mobile(self):
        # +389 must be followed by a mobile 7XXXXXXX.
        with self.assertRaises(ValidationError):
            validate_mk_mobile_number("+38921123456")


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
            plan=Salon.Plan.PRO,
        )
        Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=1000,
        )
        BookingPolicy.objects.create(salon=self.salon, email_verification_required=False)

    def _policy_post_data(self, **overrides):
        policy = self.salon.booking_policy
        data = {
            "action": "save_policy",
            "return_section": "policy",
            "minimum_notice_days": str(policy.minimum_notice_days),
            "maximum_booking_window_days": str(policy.maximum_booking_window_days),
            "late_arrival_limit_minutes": str(policy.late_arrival_limit_minutes),
            "reminder_hours_before": str(policy.reminder_hours_before),
            "max_appointments_per_day": str(policy.max_appointments_per_day),
            "slot_interval_minutes": str(policy.slot_interval_minutes),
            "buffer_minutes_between_bookings": str(policy.buffer_minutes_between_bookings),
            "service_gap_minutes": str(policy.service_gap_minutes),
            "customer_cancellation_notice_hours": str(policy.customer_cancellation_notice_hours),
            "max_pending_bookings_per_customer": str(policy.max_pending_bookings_per_customer),
            "max_active_future_bookings_per_customer": str(policy.max_active_future_bookings_per_customer),
            "booking_rate_limit_per_ip_per_hour": str(policy.booking_rate_limit_per_ip_per_hour),
            "booking_rate_limit_per_email_per_day": str(policy.booking_rate_limit_per_email_per_day),
            "booking_rate_limit_per_phone_per_day": str(policy.booking_rate_limit_per_phone_per_day),
            "max_reference_photo_size_mb": str(policy.max_reference_photo_size_mb),
            "email_verification_expiration_minutes": str(policy.email_verification_expiration_minutes),
            "sms_verification_expiration_minutes": str(policy.sms_verification_expiration_minutes),
            "fixed_start_times_text": ", ".join(policy.fixed_start_times or []),
            "salon_rules": policy.salon_rules,
            "salon_rules_en": policy.salon_rules_en,
            "msg_approved": policy.msg_approved,
            "msg_rejected": policy.msg_rejected,
            "msg_cancelled": policy.msg_cancelled,
            "msg_edited": policy.msg_edited,
            "msg_no_show": policy.msg_no_show,
            "msg_pending": policy.msg_pending,
            "msg_reminder": policy.msg_reminder,
        }
        checkbox_fields = {
            "allow_same_day_booking": policy.allow_same_day_booking,
            "allow_next_day_booking": policy.allow_next_day_booking,
            "allow_last_minute_reopen": policy.allow_last_minute_reopen,
            "auto_approve_bookings": policy.auto_approve_bookings,
            "pending_holds_slot": policy.pending_holds_slot,
            "use_fixed_start_times": policy.use_fixed_start_times,
            "enable_honeypot_protection": policy.enable_honeypot_protection,
            "email_verification_required": policy.email_verification_required,
            "sms_verification_required": policy.sms_verification_required,
            "sms_notifications_enabled": policy.sms_notifications_enabled,
        }
        for field_name, is_enabled in checkbox_fields.items():
            if is_enabled:
                data[field_name] = "on"
        data.update(overrides)
        return data

    def _booking_payload(self, phone="071111222", email="customer@example.com"):
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)
        service = self.salon.services.get(name="Manicure")
        return {
            "service": service.id,
            "date": selected_date.isoformat(),
            "start_time": "08:00",
            "full_name": "New Customer",
            "phone_number": phone,
            "email": email,
            "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
            "rules_accepted": "on",
        }

    def test_booking_page_loads_step_flow(self):
        response = self.client.get("/book/fancy-fingers/request/")

        self.assertContains(response, _("Choose service"))
        self.assertContains(response, "data-slots-url")
        self.assertContains(response, _("Review request"))
        self.assertContains(response, _("Book appointment"))

    def test_booking_form_uses_single_rules_checkbox(self):
        response = self.client.get("/book/fancy-fingers/request/")
        self.assertContains(response, "id=\"bk-rules-consent-check\"")
        self.assertContains(response, "class=\"bk-rules-list\"")
        self.assertContains(response, "class=\"bk-consent-check\"")
        self.assertContains(response, "class=\"bk-rules-legal-line\"")
        self.assertContains(response, reverse("booking:privacy_policy"))
        self.assertEqual(response.content.decode().count("type=\"checkbox\""), 2)
        self.assertNotContains(response, "bk-rule-box")
        with override("mk"):
            mk_response = self.client.get("/book/fancy-fingers/request/")
        self.assertContains(
            mk_response,
            "Ги прочитав, разбирам и се согласувам со сите правила и политики.",
        )
        with override("en"):
            self.assertEqual(
                _("I have read, understood, and agree to all rules and policies."),
                "I have read, understood, and agree to all rules and policies.",
            )

    def test_booking_form_does_not_render_instagram_field(self):
        response = self.client.get("/book/fancy-fingers/request/")
        self.assertNotContains(response, "id_instagram_username")

    def test_disabling_email_verification_in_owner_policy_applies_immediately(self):
        policy = self.salon.booking_policy
        policy.email_verification_required = True
        policy.save(update_fields=["email_verification_required"])

        self.client.login(username="owner", password="password")
        policy_data = self._policy_post_data()
        policy_data.pop("email_verification_required", None)
        response = self.client.post(
            "/owner/dashboard/",
            policy_data,
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        policy.refresh_from_db()
        self.assertFalse(policy.email_verification_required)

        submit = self.client.post("/book/fancy-fingers/request/", self._booking_payload())
        self.assertEqual(submit.status_code, 302)
        booking = Booking.objects.get(customer__phone_number="071111222")
        self.assertEqual(booking.status, Booking.Status.PENDING)

    def test_save_policy_ajax_disables_email_verification_with_fixed_times(self):
        policy = self.salon.booking_policy
        policy.use_fixed_start_times = True
        policy.fixed_start_times = ["08:00", "10:30", "13:00", "15:30"]
        policy.email_verification_required = True
        policy.save()

        self.client.login(username="owner", password="password")
        policy_data = self._policy_post_data()
        policy_data.pop("email_verification_required", None)
        policy_data["fixed_start_times_text"] = ""
        response = self.client.post(
            "/owner/dashboard/",
            policy_data,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(response.json()["ok"])

        policy.refresh_from_db()
        self.assertFalse(policy.email_verification_required)
        self.assertEqual(policy.fixed_start_times, ["08:00", "10:30", "13:00", "15:30"])

    def test_policy_toggle_off_persists_after_dashboard_reload(self):
        policy = self.salon.booking_policy
        policy.email_verification_required = True
        policy.enable_honeypot_protection = True
        policy.save()

        self.client.login(username="owner", password="password")
        policy_data = self._policy_post_data()
        policy_data.pop("email_verification_required", None)
        policy_data.pop("enable_honeypot_protection", None)
        save_response = self.client.post(
            "/owner/dashboard/",
            policy_data,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(save_response.status_code, 200, save_response.content.decode())
        self.assertTrue(save_response.json()["ok"])

        reload_response = self.client.get("/owner/dashboard/")
        self.assertEqual(reload_response.status_code, 200)
        self.assertNotContains(
            reload_response,
            'id="id_email_verification_required" checked',
        )
        self.assertNotContains(
            reload_response,
            'id="id_enable_honeypot_protection" checked',
        )

        policy.refresh_from_db()
        self.assertFalse(policy.email_verification_required)
        self.assertFalse(policy.enable_honeypot_protection)

    def test_policy_save_returns_field_errors_when_fixed_times_missing(self):
        policy = self.salon.booking_policy
        policy.use_fixed_start_times = True
        policy.fixed_start_times = []
        policy.save()

        self.client.login(username="owner", password="password")
        policy_data = self._policy_post_data()
        policy_data["use_fixed_start_times"] = "on"
        policy_data["fixed_start_times_text"] = ""
        response = self.client.post(
            "/owner/dashboard/",
            policy_data,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 400, response.content.decode())
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("fixed_start_times_text", payload.get("form_errors", {}))

    def test_policy_save_works_without_expiration_field_in_post(self):
        """Browser form omitted email_verification_expiration_minutes before template fix."""
        policy = self.salon.booking_policy
        policy.email_verification_required = True
        policy.save()

        self.client.login(username="owner", password="password")
        policy_data = self._policy_post_data()
        policy_data.pop("email_verification_expiration_minutes", None)
        policy_data.pop("email_verification_required", None)
        response = self.client.post(
            "/owner/dashboard/",
            policy_data,
            HTTP_X_REQUESTED_WITH="fetch",
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(response.json()["ok"])

        policy.refresh_from_db()
        self.assertFalse(policy.email_verification_required)
        self.assertEqual(policy.email_verification_expiration_minutes, 60)

    def test_owner_dashboard_loads_for_owner(self):
        self.client.login(username="owner", password="password")

        response = self.client.get("/owner/dashboard/")

        self.assertContains(response, _("Owner panel"))
        self.assertContains(response, _("Pending booking requests"))
        self.assertContains(response, _("Booking policy"))
        self.assertContains(response, _("Current plan"))
        self.assertContains(response, _("Request plan change"))
        self.assertContains(response, 'id="od-plan-change-modal"')
        self.assertContains(
            response,
            _("We’ll use your salon phone and Instagram from your account — no need to enter them again."),
        )

    @override_settings(
        VREMIO_CONTACT_EMAIL="leads@vremio.test",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_owner_plan_change_uses_salon_contact_from_db(self):
        from django.core import mail

        self.salon.plan = Salon.Plan.STARTER
        self.salon.phone_number = "070111222"
        self.salon.instagram_username = "city.studio"
        self.salon.save(update_fields=["plan", "phone_number", "instagram_username"])
        self.client.login(username="owner", password="password")

        response = self.client.post(
            reverse("booking:owner_request_plan_change"),
            {"plan": "pro"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("Pro", mail.outbox[0].subject)
        self.assertIn("070111222", body)
        self.assertIn("@city.studio", body)
        self.assertIn("owner_dashboard", body)
        self.assertIn("Starter", body)

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

    def test_booking_request_rejects_common_email_typo(self):
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
                "full_name": "Typo Email",
                "phone_number": "079888777",
                "instagram_username": "typo_email",
                "email": "customer@gmai.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "gmail.com")
        self.assertFalse(Booking.objects.filter(customer__phone_number="079888777").exists())

    def test_booking_request_rejects_invalid_phone(self):
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
                "full_name": "Bad Phone",
                "phone_number": "123456",
                "email": "badphone@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.filter(customer__full_name="Bad Phone").exists())

    def test_booking_request_normalizes_international_phone(self):
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
                "full_name": "Intl Phone",
                "phone_number": "+389 70 555 444",
                "email": "intl@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Booking.objects.filter(customer__phone_number="070555444").exists())

    def test_salon_page_shows_updated_hero(self):
        response = self.client.get("/book/fancy-fingers/")
        self.assertContains(response, _("Care, style, and an appointment that suits you."))

    def test_pro_salon_page_shows_location_maps_link(self):
        self.salon.address = "Ul. Partizanski Odredi 1"
        self.salon.city = "Skopje"
        self.salon.save(update_fields=["address", "city"])
        response = self.client.get("/book/fancy-fingers/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "google.com/maps/search")
        self.assertContains(response, _("Find us"))
        self.assertContains(response, "bi-geo-alt")

    def test_pro_salon_page_uses_pasted_maps_url(self):
        self.salon.address = ""
        self.salon.city = ""
        self.salon.maps_url = "https://maps.app.goo.gl/exampleSalonPin"
        self.salon.save(update_fields=["address", "city", "maps_url"])
        response = self.client.get("/book/fancy-fingers/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://maps.app.goo.gl/exampleSalonPin")
        self.assertContains(response, _("Find us"))
        self.assertContains(response, "sp-hero-social")

    def test_pro_salon_page_hides_location_without_address(self):
        self.salon.address = ""
        self.salon.city = ""
        self.salon.maps_url = ""
        self.salon.save(update_fields=["address", "city", "maps_url"])
        response = self.client.get("/book/fancy-fingers/")
        self.assertNotContains(response, _("Find us"))
        self.assertNotContains(response, "sp-hero-social")

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

    def test_booking_with_price_item_uses_its_duration(self):
        """A sub-service duration should shorten the reserved appointment time."""
        selected_date = timezone.localdate() + timedelta(days=20)
        if selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            selected_date += timedelta(days=1)

        service = self.salon.services.get(name="Manicure")
        express = ServicePriceItem.objects.create(
            service=service,
            name="Express Manicure",
            price_display="500",
            duration_minutes=45,
            sort_order=1,
        )
        response = self.client.post(
            "/book/fancy-fingers/request/",
            {
                "service": service.id,
                "selected_price_item_id": express.id,
                "date": selected_date.isoformat(),
                "start_time": "08:00",
                "full_name": "Express Customer",
                "phone_number": "072777888",
                "email": "express@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "rules_accepted": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        booking = Booking.objects.get(customer__phone_number="072777888")
        self.assertEqual(booking.total_duration_minutes, 45)
        line = booking.booking_services.first()
        self.assertEqual(line.duration_minutes_snapshot, 45)
        self.assertEqual(
            (booking.end_at - booking.start_at).total_seconds() / 60, 45
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

    def _aware(self, hour, minute):
        return timezone.make_aware(
            datetime.combine(self.selected_date, time(hour, minute)),
            timezone.get_current_timezone(),
        )

    def _book(self, start_hour, start_minute, end_hour, end_minute, minutes):
        return Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=self._aware(start_hour, start_minute),
            end_at=self._aware(end_hour, end_minute),
            total_duration_minutes=minutes,
        )

    def _slot_values(self, duration_minutes=None):
        slots = get_available_slots(
            self.salon,
            self.service,
            self.selected_date,
            now=self.now,
            duration_override_minutes=duration_minutes,
        )
        return {slot["value"] for slot in slots}

    def test_fixed_start_times_return_only_configured_starts(self):
        values = self._slot_values()
        self.assertEqual(values, {"08:00", "10:30", "13:00", "15:30"})
        self.assertNotIn("08:30", values)
        self.assertNotIn("09:00", values)
        self.assertEqual(self._slot_values(duration_minutes=60), values)

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
        self.assertNotIn("10:00", values)
        self.assertIn("10:30", values)
        self.assertIn("13:00", values)

    def test_visit_ending_before_next_anchor_keeps_anchor(self):
        self._book(8, 0, 10, 20, 140)
        values = self._slot_values()
        self.assertNotIn("08:00", values)
        self.assertNotIn("10:20", values)
        self.assertNotIn("10:50", values)
        self.assertIn("10:30", values)

    def test_visit_ending_on_next_anchor_opens_end_plus_gap(self):
        self._book(8, 0, 10, 30, 150)
        values = self._slot_values(duration_minutes=60)
        self.assertNotIn("08:00", values)
        self.assertNotIn("10:30", values)
        self.assertIn("11:00", values)
        self.assertIn("13:30", values)
        self.assertIn("16:00", values)
        self.assertNotIn("13:00", values)
        self.assertNotIn("15:30", values)

    def test_short_visit_opens_leftover_before_next_anchor(self):
        self._book(10, 30, 11, 30, 60)
        values = self._slot_values(duration_minutes=60)
        self.assertIn("08:00", values)
        self.assertNotIn("10:30", values)
        self.assertIn("12:00", values)
        self.assertIn("14:30", values)
        self.assertIn("17:00", values)
        self.assertNotIn("13:00", values)
        self.assertNotIn("15:30", values)

    def test_ninety_minute_visit_opens_twelve_thirty(self):
        self._book(10, 30, 12, 0, 90)
        values = self._slot_values(duration_minutes=60)
        self.assertIn("12:30", values)
        self.assertIn("15:00", values)
        self.assertNotIn("13:00", values)
        self.assertNotIn("12:00", values)
        self.assertIn("08:00", values)

    def test_visit_ending_close_to_next_anchor_keeps_anchor(self):
        self._book(10, 30, 12, 40, 130)
        values = self._slot_values(duration_minutes=60)
        self.assertNotIn("12:40", values)
        self.assertNotIn("13:10", values)
        self.assertIn("13:00", values)

    def test_leftover_does_not_butt_against_later_anchor_booking(self):
        self._book(10, 30, 11, 30, 60)
        self._book(13, 0, 15, 0, 120)
        values = self._slot_values(duration_minutes=60)
        self.assertNotIn("12:00", values)
        self.assertNotIn("13:00", values)
        self.assertIn("08:00", values)
        self.assertIn("15:30", values)

    def test_short_leftover_can_fit_before_later_anchor_booking(self):
        self._book(10, 30, 11, 30, 60)
        self._book(13, 0, 15, 0, 120)
        values = self._slot_values(duration_minutes=30)
        self.assertIn("12:00", values)
        self.assertNotIn("13:00", values)

    def test_afternoon_one_fifty_fits_closing(self):
        values = self._slot_values(duration_minutes=150)
        self.assertIn("15:30", values)
        self.assertIn("08:00", values)

    def test_rebased_last_hour_only_fits_short_service(self):
        self._book(10, 30, 11, 30, 60)
        hour = self._slot_values(duration_minutes=60)
        self.assertIn("17:00", hour)
        full = self._slot_values(duration_minutes=150)
        self.assertIn("12:00", full)
        self.assertIn("14:30", full)
        self.assertNotIn("17:00", full)
        self.assertNotIn("13:00", full)
        self.assertNotIn("15:30", full)

    def test_max_duration_from_noon_opens_three_pm(self):
        self._book(8, 0, 10, 0, 120)
        self._book(10, 30, 11, 30, 60)
        self._book(12, 0, 14, 30, 150)
        values = self._slot_values(duration_minutes=150)
        self.assertEqual(values, {"15:00"})
        self.assertNotIn("17:00", values)
        self.assertNotIn("15:30", values)

    def test_thirty_minute_service_keeps_empty_day_anchors(self):
        values = self._slot_values(duration_minutes=30)
        self.assertEqual(values, {"08:00", "10:30", "13:00", "15:30"})

    def test_thirty_minute_service_fits_rebased_last_hour(self):
        self._book(10, 30, 11, 30, 60)
        values = self._slot_values(duration_minutes=30)
        self.assertIn("08:00", values)
        self.assertIn("12:00", values)
        self.assertIn("14:30", values)
        self.assertIn("17:00", values)
        self.assertNotIn("13:00", values)
        self.assertNotIn("15:30", values)

    def test_thirty_minute_booking_at_noon_keeps_thirty_min_gap(self):
        self._book(10, 30, 11, 30, 60)
        self._book(12, 0, 12, 30, 30)
        values = self._slot_values(duration_minutes=30)
        self.assertIn("13:00", values)
        self.assertNotIn("12:00", values)
        self.assertIn("08:00", values)

    def test_leftover_start_helper_keeps_anchor_when_end_is_before_it(self):
        gap = timedelta(minutes=30)
        anchors = [
            self._aware(8, 0),
            self._aware(10, 30),
            self._aware(13, 0),
            self._aware(15, 30),
        ]
        self.assertIsNone(
            leftover_start_after_visit(self._aware(8, 0), self._aware(10, 20), anchors, gap)
        )
        self.assertEqual(
            leftover_start_after_visit(self._aware(8, 0), self._aware(10, 30), anchors, gap),
            self._aware(11, 0),
        )
        self.assertEqual(
            leftover_start_after_visit(self._aware(10, 30), self._aware(11, 30), anchors, gap),
            self._aware(12, 0),
        )
        self.assertIsNone(
            leftover_start_after_visit(self._aware(10, 30), self._aware(12, 40), anchors, gap)
        )

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

    def test_policy_form_checkbox_fields_toggle_on_off(self):
        base_data = {
            "minimum_notice_days": 14,
            "maximum_booking_window_days": 60,
            "late_arrival_limit_minutes": 15,
            "reminder_hours_before": 24,
            "max_appointments_per_day": 4,
            "slot_interval_minutes": 30,
            "buffer_minutes_between_bookings": 0,
            "service_gap_minutes": 30,
            "customer_cancellation_notice_hours": 24,
            "max_pending_bookings_per_customer": 1,
            "max_active_future_bookings_per_customer": 2,
            "booking_rate_limit_per_ip_per_hour": 5,
            "booking_rate_limit_per_email_per_day": 3,
            "booking_rate_limit_per_phone_per_day": 3,
            "max_reference_photo_size_mb": 5,
            "email_verification_expiration_minutes": 60,
            "use_fixed_start_times": "on",
            "fixed_start_times_text": "08:00, 10:30, 13:00, 15:30",
            "salon_rules": "Rule",
            "salon_rules_en": "Rule EN",
            "msg_approved": "ok",
            "msg_rejected": "no",
            "msg_cancelled": "cancel",
            "msg_edited": "edit",
            "msg_no_show": "noshow",
            "msg_pending": "pending",
            "msg_reminder": "reminder",
        }
        checkbox_fields = [
            "allow_same_day_booking",
            "allow_next_day_booking",
            "allow_last_minute_reopen",
            "auto_approve_bookings",
            "pending_holds_slot",
            "use_fixed_start_times",
            "enable_honeypot_protection",
            "email_verification_required",
        ]
        for field_name in checkbox_fields:
            enabled_data = dict(base_data)
            enabled_data[field_name] = "on"
            enabled_form = BookingPolicyForm(data=enabled_data, instance=self.policy)
            self.assertTrue(enabled_form.is_valid(), enabled_form.errors)
            enabled_policy = enabled_form.save()
            self.assertTrue(getattr(enabled_policy, field_name))

            disabled_data = dict(base_data)
            disabled_data.pop(field_name, None)
            disabled_form = BookingPolicyForm(data=disabled_data, instance=self.policy)
            self.assertTrue(disabled_form.is_valid(), disabled_form.errors)
            disabled_policy = disabled_form.save()
            self.assertFalse(getattr(disabled_policy, field_name))


class SalonPublicHoursDisplayTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="display_owner",
            password="password",
        )
        self.salon = Salon.objects.create(
            owner=user,
            name="Display Salon",
            slug="display-salon",
        )
        ensure_default_working_hours(self.salon)
        self.working_hours = list(self.salon.working_hours.order_by("weekday"))
        for row in self.working_hours:
            if row.is_working_day:
                row.start_time = time(8, 0)
                row.end_time = time(18, 0)
                row.save(update_fields=["start_time", "end_time"])
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
            use_fixed_start_times=True,
            fixed_start_times=["08:00", "10:30", "13:00", "15:30"],
            email_verification_required=False,
        )
        self.selected_date = timezone.localdate() + timedelta(days=7)
        while self.selected_date.weekday() == WorkingHours.Weekday.SUNDAY:
            self.selected_date += timedelta(days=1)

    def test_hours_rows_use_working_end_without_override(self):
        rows = get_salon_page_hours_rows(self.salon, self.working_hours)
        monday = next(item for item in rows if item["row"].weekday == WorkingHours.Weekday.MONDAY)
        self.assertEqual(monday["display_start_time"], time(8, 0))
        self.assertEqual(monday["display_end_time"], time(18, 0))

    def test_hours_rows_use_public_display_end_when_set(self):
        self.salon.public_hours_end_display = time(16, 0)
        self.salon.save(update_fields=["public_hours_end_display"])

        rows = get_salon_page_hours_rows(self.salon, self.working_hours)
        monday = next(item for item in rows if item["row"].weekday == WorkingHours.Weekday.MONDAY)
        sunday = next(item for item in rows if item["row"].weekday == WorkingHours.Weekday.SUNDAY)

        self.assertEqual(monday["display_end_time"], time(16, 0))
        self.assertFalse(sunday["row"].is_working_day)

    def test_salon_page_shows_public_display_end_not_booking_end(self):
        self.salon.public_hours_end_display = time(16, 0)
        self.salon.save(update_fields=["public_hours_end_display"])

        response = self.client.get(reverse("booking:salon_page", args=[self.salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "08:00 – 16:00")
        self.assertNotContains(response, "08:00 – 18:00")

    def test_booking_slots_ignore_public_display_end(self):
        self.salon.public_hours_end_display = time(16, 0)
        self.salon.save(update_fields=["public_hours_end_display"])

        slots = get_available_slots(self.salon, self.service, self.selected_date)
        values = {slot["value"] for slot in slots}
        self.assertIn("15:30", values)


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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        OWNER_NOTIFICATION_EMAIL="",
    )
    @patch("booking.views.defer_after_commit", side_effect=_run_deferred_immediately)
    def test_new_booking_sends_customer_request_email(self, _defer):
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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        OWNER_NOTIFICATION_EMAIL="",
    )
    @patch("booking.views.defer_after_commit", side_effect=_run_deferred_immediately)
    def test_new_booking_sends_owner_email_when_configured(self, _defer):
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
    @patch("booking.views.defer_after_commit", side_effect=_run_deferred_immediately)
    def test_owner_notification_prefers_env_email(self, _defer):
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
        body = mail.outbox[0].body
        self.assertIn(_("You can view or cancel your appointment here:"), body)
        self.assertIn(_("Add to Google Calendar"), body)
        self.assertIn(_("Apple / Samsung / other"), body)
        # Plain text keeps labels only; clickable hrefs live in the HTML part.
        self.assertNotIn("calendar.google.com/calendar/render", body)
        html_part = mail.outbox[0].alternatives[0][0]
        google_label = _("Add to Google Calendar")
        apple_label = _("Apple / Samsung / other")
        self.assertIn("calendar.google.com/calendar/render", html_part)
        self.assertIn(
            reverse("booking:manage_booking_ics", args=[self.booking_a.manage_token]),
            html_part,
        )
        self.assertIn('text-decoration: underline', html_part)
        self.assertIn(f">{google_label}</a>", html_part)
        self.assertIn(f">{apple_label}</a>", html_part)
        self.assertLess(html_part.find(google_label), html_part.find(apple_label))
        self.assertLess(
            body.find(_("You can view or cancel your appointment here:")),
            body.find(google_label),
        )

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

    def test_manage_page_shows_calendar_only_when_approved(self):
        self.booking_a.status = Booking.Status.PENDING
        self.booking_a.save(update_fields=["status"])
        pending = self.client.get(
            reverse("booking:manage_booking", args=[self.booking_a.manage_token])
        )
        self.assertNotContains(pending, _("Add to calendar"))

        self.booking_a.status = Booking.Status.APPROVED
        self.booking_a.save(update_fields=["status"])
        approved = self.client.get(
            reverse("booking:manage_booking", args=[self.booking_a.manage_token])
        )
        self.assertContains(approved, _("Add to calendar"))
        self.assertContains(approved, "calendar.google.com/calendar/render")
        self.assertContains(
            approved,
            reverse("booking:manage_booking_ics", args=[self.booking_a.manage_token]),
        )

    def test_manage_ics_only_for_approved(self):
        self.booking_a.status = Booking.Status.PENDING
        self.booking_a.save(update_fields=["status"])
        pending = self.client.get(
            reverse("booking:manage_booking_ics", args=[self.booking_a.manage_token])
        )
        self.assertEqual(pending.status_code, 404)

        self.booking_a.status = Booking.Status.APPROVED
        self.booking_a.save(update_fields=["status"])
        approved = self.client.get(
            reverse("booking:manage_booking_ics", args=[self.booking_a.manage_token])
        )
        self.assertEqual(approved.status_code, 200)
        self.assertIn("text/calendar", approved["Content-Type"])
        self.assertIn(b"BEGIN:VEVENT", approved.content)

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

    def test_second_pending_blocked_for_same_email_different_phone_allowed(self):
        self._create_booking("070111222", "shared@example.com")
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070999888", "shared@example.com", start_time="12:00"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Booking.objects.filter(
                customer__phone_number="070999888",
                status=Booking.Status.PENDING,
            ).count(),
            1,
        )

    def test_second_pending_blocked_for_same_phone_different_format(self):
        self._create_booking("070111222", "first@example.com")
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("+389 70 111 222", "other@example.com", start_time="12:00"),
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

    def test_expired_unverified_does_not_block_new_booking(self):
        self.policy.email_verification_required = True
        self.policy.save()
        self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111333", "verify@example.com"),
        )
        booking = Booking.objects.get(customer__phone_number="070111333")
        booking.verification_expires_at = timezone.now() - timedelta(minutes=5)
        booking.save(update_fields=["verification_expires_at"])
        response = self.client.post(
            "/book/salon-a/request/",
            self._post_data("070111333", "verify@example.com", start_time="12:00"),
        )
        self.assertEqual(response.status_code, 302)

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

    def test_rate_limit_fails_open_when_cache_unavailable(self):
        self.policy.booking_rate_limit_per_ip_per_hour = 1
        self.policy.save()
        with patch("booking.anti_abuse.cache.get", side_effect=OSError("redis down")):
            response = self.client.post(
                "/book/salon-a/request/",
                self._post_data("070111001", "one@example.com"),
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)

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
                "same_client_confirmed": "1",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "активен")
        customer = Customer.objects.get(salon=self.salon, phone_number="070111222")
        self.assertEqual(customer.full_name, "Existing")

    def test_owner_manual_booking_asks_same_client_when_phone_name_differ(self):
        self._create_booking("070111222", "owner@example.com")
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        before = Booking.objects.count()
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Simona Maneva",
                "phone_number": "070111222",
                "instagram_username": "simona",
                "email": "simona@example.com",
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
        self.assertEqual(Booking.objects.count(), before)
        customer = Customer.objects.get(salon=self.salon, phone_number="070111222")
        self.assertEqual(customer.full_name, "Existing")
        self.assertContains(response, "Existing")

    def test_owner_manual_booking_same_name_reuses_customer_without_confirm(self):
        self._create_booking("070111222", "owner@example.com")
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Existing",
                "phone_number": "070111222",
                "instagram_username": "existing",
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
        self.assertEqual(
            Booking.objects.filter(customer__phone_number="070111222").count(),
            2,
        )

    def test_owner_manual_booking_allows_empty_phone(self):
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Walk In Client",
                "phone_number": "",
                "instagram_username": "",
                "email": "",
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
        booking = Booking.objects.get(customer__full_name="Walk In Client")
        self.assertEqual(booking.customer.phone_number, "")
        # Multiple no-phone customers are allowed for owner manual bookings.
        response2 = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Another Walk In",
                "phone_number": "",
                "instagram_username": "",
                "email": "",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.service.id],
                "date": selected.isoformat(),
                "start_time": "16:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(
            Customer.objects.filter(salon=self.salon, phone_number="").count(),
            2,
        )
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


class OwnerLoginThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(username="owner_login", password="correct-pass")
        self.url = reverse("booking:owner_login")

    def test_successful_login_clears_failures(self):
        from .login_throttle import record_login_failure

        record_login_failure("127.0.0.1", "owner_login")
        response = self.client.post(
            self.url,
            {"username": "owner_login", "password": "correct-pass"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/owner/dashboard/"))

    def test_locks_after_too_many_failures(self):
        from .login_throttle import LOGIN_MAX_ATTEMPTS

        for _attempt in range(LOGIN_MAX_ATTEMPTS):
            response = self.client.post(
                self.url,
                {"username": "owner_login", "password": "wrong"},
            )
            self.assertEqual(response.status_code, 200)

        response = self.client.post(
            self.url,
            {"username": "owner_login", "password": "correct-pass"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            _(
                "Too many failed sign-in attempts. Please wait a few minutes and try again."
            ),
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_device_cookie_sets_secure_when_session_secure(self):
        salon = Salon.objects.create(
            owner=self.user,
            name="Cookie Salon",
            slug="cookie-salon",
            is_active=True,
        )
        BookingPolicy.objects.create(
            salon=salon,
            minimum_notice_days=0,
            email_verification_required=False,
        )
        with override_settings(SESSION_COOKIE_SECURE=True):
            response = self.client.get(reverse("booking:book_salon", args=[salon.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("salon_booking_device", response.cookies)
        self.assertTrue(response.cookies["salon_booking_device"]["secure"])


class ContentSecurityPolicyTests(TestCase):
    def test_csp_header_present_when_enabled(self):
        with override_settings(CONTENT_SECURITY_POLICY_ENABLED=True):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        policy = response.get("Content-Security-Policy", "")
        self.assertIn("default-src 'self'", policy)
        self.assertIn("script-src 'self' 'unsafe-inline'", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        self.assertIn("https://fonts.googleapis.com", policy)
        self.assertIn("https://cdn.jsdelivr.net", policy)
        self.assertIn("camera=()", response["Permissions-Policy"])

    def test_csp_header_absent_when_disabled(self):
        with override_settings(CONTENT_SECURITY_POLICY_ENABLED=False):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response)
        self.assertNotIn("Permissions-Policy", response)

    def test_csp_skipped_on_admin(self):
        with override_settings(CONTENT_SECURITY_POLICY_ENABLED=True):
            response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Security-Policy", response)


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

    def test_line_items_duration_uses_price_item_duration(self):
        """A sub-service with its own duration overrides the parent service."""
        express = ServicePriceItem.objects.create(
            service=self.pedicure,
            name="Express pedicure",
            price_display="600",
            duration_minutes=60,
        )
        total = calculate_line_items_duration_minutes(
            [{"service": self.pedicure, "price_item": express}],
            self.salon,
        )
        self.assertEqual(total, 60)

    def test_line_items_duration_falls_back_to_service(self):
        """A sub-service with no duration (0) inherits the parent duration."""
        classic = ServicePriceItem.objects.create(
            service=self.pedicure,
            name="Classic pedicure",
            price_display="800",
            duration_minutes=0,
        )
        total = calculate_line_items_duration_minutes(
            [{"service": self.pedicure, "price_item": classic}],
            self.salon,
        )
        self.assertEqual(total, 120)

    def test_line_items_duration_mixes_override_and_gap(self):
        """Overridden sub-service + full service, plus one inter-service gap."""
        express = ServicePriceItem.objects.create(
            service=self.pedicure,
            name="Express pedicure",
            price_display="600",
            duration_minutes=60,
        )
        total = calculate_line_items_duration_minutes(
            [
                {"service": self.pedicure, "price_item": express},
                {"service": self.manicure, "price_item": None},
            ],
            self.salon,
        )
        # 60 (express) + 120 (manicure) + 30 (gap)
        self.assertEqual(total, 210)

    def test_line_items_duration_base_plus_addons_no_inner_gap(self):
        base = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Gel polish",
            price_display="600",
            duration_minutes=120,
            is_addon=False,
        )
        art = ServicePriceItem.objects.create(
            service=self.manicure,
            name="French",
            price_display="+100",
            duration_minutes=20,
            is_addon=True,
        )
        total = calculate_line_items_duration_minutes(
            [{"service": self.manicure, "price_item": base, "addons": [art]}],
            self.salon,
        )
        self.assertEqual(total, 140)

    def test_addon_duration_zero_does_not_use_parent_service(self):
        base = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Gel polish",
            price_display="600",
            duration_minutes=120,
        )
        art = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Simple art",
            price_display="100",
            duration_minutes=0,
            is_addon=True,
        )
        total = calculate_line_items_duration_minutes(
            [{"service": self.manicure, "price_item": base, "addons": [art]}],
            self.salon,
        )
        self.assertEqual(total, 120)

    def test_zero_minute_addon_snapshot_not_inflated_to_parent(self):
        """Regression: addon duration 0 must stay 0 on BookingService (not 120)."""
        base = ServicePriceItem.objects.create(
            service=self.manicure,
            name="КОРЕКЦИЈА",
            price_display="900",
            duration_minutes=120,
        )
        art = ServicePriceItem.objects.create(
            service=self.manicure,
            name="ФРЕНЧ/ОМБРЕ",
            price_display="+200",
            duration_minutes=0,
            is_addon=True,
        )
        selected = self._future_date()
        from django.test import RequestFactory

        request = RequestFactory().post("/book/")
        form = BookingRequestForm(
            data={
                "service_ids": str(self.manicure.id),
                "service_price_items": json.dumps(
                    {str(self.manicure.id): {"base": base.id, "addons": [art.id]}}
                ),
                "date": selected.isoformat(),
                "start_time": "08:00",
                "full_name": "Evdokija Test",
                "phone_number": "070123456",
                "email": "evdokija@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.PHONE,
                "rules_accepted": True,
            },
            salon=self.salon,
            request=request,
        )
        self.assertTrue(form.is_valid(), form.errors)
        booking = form.save()
        rows = list(booking.booking_services.order_by("sort_order"))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].duration_minutes_snapshot, 120)
        self.assertFalse(rows[0].is_addon_snapshot)
        self.assertEqual(rows[1].duration_minutes_snapshot, 0)
        self.assertTrue(rows[1].is_addon_snapshot)
        self.assertEqual(booking.total_duration_minutes, 120)
        self.assertEqual(
            (booking.end_at - booking.start_at).total_seconds(),
            120 * 60,
        )
        schedule = build_service_schedule(
            booking.start_at, rows, self.salon
        )
        self.assertEqual(schedule[0]["start_time"], "08:00")
        self.assertEqual(schedule[0]["end_time"], "10:00")
        # Zero-minute add-on shares the base window — not a second 2h slot.
        self.assertEqual(schedule[1]["start_time"], "08:00")
        self.assertEqual(schedule[1]["end_time"], "10:00")
        self.assertEqual(schedule[1]["duration_minutes"], 0)

    def test_booking_form_accepts_base_and_addon_map(self):
        base = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Gel polish",
            price_display="600",
            duration_minutes=90,
        )
        art = ServicePriceItem.objects.create(
            service=self.manicure,
            name="French",
            price_display="+100",
            duration_minutes=15,
            is_addon=True,
        )
        selected = self._future_date()
        from django.test import RequestFactory

        request = RequestFactory().post("/book/")
        form = BookingRequestForm(
            data={
                "service_ids": str(self.manicure.id),
                "service_price_items": json.dumps(
                    {str(self.manicure.id): {"base": base.id, "addons": [art.id]}}
                ),
                "date": selected.isoformat(),
                "start_time": "08:00",
                "full_name": "Ana Test",
                "phone_number": "070123456",
                "email": "ana@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.PHONE,
                "rules_accepted": True,
            },
            salon=self.salon,
            request=request,
        )
        self.assertTrue(form.is_valid(), form.errors)
        booking = form.save()
        names = list(
            booking.booking_services.order_by("sort_order").values_list(
                "service_name_snapshot", flat=True
            )
        )
        self.assertEqual(names, ["Gel polish", "French"])
        self.assertEqual(booking.total_duration_minutes, 105)
        snaps = list(
            booking.booking_services.order_by("sort_order").values_list(
                "duration_minutes_snapshot", "is_addon_snapshot"
            )
        )
        self.assertEqual(snaps, [(90, False), (15, True)])

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

    def test_owner_edit_keeps_express_duration_when_services_unchanged(self):
        """Saving an email/contact tweak must not rewrite an express 60-min line as 120 min."""
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Express Client",
            phone_number="070888999",
            email="wrong@example.com",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            start_at=start,
            end_at=start + timedelta(minutes=60),
            total_duration_minutes=60,
            source=Booking.Source.ONLINE,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Express manicure",
            duration_minutes_snapshot=60,
            price_snapshot=500,
            sort_order=0,
        )
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "booking_id": str(booking.id),
                "full_name": "Express Client",
                "phone_number": "070888999",
                "email": "fixed@example.com",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.manicure.id],
                "date": selected.isoformat(),
                "start_time": "08:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.ONLINE,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        line = booking.booking_services.get()
        self.assertEqual(booking.customer.email, "fixed@example.com")
        self.assertEqual(booking.total_duration_minutes, 60)
        self.assertEqual(line.duration_minutes_snapshot, 60)
        self.assertEqual(line.service_name_snapshot, "Express manicure")
        self.assertEqual((booking.end_at - booking.start_at).total_seconds() / 60, 60)

    def test_owner_manual_booking_uses_express_price_item(self):
        express = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Express manicure",
            price_display="500",
            duration_minutes=60,
        )
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "full_name": "Express New",
                "phone_number": "070111222",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.manicure.id],
                "service_price_items": json.dumps(
                    {str(self.manicure.id): {"base": express.id, "addons": []}}
                ),
                "date": selected.isoformat(),
                "start_time": "08:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get(customer__phone_number="070111222")
        line = booking.booking_services.get()
        self.assertEqual(booking.total_duration_minutes, 60)
        self.assertEqual(line.service_name_snapshot, "Express manicure")
        self.assertEqual(line.duration_minutes_snapshot, 60)
        self.assertEqual((booking.end_at - booking.start_at).total_seconds() / 60, 60)

    def test_owner_edit_saves_express_from_price_items(self):
        """Owner picking Express in the expanded card must rewrite the 120-min parent line."""
        express = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Express manicure",
            price_display="500",
            duration_minutes=60,
        )
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Needs Express",
            phone_number="070333444",
        )
        start = timezone.make_aware(
            datetime.combine(selected, time(8, 0)),
            timezone.get_current_timezone(),
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.APPROVED,
            start_at=start,
            end_at=start + timedelta(minutes=120),
            total_duration_minutes=120,
            source=Booking.Source.OWNER_MANUAL,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Manicure",
            duration_minutes_snapshot=120,
            price_snapshot=600,
            sort_order=0,
        )
        response = self.client.post(
            "/owner/dashboard/",
            {
                "action": "save_booking",
                "booking_id": str(booking.id),
                "full_name": "Needs Express",
                "phone_number": "070333444",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.manicure.id],
                "service_price_items": json.dumps(
                    {str(self.manicure.id): {"base": express.id, "addons": []}}
                ),
                "date": selected.isoformat(),
                "start_time": "08:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        line = booking.booking_services.get()
        self.assertEqual(booking.total_duration_minutes, 60)
        self.assertEqual(line.service_name_snapshot, "Express manicure")
        self.assertEqual(line.duration_minutes_snapshot, 60)

    def test_owner_dashboard_booking_modal_lists_price_items(self):
        ServicePriceItem.objects.create(
            service=self.manicure,
            name="Express manicure",
            price_display="500",
            duration_minutes=60,
        )
        ServicePriceItem.objects.create(
            service=self.manicure,
            name="French",
            price_display="+100",
            duration_minutes=15,
            is_addon=True,
        )
        self.client.login(username="owner", password="pass")
        response = self.client.get("/owner/dashboard/")
        self.assertContains(response, "od-bk-svc-card--expandable")
        self.assertContains(response, "Express manicure")
        self.assertContains(response, "French")
        self.assertContains(response, "od-booking-price-items")

    def test_owner_slots_api_uses_price_item_duration(self):
        express = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Express manicure",
            price_display="500",
            duration_minutes=60,
        )
        self.client.login(username="owner", password="pass")
        selected = self._future_date()
        response = self.client.get(
            reverse("booking:owner_available_slots"),
            {
                "services": str(self.manicure.id),
                "date": selected.isoformat(),
                "price_items": json.dumps(
                    {str(self.manicure.id): {"base": express.id, "addons": []}}
                ),
            },
        )
        values = {slot["value"] for slot in response.json()["slots"]}
        self.assertIn("17:00", values)

    def test_owner_booking_detail_returns_price_items_map(self):
        express = ServicePriceItem.objects.create(
            service=self.manicure,
            name="Express manicure",
            price_display="500",
            duration_minutes=60,
        )
        art = ServicePriceItem.objects.create(
            service=self.manicure,
            name="French",
            price_display="+100",
            duration_minutes=15,
            is_addon=True,
        )
        selected = self._future_date()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Detail Express",
            phone_number="070555666",
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
            end_at=start + timedelta(minutes=75),
            total_duration_minutes=75,
            rules_accepted=True,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="Express manicure",
            duration_minutes_snapshot=60,
            sort_order=0,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.manicure,
            service_name_snapshot="French",
            duration_minutes_snapshot=15,
            is_addon_snapshot=True,
            sort_order=1,
        )
        self.client.login(username="owner", password="pass")
        response = self.client.get(
            reverse("booking:owner_booking_detail", args=[booking.pk])
        )
        data = response.json()
        self.assertEqual(
            data["service_price_items"][str(self.manicure.id)],
            {"base": express.id, "addons": [art.id]},
        )

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
    def test_resend_verification_email(self):
        from django.core import mail

        self.client.post("/book/salon-v/request/", self._booking_post_data())
        mail.outbox.clear()
        response = self.client.post(reverse("booking:resend_booking_verification_email"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify@example.com", mail.outbox[0].to)

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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        OWNER_NOTIFICATION_EMAIL="",
    )
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


class BookingReminderTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner_reminder",
            email="owner_reminder@example.com",
            password="pass",
        )
        self.salon = Salon.objects.create(owner=self.owner, name="Reminder Salon", slug="reminder-salon")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            reminder_hours_before=24,
        )
        self.customer = Customer.objects.create(
            salon=self.salon,
            full_name="Reminder Client",
            phone_number="070888777",
            email="reminder@example.com",
        )
        self.service = Service.objects.create(
            salon=self.salon,
            name="Manicure",
            duration_minutes=120,
            base_price=600,
        )

    def _make_booking(self, *, hours_until_start):
        start = timezone.now() + timedelta(hours=hours_until_start)
        booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=Booking.Status.APPROVED,
            source=Booking.Source.OWNER_MANUAL,
            start_at=start,
            end_at=start + timedelta(hours=2),
            total_duration_minutes=120,
        )
        BookingService.objects.create(
            booking=booking,
            service=self.service,
            service_name_snapshot=self.service.name,
            duration_minutes_snapshot=self.service.duration_minutes,
            price_snapshot=self.service.base_price,
        )
        return booking

    def test_reminder_not_due_yet(self):
        self._make_booking(hours_until_start=30)
        self.assertEqual(send_due_booking_reminders(dry_run=True), 0)

    def test_reminder_due_within_policy_window(self):
        self._make_booking(hours_until_start=20)
        self.assertEqual(send_due_booking_reminders(dry_run=True), 1)

    @patch("booking.services.send_booking_notification", return_value=(True, "sent"))
    def test_reminder_sent_marks_booking(self, mock_send):
        booking = self._make_booking(hours_until_start=20)
        count = send_due_booking_reminders()
        self.assertEqual(count, 1)
        mock_send.assert_called_once_with(booking, "reminder")
        booking.refresh_from_db()
        self.assertIsNotNone(booking.reminder_sent_at)

    @patch("booking.services.send_booking_notification", return_value=(True, "sent"))
    def test_reminder_not_sent_twice(self, mock_send):
        booking = self._make_booking(hours_until_start=20)
        send_due_booking_reminders()
        send_due_booking_reminders()
        mock_send.assert_called_once()

    def test_reminder_disabled_when_hours_zero(self):
        self.policy.reminder_hours_before = 0
        self.policy.save(update_fields=["reminder_hours_before"])
        self._make_booking(hours_until_start=20)
        self.assertEqual(send_due_booking_reminders(dry_run=True), 0)

    @patch("booking.services.send_booking_notification", return_value=(False, "no_email"))
    def test_reminder_skipped_without_contact_channel(self, mock_send):
        booking = self._make_booking(hours_until_start=20)
        booking.customer.email = ""
        booking.customer.save(update_fields=["email"])
        count = send_due_booking_reminders()
        self.assertEqual(count, 1)
        booking.refresh_from_db()
        self.assertIsNotNone(booking.reminder_sent_at)

    @patch("booking.services.send_booking_notification", return_value=(True, "sent"))
    def test_management_command_sends_reminders(self, mock_send):
        self._make_booking(hours_until_start=20)
        call_command("send_booking_reminders")
        mock_send.assert_called_once()


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

    def test_public_ip_blocks_even_with_different_phone(self):
        CustomerBlocklist.objects.create(
            salon=self.salon,
            phone_number="070000002",
            last_known_ip="8.8.8.8",
            reason_code=CustomerBlocklist.ReasonCode.OTHER,
            is_active=True,
            blocked_at=timezone.now(),
        )
        from .anti_abuse import is_customer_blocked

        self.assertTrue(
            is_customer_blocked(
                self.salon,
                phone="070222888",
                ip="8.8.8.8",
            )
        )

    def test_private_ip_is_not_used_for_block_matching(self):
        CustomerBlocklist.objects.create(
            salon=self.salon,
            phone_number="070000003",
            last_known_ip="192.168.1.20",
            reason_code=CustomerBlocklist.ReasonCode.OTHER,
            is_active=True,
            blocked_at=timezone.now(),
        )
        from .anti_abuse import is_customer_blocked

        self.assertFalse(
            is_customer_blocked(
                self.salon,
                phone="070333777",
                ip="192.168.1.20",
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

    def _future_date(self, days=20):
        selected = timezone.localdate() + timedelta(days=days)
        while selected.weekday() == 6:
            selected += timedelta(days=1)
        return selected

    def test_save_booking_phone_match_returns_structured_error(self):
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Biljana Stojanovska",
            phone_number="070999888",
            preferred_contact_method=Customer.PreferredContactMethod.VIBER,
        )
        selected = self._future_date()
        response = self._fetch_post(
            {
                "action": "save_booking",
                "full_name": "Simona Maneva",
                "phone_number": "070999888",
                "instagram_username": "",
                "email": "",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.service.id],
                "date": selected.isoformat(),
                "start_time": "10:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
                "return_section": "calendar",
            }
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["code"], "phone_match")
        self.assertEqual(data["phone_match"]["existing_name"], "Biljana Stojanovska")
        self.assertEqual(data["phone_match"]["typed_name"], "Simona Maneva")
        customer.refresh_from_db()
        self.assertEqual(customer.full_name, "Biljana Stojanovska")
        self.assertFalse(Booking.objects.filter(customer=customer).exists())

    def test_save_booking_phone_match_confirmed_keeps_existing_name(self):
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Biljana Stojanovska",
            phone_number="070999888",
            preferred_contact_method=Customer.PreferredContactMethod.VIBER,
        )
        selected = self._future_date()
        response = self._fetch_post(
            {
                "action": "save_booking",
                "full_name": "Simona Maneva",
                "phone_number": "070999888",
                "instagram_username": "biljana",
                "email": "",
                "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
                "services": [self.service.id],
                "date": selected.isoformat(),
                "start_time": "10:00",
                "status": Booking.Status.APPROVED,
                "source": Booking.Source.OWNER_MANUAL,
                "same_client_confirmed": "1",
                "return_section": "calendar",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        customer.refresh_from_db()
        self.assertEqual(customer.full_name, "Biljana Stojanovska")
        self.assertTrue(Booking.objects.filter(customer=customer).exists())

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

    def test_save_service_respects_unchecked_photo_toggles(self):
        """OwnerAjax sends unchecked checkboxes as 'false'; do not treat presence as True."""
        response = self._fetch_post(
            {
                "action": "save_service",
                "name": "Gel manicure",
                "duration_minutes": "90",
                "base_price": "800",
                "sort_order": "0",
                "is_active": "on",
                "requires_photo": "false",
                "photo_recommended": "false",
                "return_section": "services",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        service = self.salon.services.get(name="Gel manicure")
        self.assertTrue(service.is_active)
        self.assertFalse(service.requires_photo)
        self.assertFalse(service.photo_recommended)

    def test_edit_service_can_turn_photo_toggles_off(self):
        service = Service.objects.create(
            salon=self.salon,
            name="Design",
            duration_minutes=120,
            base_price=1500,
            requires_photo=True,
            photo_recommended=True,
            is_active=True,
        )
        response = self._fetch_post(
            {
                "action": "save_service",
                "service_id": str(service.pk),
                "name": "Design",
                "duration_minutes": "120",
                "base_price": "1500",
                "sort_order": "0",
                "is_active": "on",
                "requires_photo": "false",
                "photo_recommended": "false",
                "return_section": "services",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        service.refresh_from_db()
        self.assertFalse(service.requires_photo)
        self.assertFalse(service.photo_recommended)

    def test_save_service_can_enable_photo_toggles(self):
        response = self._fetch_post(
            {
                "action": "save_service",
                "name": "Medical pedicure",
                "duration_minutes": "120",
                "base_price": "2000",
                "sort_order": "0",
                "is_active": "on",
                "requires_photo": "on",
                "photo_recommended": "on",
                "return_section": "services",
            }
        )
        self.assertEqual(response.status_code, 200)
        service = self.salon.services.get(name="Medical pedicure")
        self.assertTrue(service.requires_photo)
        self.assertTrue(service.photo_recommended)

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

    def test_save_public_hours_display_returns_json(self):
        response = self._fetch_post(
            {
                "action": "save_public_hours_display",
                "public_hours_end_display": "16:00",
                "return_section": "hours",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["action"], "save_public_hours_display")
        self.salon.refresh_from_db()
        self.assertEqual(self.salon.public_hours_end_display, time(16, 0))

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

    def test_save_blocked_date_without_end_blocks_one_day(self):
        day = timezone.localdate() + timedelta(days=20)
        response = self._fetch_post(
            {
                "action": "save_blocked_date",
                "date": day.isoformat(),
                "end_date": "",
                "reason": "Trip",
                "return_section": "availability",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        rows = list(
            self.salon.date_working_hours_overrides.filter(
                mode=DateWorkingHoursOverride.Mode.CLOSED
            )
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].date, day)
        self.assertEqual(rows[0].reason, "Trip")

    def test_save_blocked_date_range_blocks_each_day(self):
        start = timezone.localdate() + timedelta(days=20)
        end = start + timedelta(days=4)
        response = self._fetch_post(
            {
                "action": "save_blocked_date",
                "date": start.isoformat(),
                "end_date": end.isoformat(),
                "reason": "Vacation",
                "return_section": "availability",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        dates = list(
            self.salon.date_working_hours_overrides.filter(
                mode=DateWorkingHoursOverride.Mode.CLOSED
            )
            .order_by("date")
            .values_list("date", flat=True)
        )
        self.assertEqual(dates, [start + timedelta(days=i) for i in range(5)])

    def test_save_blocked_date_end_before_start_fails(self):
        start = timezone.localdate() + timedelta(days=20)
        response = self._fetch_post(
            {
                "action": "save_blocked_date",
                "date": start.isoformat(),
                "end_date": (start - timedelta(days=1)).isoformat(),
                "return_section": "availability",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])
        self.assertFalse(self.salon.date_working_hours_overrides.exists())

    def test_delete_blocked_date_range_ids(self):
        start = timezone.localdate() + timedelta(days=21)
        ids = []
        for offset in range(3):
            row = DateWorkingHoursOverride.objects.create(
                salon=self.salon,
                date=start + timedelta(days=offset),
                mode=DateWorkingHoursOverride.Mode.CLOSED,
                reason="Away",
            )
            ids.append(row.id)
        response = self._fetch_post(
            {
                "action": "delete_blocked_date",
                "override_id": ids[0],
                "override_ids": ",".join(str(item) for item in ids),
                "return_section": "availability",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(
            self.salon.date_working_hours_overrides.filter(pk__in=ids).exists()
        )

    def test_blocked_date_range_is_grouped_in_list(self):
        start = timezone.localdate() + timedelta(days=22)
        ids = []
        for offset in range(3):
            row = DateWorkingHoursOverride.objects.create(
                salon=self.salon,
                date=start + timedelta(days=offset),
                mode=DateWorkingHoursOverride.Mode.CLOSED,
                reason="Away",
            )
            ids.append(row.id)
        response = self.client.get(reverse("booking:owner_dashboard"))
        self.assertContains(response, start.strftime("%d/%m/%Y"))
        self.assertContains(response, (start + timedelta(days=2)).strftime("%d/%m/%Y"))
        self.assertContains(response, ",".join(str(item) for item in ids))

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

    def test_grouped_price_items_render_group_move_arrows(self):
        ServicePriceItem.objects.create(
            service=self.service,
            name="Short",
            price_display="500",
            group="Gel",
            sort_order=0,
        )
        ServicePriceItem.objects.create(
            service=self.service,
            name="Long",
            price_display="900",
            group="Acrylic",
            sort_order=1,
        )
        response = self.client.get(reverse("booking:owner_dashboard"))
        self.assertContains(response, 'data-group-move="up"')
        self.assertContains(response, 'data-group-move="down"')
        self.assertContains(response, "od-price-group-head")

    def test_reorder_moves_group_block_and_persists_order(self):
        gel_a = ServicePriceItem.objects.create(
            service=self.service, name="Gel A", price_display="500", group="Gel", sort_order=0
        )
        gel_b = ServicePriceItem.objects.create(
            service=self.service, name="Gel B", price_display="550", group="Gel", sort_order=1
        )
        acr_a = ServicePriceItem.objects.create(
            service=self.service, name="Acr A", price_display="900", group="Acrylic", sort_order=2
        )
        # Simulate the front-end moving the Acrylic group above the Gel group:
        # the whole Acrylic block comes first, Gel block after.
        new_order = [acr_a.id, gel_a.id, gel_b.id]
        response = self._fetch_post(
            {
                "action": "reorder_price_items",
                "item_ids": ",".join(str(i) for i in new_order),
                "return_section": "services",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        acr_a.refresh_from_db()
        gel_a.refresh_from_db()
        gel_b.refresh_from_db()
        self.assertLess(acr_a.sort_order, gel_a.sort_order)
        self.assertLess(gel_a.sort_order, gel_b.sort_order)

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


class BrevoAPIEmailBackendTests(TestCase):
    @override_settings(
        BREVO_API_KEY="test-key",
        DEFAULT_FROM_EMAIL="Fancy Fingers <noreply@test.local>",
        EMAIL_BACKEND="booking.backends.brevo_api.BrevoAPIEmailBackend",
    )
    @patch("booking.backends.brevo_api.urllib.request.urlopen")
    def test_sends_via_brevo_api(self, mock_urlopen):
        from unittest.mock import MagicMock

        from django.core.mail import EmailMultiAlternatives

        from booking.backends.brevo_api import BREVO_API_URL

        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.status = 201
        mock_response.read = MagicMock(return_value=b'{"messageId":"abc"}')
        mock_urlopen.return_value = mock_response

        msg = EmailMultiAlternatives(
            subject="Test subject",
            body="Hello body",
            from_email="Fancy Fingers <noreply@test.local>",
            to=["user@example.com"],
            reply_to=["owner@test.local"],
        )
        msg.attach_alternative("<p>Hello body</p>", "text/html")
        sent = msg.send()
        self.assertEqual(sent, 1)
        mock_urlopen.assert_called_once()
        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, BREVO_API_URL)
        self.assertEqual(request.headers.get("Api-key"), "test-key")

    @override_settings(
        BREVO_API_KEY="",
        EMAIL_BACKEND="booking.backends.brevo_api.BrevoAPIEmailBackend",
    )
    def test_missing_api_key_returns_zero(self):
        from django.core.mail import send_mail

        sent = send_mail("Subject", "Body", None, ["user@example.com"], fail_silently=True)
        self.assertEqual(sent, 0)


class SmsVerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner_sms",
            email="owner_sms@example.com",
            password="pass",
        )
        self.salon = Salon.objects.create(owner=self.owner, name="Salon SMS", slug="salon-sms")
        self.policy = BookingPolicy.objects.create(
            salon=self.salon,
            minimum_notice_days=0,
            email_verification_required=False,
            sms_verification_required=True,
            sms_verification_expiration_minutes=10,
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
            "full_name": "SMS Customer",
            "phone_number": "070555999",
            "preferred_contact_method": Customer.PreferredContactMethod.VIBER,
            "rules_accepted": "on",
        }
        data.update(extra)
        return data

    @patch("booking.sms_utils.send_brevo_transactional_sms", return_value=(True, "sent"))
    def test_post_redirects_to_sms_verify_without_email(self, mock_send):
        response = self.client.post("/book/salon-sms/request/", self._booking_post_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("booking:booking_verify_sms"))
        booking = Booking.objects.get(customer__phone_number="070555999")
        self.assertEqual(booking.status, Booking.Status.UNVERIFIED)
        self.assertTrue(booking.sms_otp_digest)
        mock_send.assert_called_once()

    @patch("booking.sms_utils.send_brevo_transactional_sms", return_value=(True, "sent"))
    def test_valid_otp_promotes_to_pending(self, mock_send):
        self.client.post("/book/salon-sms/request/", self._booking_post_data(phone_number="070555998"))
        booking = Booking.objects.get(customer__phone_number="070555998")
        self.assertEqual(booking.status, Booking.Status.UNVERIFIED)

        with patch("booking.sms_utils.verify_booking_sms_otp", return_value=True):
            response = self.client.post(
                reverse("booking:booking_verify_sms"),
                {"otp_code": "123456"},
            )
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.PENDING)
        self.assertIsNotNone(booking.phone_verified_at)
        self.assertEqual(booking.sms_otp_digest, "")

    def test_booking_form_hides_email_when_sms_verification_on(self):
        response = self.client.get("/book/salon-sms/request/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="id_email"')
        self.assertContains(response, 'data-sms-verification="true"')

    def test_enabling_sms_verification_disables_email_in_policy_form(self):
        policy = self.salon.booking_policy
        policy.email_verification_required = True
        policy.sms_verification_required = False
        policy.save()
        form = BookingPolicyForm(
            data={
                "minimum_notice_days": policy.minimum_notice_days,
                "maximum_booking_window_days": policy.maximum_booking_window_days,
                "late_arrival_limit_minutes": policy.late_arrival_limit_minutes,
                "reminder_hours_before": policy.reminder_hours_before,
                "max_appointments_per_day": policy.max_appointments_per_day,
                "slot_interval_minutes": policy.slot_interval_minutes,
                "buffer_minutes_between_bookings": policy.buffer_minutes_between_bookings,
                "service_gap_minutes": policy.service_gap_minutes,
                "customer_cancellation_notice_hours": policy.customer_cancellation_notice_hours,
                "max_pending_bookings_per_customer": policy.max_pending_bookings_per_customer,
                "max_active_future_bookings_per_customer": policy.max_active_future_bookings_per_customer,
                "booking_rate_limit_per_ip_per_hour": policy.booking_rate_limit_per_ip_per_hour,
                "booking_rate_limit_per_email_per_day": policy.booking_rate_limit_per_email_per_day,
                "booking_rate_limit_per_phone_per_day": policy.booking_rate_limit_per_phone_per_day,
                "max_reference_photo_size_mb": policy.max_reference_photo_size_mb,
                "email_verification_expiration_minutes": policy.email_verification_expiration_minutes,
                "sms_verification_expiration_minutes": policy.sms_verification_expiration_minutes,
                "fixed_start_times_text": "",
                "salon_rules": policy.salon_rules,
                "salon_rules_en": policy.salon_rules_en,
                "msg_approved": policy.msg_approved,
                "msg_rejected": policy.msg_rejected,
                "msg_cancelled": policy.msg_cancelled,
                "msg_edited": policy.msg_edited,
                "msg_no_show": policy.msg_no_show,
                "msg_pending": policy.msg_pending,
                "msg_reminder": policy.msg_reminder,
                "email_verification_required": True,
                "sms_verification_required": True,
            },
            instance=policy,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertTrue(saved.sms_verification_required)
        self.assertFalse(saved.email_verification_required)

    @patch("booking.sms_utils.send_brevo_transactional_sms", return_value=(True, "sent"))
    @override_settings(BREVO_API_KEY="test-key", BREVO_SMS_SENDER="SalonSMS")
    def test_transactional_sms_on_approve(self, mock_send):
        self.policy.sms_notifications_enabled = True
        self.policy.save()
        customer = Customer.objects.create(
            salon=self.salon,
            full_name="Notify Me",
            phone_number="070111222",
            email="",
        )
        booking = Booking.objects.create(
            salon=self.salon,
            customer=customer,
            status=Booking.Status.PENDING,
            start_at=timezone.now() + timedelta(days=21),
            end_at=timezone.now() + timedelta(days=21, hours=2),
            total_duration_minutes=120,
            source=Booking.Source.ONLINE,
            rules_accepted=True,
        )
        booking.booking_services.create(
            service=self.service,
            service_name_snapshot=self.service.name,
            duration_minutes_snapshot=120,
            price_snapshot=600,
        )
        sent, reason = send_booking_notification(booking, "approved")
        self.assertTrue(sent)
        mock_send.assert_called_once()

    def test_format_phone_for_brevo_macedonia(self):
        from booking.sms_utils import format_phone_for_brevo

        self.assertEqual(format_phone_for_brevo("070 123 456"), "38970123456")
        self.assertEqual(format_phone_for_brevo("+389 70 123 456"), "38970123456")


class OwnerStatisticsTests(TestCase):
    def setUp(self):
        from decimal import Decimal

        self.Decimal = Decimal
        user = get_user_model().objects.create_user(username="statowner", password="pw")
        self.salon = Salon.objects.create(
            owner=user, name="Stat Studio", slug="stat-studio"
        )
        self.service = Service.objects.create(
            salon=self.salon, name="Manicure", duration_minutes=120, base_price=1000
        )
        self.customer = Customer.objects.create(
            salon=self.salon, full_name="Stat Client", phone_number="070000000"
        )
        self.now = timezone.now()

    def _booking(self, status, source, lines, start_at=None):
        start = start_at or self.now
        booking = Booking.objects.create(
            salon=self.salon,
            customer=self.customer,
            status=status,
            start_at=start,
            end_at=start + timedelta(hours=2),
            total_duration_minutes=120,
            source=source,
            rules_accepted=True,
        )
        for name, price in lines:
            BookingService.objects.create(
                booking=booking,
                service=self.service,
                service_name_snapshot=name,
                price_snapshot=self.Decimal(price),
            )
        return booking

    def test_statistics_aggregate_expected_values(self):
        self._booking(
            Booking.Status.COMPLETED, Booking.Source.ONLINE, [("Manicure", "1000")]
        )
        self._booking(
            Booking.Status.COMPLETED, Booking.Source.ONLINE, [("Manicure", "500")]
        )
        self._booking(
            Booking.Status.NO_SHOW, Booking.Source.OWNER_MANUAL, [("Pedicure", "800")]
        )
        self._booking(
            Booking.Status.PENDING, Booking.Source.ONLINE, [("Manicure", "1000")]
        )

        stats = get_owner_statistics(self.salon)
        month = stats["ranges"]["month"]
        year = stats["ranges"]["year"]
        all_time = stats["ranges"]["all"]

        self.assertTrue(stats["has_data"])
        self.assertEqual(stats["default_range"], "month")
        # Money comes from completed bookings only.
        self.assertEqual(month["revenue"], 1500)
        self.assertEqual(all_time["revenue"], 1500)
        self.assertEqual(month["completed"], 2)
        # No-show rate = no_show / (completed + no_show) = 1 / 3 -> 33%.
        self.assertEqual(month["no_show_rate"], 33)
        # Online share = online / non-unverified bookings = 3 / 4 -> 75%.
        self.assertEqual(month["online_share"], 75)
        self.assertEqual(year["revenue"], 1500)

        top = {row["name"]: row["count"] for row in month["top_services"]}
        self.assertEqual(top.get("Manicure"), 3)
        self.assertEqual(top.get("Pedicure"), 1)

        # This month is a daily chart covering the current calendar month.
        self.assertGreaterEqual(len(month["trend"]), timezone.localdate().day)
        accepted_this_month = sum(point["bookings"] for point in month["trend"])
        self.assertEqual(accepted_this_month, 3)
        self.assertEqual(sum(point["revenue"] for point in month["trend"]), 1500)

        # This year is 12 monthly bars; all-time spans from first booking to now.
        self.assertEqual(len(year["trend"]), 12)
        self.assertGreaterEqual(len(all_time["trend"]), 1)
        self.assertEqual(all_time["trend"][-1]["bookings"], 3)

        self.assertIsNotNone(month["busiest_weekday"])
        self.assertEqual(month["busiest_weekday"]["count"], 3)
        self.assertIn("note", month["busiest_weekday"])
        # Full weekday name in the sentence (e.g. Wednesday), not the short chart label (Wed).
        self.assertGreater(len(month["busiest_weekday"]["label"]), 3)

    def test_statistics_empty_salon_has_no_data(self):
        stats = get_owner_statistics(self.salon)

        self.assertFalse(stats["has_data"])
        self.assertEqual(stats["ranges"]["month"]["no_show_rate"], 0)
        self.assertEqual(stats["ranges"]["all"]["online_share"], 0)
        self.assertIsNone(stats["ranges"]["all"]["busiest_weekday"])
        self.assertEqual(stats["ranges"]["all"]["top_services"], [])
        self.assertEqual(len(stats["ranges"]["all"]["trend"]), 6)
        self.assertEqual(len(stats["ranges"]["year"]["trend"]), 12)

    def test_statistics_range_excludes_previous_year(self):
        last_year = timezone.make_aware(datetime(timezone.now().year - 1, 6, 15, 10, 0))
        self._booking(
            Booking.Status.COMPLETED,
            Booking.Source.ONLINE,
            [("Gel", "2000")],
            start_at=last_year,
        )
        self._booking(
            Booking.Status.COMPLETED, Booking.Source.ONLINE, [("Manicure", "1000")]
        )

        stats = get_owner_statistics(self.salon)
        self.assertEqual(stats["ranges"]["month"]["revenue"], 1000)
        self.assertEqual(stats["ranges"]["year"]["revenue"], 1000)
        self.assertEqual(stats["ranges"]["all"]["revenue"], 3000)
        self.assertEqual(stats["ranges"]["month"]["completed"], 1)
        self.assertEqual(stats["ranges"]["all"]["completed"], 2)

    def test_busiest_day_note_is_translated_with_full_weekday(self):
        self._booking(
            Booking.Status.COMPLETED, Booking.Source.ONLINE, [("Manicure", "1000")]
        )
        with override("mk"):
            stats = get_owner_statistics(self.salon)
        note = stats["ranges"]["month"]["busiest_weekday"]["note"]
        self.assertTrue(
            note.startswith("Вашиот најзафатен ден е "),
            msg=note,
        )
        self.assertFalse(note.startswith("Your busiest day"))
        # Full Macedonian weekday, not the short chart form like "Сре".
        self.assertNotIn(" Сре.", note)
