from django.core.management.base import BaseCommand, CommandError

from booking.email_utils import send_test_email


class Command(BaseCommand):
    help = "Send a test email to verify SMTP or console email configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            "recipient",
            help="Email address that should receive the test message.",
        )

    def handle(self, *args, **options):
        recipient = options["recipient"].strip()
        if not recipient or "@" not in recipient:
            raise CommandError("Provide a valid recipient email address.")

        sent, reason = send_test_email(recipient)
        if sent:
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}."))
            return

        if reason == "no_email":
            raise CommandError("Recipient email address is empty.")
        raise CommandError("Test email could not be sent. Check EMAIL_* settings and logs.")
