from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from booking.models import BookingPolicy, Salon, Service, WorkingHours
from booking.services import DEFAULT_END_TIME, DEFAULT_START_TIME, ensure_default_working_hours


DEFAULT_SERVICES = [
    {
        "name": "Маникир",
        "duration_minutes": 120,
        "base_price": 600,
        "photo_recommended": True,
        "requires_photo": False,
        "sort_order": 1,
    },
    {
        "name": "Маникир со дизајн",
        "duration_minutes": 120,
        "base_price": 600,
        "photo_recommended": True,
        "requires_photo": False,
        "sort_order": 2,
    },
    {
        "name": "Педикир",
        "duration_minutes": 120,
        "base_price": 600,
        "photo_recommended": False,
        "requires_photo": False,
        "sort_order": 3,
    },
    {
        "name": "Медицински педикир",
        "duration_minutes": 120,
        "base_price": 600,
        "photo_recommended": False,
        "requires_photo": True,
        "sort_order": 4,
    },
]


class Command(BaseCommand):
    help = (
        "Create or update beta salon data: owner user, salon, booking policy, "
        "working hours, and default services."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Owner Django username")
        parser.add_argument("--email", required=True, help="Owner email address")
        parser.add_argument("--slug", required=True, help="Salon URL slug, e.g. fancy-fingers")
        parser.add_argument(
            "--salon-name",
            default="",
            help="Salon display name (defaults to title-cased slug)",
        )
        parser.add_argument(
            "--user-exists",
            action="store_true",
            help="Use an existing user instead of creating one",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Create owner as superuser (dev convenience only)",
        )
        parser.add_argument(
            "--instagram",
            default="",
            help="Salon Instagram username (without @)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update existing salon/policy/services if they already exist",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip()
        slug = options["slug"].strip()
        salon_name = options["salon_name"].strip() or slug.replace("-", " ").title()

        if not username or not email or not slug:
            raise CommandError("--username, --email, and --slug are required.")

        User = get_user_model()
        user = User.objects.filter(username=username).first()

        if options["user_exists"]:
            if not user:
                raise CommandError(f"User '{username}' does not exist. Remove --user-exists or create the user first.")
            if user.email != email:
                user.email = email
                user.save(update_fields=["email"])
                self.stdout.write(f"Updated email for user '{username}'.")
        else:
            if user:
                if not options["force"]:
                    raise CommandError(
                        f"User '{username}' already exists. Use --user-exists or --force."
                    )
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=None,
                )
                user.set_unusable_password()
                if options["superuser"]:
                    user.is_staff = True
                    user.is_superuser = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user '{username}' (no password set)."))

        salon, salon_created = Salon.objects.get_or_create(
            slug=slug,
            defaults={
                "owner": user,
                "name": salon_name,
                "is_active": True,
                "business_category": Salon.BusinessCategory.SALON,
                "short_description": "Салон за маникир и педикир.",
                "city": "Скопје",
            },
        )
        if not salon_created:
            if salon.owner_id != user.id and not options["force"]:
                raise CommandError(
                    f"Salon slug '{slug}' belongs to another owner. Use --force to reassign."
                )
            salon.owner = user
            salon.name = salon_name
            salon.is_active = True
            if options["force"]:
                salon.business_category = Salon.BusinessCategory.SALON
                if not salon.short_description:
                    salon.short_description = "Салон за маникир и педикир."
                if not salon.city:
                    salon.city = "Скопје"
            salon.save()
            self.stdout.write(f"Updated salon '{salon_name}'.")
        else:
            self.stdout.write(self.style.SUCCESS(f"Created salon '{salon_name}' ({slug})."))

        instagram = options["instagram"].strip().lstrip("@")
        if instagram and (options["force"] or salon_created or not salon.instagram_username):
            salon.instagram_username = instagram
            salon.save(update_fields=["instagram_username"])
            self.stdout.write(f"Instagram: @{instagram}")

        policy, policy_created = BookingPolicy.objects.get_or_create(salon=salon)
        if options["force"] or policy_created:
            policy.minimum_notice_days = 14
            policy.maximum_booking_window_days = 60
            policy.allow_same_day_booking = False
            policy.allow_next_day_booking = False
            policy.allow_last_minute_reopen = True
            policy.auto_approve_bookings = False
            policy.pending_holds_slot = True
            policy.late_arrival_limit_minutes = 15
            policy.reminder_hours_before = 24
            policy.use_fixed_start_times = True
            policy.fixed_start_times = ["08:00", "10:30", "13:00", "15:30"]
            policy.max_appointments_per_day = 4
            policy.save()
            self.stdout.write("Booking policy configured with beta defaults.")

        ensure_default_working_hours(salon)
        for weekday in range(7):
            WorkingHours.objects.update_or_create(
                salon=salon,
                weekday=weekday,
                defaults={
                    "is_working_day": weekday != WorkingHours.Weekday.SUNDAY,
                    "start_time": DEFAULT_START_TIME,
                    "end_time": DEFAULT_END_TIME,
                },
            )
        self.stdout.write("Working hours set: Mon–Sat 08:00–18:00, Sunday closed.")

        for svc_data in DEFAULT_SERVICES:
            service, created = Service.objects.get_or_create(
                salon=salon,
                name=svc_data["name"],
                defaults=svc_data,
            )
            if options["force"] and not created:
                for field, value in svc_data.items():
                    setattr(service, field, value)
                service.is_active = True
                service.save()
            elif created:
                self.stdout.write(
                    f"  + Service: {self._console_safe(svc_data['name'])}"
                )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Beta salon setup complete."))
        self.stdout.write("")
        self.stdout.write("Next steps:")
        self.stdout.write("  1. Send password setup link: /owner/password/reset/")
        self.stdout.write("     Or run: python manage.py changepassword " + username)
        self.stdout.write(f"  2. Owner login: /owner/login/")
        self.stdout.write(f"  3. Customer page: /book/{slug}/")
        self.stdout.write(f"  4. Admin panel: /admin/")

    def _console_safe(self, text: str) -> str:
        encoding = getattr(self.stdout, "encoding", None) or "utf-8"
        return text.encode(encoding, errors="replace").decode(encoding)
