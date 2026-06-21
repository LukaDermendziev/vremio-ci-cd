import uuid

from django.db import migrations, models


def populate_manage_tokens(apps, schema_editor):
    Booking = apps.get_model("booking", "Booking")
    for booking in Booking.objects.all():
        booking.manage_token = uuid.uuid4()
        booking.save(update_fields=["manage_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0006_add_policy_messages"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingpolicy",
            name="customer_cancellation_notice_hours",
            field=models.PositiveSmallIntegerField(
                default=24,
                help_text="Minimum hours before appointment start when customers may cancel online.",
            ),
        ),
        migrations.AddField(
            model_name="booking",
            name="manage_token",
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="booking",
            name="cancelled_by_customer",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(populate_manage_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="booking",
            name="manage_token",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
