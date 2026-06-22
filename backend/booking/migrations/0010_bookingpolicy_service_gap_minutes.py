from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0009_bookingpolicy_salon_rules_en"),
    ]

    operations = [
        migrations.AddField(
            model_name="bookingpolicy",
            name="service_gap_minutes",
            field=models.PositiveSmallIntegerField(
                default=30,
                help_text="Gap between consecutive services within the same booking.",
            ),
        ),
    ]
