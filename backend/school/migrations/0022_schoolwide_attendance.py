from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("school", "0021_payment_slips"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="attendancesession",
            name="uniq_attendance_session_group_date",
        ),
        migrations.AlterField(
            model_name="attendancesession",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_sessions",
                to="school.teachergroup",
            ),
        ),
        migrations.AddField(model_name="attendancesession", name="title", field=models.CharField(default="คาบเรียน", max_length=255)),
        migrations.AddField(model_name="attendancesession", name="topic", field=models.TextField(blank=True)),
        migrations.AddField(model_name="attendancesession", name="starts_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="attendancesession", name="ends_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="attendancesession", name="is_active", field=models.BooleanField(default=True)),
        migrations.AddField(
            model_name="attendancesession",
            name="created_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_attendance_sessions", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name="attendancerecord",
            name="status",
            field=models.CharField(choices=[("present", "มาเรียน"), ("absent", "ขาด"), ("late", "มาสาย"), ("leave", "ลา")], max_length=20),
        ),
        migrations.AddField(model_name="attendancerecord", name="checked_in_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="attendancerecord", name="note", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(
            model_name="attendancerecord",
            name="marked_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="marked_attendance_records", to=settings.AUTH_USER_MODEL),
        ),
    ]
