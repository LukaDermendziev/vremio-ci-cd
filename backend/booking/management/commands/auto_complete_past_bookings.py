from django.core.management.base import BaseCommand

from booking.services import auto_complete_past_bookings


class Command(BaseCommand):
    help = (
        "Auto-mark approved bookings as completed after their end time plus "
        "the salon policy grace period."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many bookings would be updated without saving.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        count = auto_complete_past_bookings(dry_run=dry_run)
        if dry_run:
            self.stdout.write(f"Would auto-complete {count} booking(s).")
            return
        if count == 0:
            self.stdout.write("No approved bookings ready for auto-completion.")
            return
        self.stdout.write(self.style.SUCCESS(f"Auto-completed {count} booking(s)."))
