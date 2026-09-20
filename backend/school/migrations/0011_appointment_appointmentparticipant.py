import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def migrate_legacy_interviews(apps, schema_editor):
    Person = apps.get_model("school", "Person")
    Appointment = apps.get_model("school", "Appointment")
    Participant = apps.get_model("school", "AppointmentParticipant")

    for person in Person.objects.exclude(interview_at=None).iterator():
        appointment = Appointment.objects.create(
            appointment_type="interview",
            title="นัดสัมภาษณ์ (ข้อมูลเดิม)",
            starts_at=person.interview_at,
            details=person.interview_details,
            status="scheduled",
        )
        response_status = "confirmed" if person.interview_confirmed_at else "waiting"
        notification_status = person.interview_notification_state or "pending"
        Participant.objects.create(
            appointment=appointment,
            person=person,
            response_status=response_status,
            notification_status=notification_status,
            notified_at=person.interview_notified_at,
            confirmed_at=person.interview_confirmed_at,
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("school", "0010_person_interview_confirmed_at"),
    ]

    operations = [
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("appointment_type", models.CharField(choices=[("interview", "สัมภาษณ์"), ("orientation", "ปฐมนิเทศ")], max_length=20)),
                ("title", models.CharField(max_length=255)),
                ("starts_at", models.DateTimeField()),
                ("location", models.CharField(blank=True, max_length=500)),
                ("meeting_url", models.URLField(blank=True, max_length=1000)),
                ("details", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("scheduled", "กำหนดนัดแล้ว"), ("cancelled", "ยกเลิก"), ("completed", "เสร็จสิ้น")], default="scheduled", max_length=20)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_appointments", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-starts_at", "-pk")},
        ),
        migrations.CreateModel(
            name="AppointmentParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("response_status", models.CharField(choices=[("waiting", "รอตอบรับ"), ("confirmed", "ยืนยันแล้ว"), ("declined", "ไม่สะดวกเข้าร่วม")], default="waiting", max_length=20)),
                ("notification_status", models.CharField(choices=[("pending", "รอส่ง"), ("sent", "LINE รับข้อความแล้ว"), ("failed", "ส่งไม่สำเร็จ")], default="pending", max_length=20)),
                ("notified_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("notification_error", models.CharField(blank=True, max_length=500)),
                ("appointment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="school.appointment")),
                ("person", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="appointment_participations", to="school.person")),
            ],
            options={"ordering": ("pk",)},
        ),
        migrations.AddConstraint(
            model_name="appointmentparticipant",
            constraint=models.UniqueConstraint(fields=("appointment", "person"), name="uniq_appointment_participant"),
        ),
        migrations.RunPython(migrate_legacy_interviews, migrations.RunPython.noop),
    ]
