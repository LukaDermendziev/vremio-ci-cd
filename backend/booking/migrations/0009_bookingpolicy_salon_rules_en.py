from django.db import migrations, models


DEFAULT_SALON_RULES_EN = (
    "Booking is available at least 14 days in advance.\n"
    "Being more than 15 minutes late without notice may result in cancellation.\n"
    "When cancelling, please notify us at least 24 hours in advance.\n"
    "A reference photo is required for certain services."
)


def populate_english_salon_rules(apps, schema_editor):
    BookingPolicy = apps.get_model("booking", "BookingPolicy")
    for policy in BookingPolicy.objects.filter(salon_rules_en=""):
        policy.salon_rules_en = DEFAULT_SALON_RULES_EN
        policy.save(update_fields=["salon_rules_en"])


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0008_anti_abuse_and_photo_policy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bookingpolicy",
            name="salon_rules",
            field=models.TextField(
                blank=True,
                default=(
                    "Закажувањето е можно минимум 14 дена однапред.\n"
                    "Доцнење повеќе од 15 минути без известување може да резултира со откажување на терминот.\n"
                    "При откажување, известете не најмалку 24 часа однапред.\n"
                    "За одредени услуги е потребна референтна фотографија."
                ),
                help_text=(
                    "Rules shown to customers when the site language is Macedonian. "
                    "Each line becomes a separate rule."
                ),
                verbose_name="Salon rules (Macedonian)",
            ),
        ),
        migrations.AddField(
            model_name="bookingpolicy",
            name="salon_rules_en",
            field=models.TextField(
                blank=True,
                default=(
                    "Booking is available at least 14 days in advance.\n"
                    "Being more than 15 minutes late without notice may result in cancellation.\n"
                    "When cancelling, please notify us at least 24 hours in advance.\n"
                    "A reference photo is required for certain services."
                ),
                help_text=(
                    "Rules shown to customers when the site language is English. "
                    "Each line becomes a separate rule."
                ),
                verbose_name="Salon rules (English)",
            ),
        ),
        migrations.RunPython(populate_english_salon_rules, migrations.RunPython.noop),
    ]
