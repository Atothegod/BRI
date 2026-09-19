import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0013_class_appointments_homework_upload"),
    ]

    operations = [
        migrations.CreateModel(
            name="AppointmentSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("starts_at", models.DateTimeField()),
                ("ends_at", models.DateTimeField()),
                ("capacity", models.PositiveIntegerField(default=0)),
                (
                    "appointment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="school.appointment",
                    ),
                ),
            ],
            options={"ordering": ("starts_at", "pk")},
        ),
        migrations.AddField(
            model_name="appointmentparticipant",
            name="selected_slot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="participants",
                to="school.appointmentslot",
            ),
        ),
    ]
