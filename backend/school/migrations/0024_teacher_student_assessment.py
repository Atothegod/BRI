from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0023_homework_assignment_workspace"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherStudentAssessment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("grade", models.CharField(blank=True, choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D"), ("F", "F")], max_length=2)),
                ("comment", models.TextField(blank=True)),
                ("needs_care", models.BooleanField(default=False)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_assessments", to="school.student")),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_assessments", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "constraints": [models.UniqueConstraint(fields=("teacher", "student"), name="uniq_teacher_student_assessment")],
            },
        ),
    ]
