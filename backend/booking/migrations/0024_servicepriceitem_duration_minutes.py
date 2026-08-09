from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0023_alter_customer_instagram_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicepriceitem",
            name="duration_minutes",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text=(
                    "How long this specific sub-service takes, in minutes. "
                    "Leave 0 to use the parent service's duration."
                ),
            ),
        ),
    ]
