from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0018_sms_verification_and_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="salon",
            name="public_hours_end_display",
            field=models.TimeField(
                blank=True,
                help_text="Optional end time shown on the public salon page only. Online booking still uses the working hours configured in the dashboard.",
                null=True,
                verbose_name="Public page closing time",
            ),
        ),
    ]
