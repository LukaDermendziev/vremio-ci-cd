from django.core.management.base import BaseCommand

from booking.services import send_due_booking_reminders


class Command(BaseCommand):
    help = (
        "Send appointment reminders to customers for approved bookings "
        "based on each salon's reminder_hours_before policy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many reminders would be sent without sending.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        count = send_due_booking_reminders(dry_run=dry_run)
        if dry_run:
            self.stdout.write(f"Would send {count} appointment reminder(s).")
            return
        if count == 0:
            self.stdout.write("No appointment reminders due.")
            return
        self.stdout.write(self.style.SUCCESS(f"Sent {count} appointment reminder(s)."))
