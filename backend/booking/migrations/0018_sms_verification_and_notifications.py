from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0017_fixed_start_times"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingpolicy",
            name="sms_notifications_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Send transactional SMS to customers on booking status changes.",
            ),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="sms_verification_expiration_minutes",
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="sms_verification_required",
            field=models.BooleanField(
                default=False,
                help_text="Online bookings require SMS OTP verification before becoming pending.",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="phone_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="sms_otp_digest",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AlterField(
            model_name="bookingactivitylog",
            name="action",
            field=models.CharField(
                choices=[
                    ("requested", "Requested"),
                    ("verification_sent", "Verification sent"),
                    ("email_verified", "Email verified"),
                    ("phone_verified", "Phone verified"),
                    ("verification_expired", "Verification expired"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("cancelled", "Cancelled"),
                    ("customer_cancelled", "Cancelled by customer"),
                    ("edited", "Edited"),
                    ("completed", "Completed"),
                    ("no_show", "No Show"),
                    ("email_sent", "Email sent"),
                    ("sms_sent", "SMS sent"),
                    ("photo_removed", "Photo removed"),
                    ("customer_blocked", "Customer blocked"),
                ],
                max_length=30,
            ),
        ),
    ]
