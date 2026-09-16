from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0021_salon_plan"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customer",
            name="phone_number",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.RemoveConstraint(
            model_name="customer",
            name="unique_customer_phone_per_salon",
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                condition=models.Q(("phone_number", ""), _negated=True),
                fields=("salon", "phone_number"),
                name="unique_customer_phone_per_salon",
            ),
        ),
    ]
