from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0011_email_verification_and_photo_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingpolicy",
            name="auto_complete_hours_after_end",
            field=models.PositiveSmallIntegerField(
                default=4,
                help_text="Hours after appointment end to auto-mark approved bookings as completed (0 = disabled).",
            ),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="calendar_history_days",
            field=models.PositiveSmallIntegerField(
                default=365,
                help_text="Max days to show completed/cancelled bookings on the owner calendar.",
            ),
        ),
    ]
