from django.db import migrations, models


def backfill_notification_count(apps, schema_editor):
    AppointmentParticipant = apps.get_model("school", "AppointmentParticipant")
    AppointmentParticipant.objects.filter(notification_status="sent").update(
        notification_count=1
    )


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0016_comments_group_teachers_payment_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointmentparticipant",
            name="invitation_message",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="appointmentparticipant",
            name="notification_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(backfill_notification_count, migrations.RunPython.noop),
    ]
