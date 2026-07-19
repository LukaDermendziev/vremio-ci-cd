from django.db import migrations, models


def backfill_salon_plans(apps, schema_editor):
    Salon = apps.get_model("booking", "Salon")
    # Existing Pro-branded sites (e.g. Fancy Fingers) → Pro plan.
    Salon.objects.filter(website_template="pro").update(plan="pro")
    Salon.objects.filter(slug="fancy-fingers").update(plan="pro", website_template="pro")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0020_salon_website_template"),
    ]

    operations = [
        migrations.AddField(
            model_name="salon",
            name="plan",
            field=models.CharField(
                choices=[
                    ("starter", "Starter"),
                    ("pro", "Pro"),
                    ("premium", "Premium"),
                ],
                db_index=True,
                default="starter",
                help_text=(
                    "Subscription plan for this business. "
                    "Controls website template and future plan features."
                ),
                max_length=20,
            ),
        ),
        migrations.AlterField(
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
                    "Synced from plan automatically. "
                    "Starter plan → Vremio template; Pro/Premium → custom branded page."
                ),
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_salon_plans, noop_reverse),
    ]
