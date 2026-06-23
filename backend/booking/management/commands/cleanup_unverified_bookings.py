from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import Booking, BookingActivityLog
from booking.services import delete_unverified_booking, log_booking_activity


class Command(BaseCommand):
    help = "Delete expired unverified bookings and their reference photos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without making changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()
        expired = Booking.objects.filter(
            status=Booking.Status.UNVERIFIED,
            verification_expires_at__lt=now,
        ).select_related("salon")

        count = expired.count()
        if count == 0:
            self.stdout.write("No expired unverified bookings to clean up.")
            return

        if dry_run:
            self.stdout.write(f"Would delete {count} expired unverified booking(s).")
            for booking in expired:
                self.stdout.write(
                    f"  - #{booking.id} {booking.customer.full_name} "
                    f"({booking.salon.slug}) expires {booking.verification_expires_at}"
                )
            return

        deleted = 0
        for booking in expired:
            log_booking_activity(
                booking,
                BookingActivityLog.Action.VERIFICATION_EXPIRED,
                note="Cleaned up by cleanup_unverified_bookings",
            )
            delete_unverified_booking(booking)
            deleted += 1

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} expired unverified booking(s)."))
