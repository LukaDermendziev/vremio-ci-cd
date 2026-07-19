from django.db import migrations, models


def set_fancy_fingers_pro(apps, schema_editor):
    Salon = apps.get_model("booking", "Salon")
    Salon.objects.filter(slug="fancy-fingers").update(website_template="pro")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0019_salon_public_hours_end_display"),
    ]

    operations = [
        migrations.AddField(
            model_name="salon",
            name="website_template",
            field=models.CharField(
                choices=[
                    ("starter", "Starter (Vremio template)"),
                    ("pro", "Pro (custom branded)"),
                ],
                db_index=True,
                default="starter",
                help_text=(
                    "Starter uses the reusable Vremio business website. "
                    "Pro keeps the custom branded salon page (e.g. Fancy Fingers)."
                ),
                max_length=20,
            ),
        ),
        migrations.RunPython(set_fancy_fingers_pro, noop_reverse),
    ]
