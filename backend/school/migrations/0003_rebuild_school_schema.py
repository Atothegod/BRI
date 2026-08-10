import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0002_applicationdetail"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="ApplicationDetail"),
        migrations.DeleteModel(name="Submission"),
        migrations.DeleteModel(name="Attendance"),
        migrations.DeleteModel(name="Assignment"),
        migrations.DeleteModel(name="ClassSession"),
        migrations.DeleteModel(name="Enrollment"),
        migrations.DeleteModel(name="Student"),
        migrations.DeleteModel(name="ClassGroup"),
        migrations.DeleteModel(name="Application"),
        migrations.DeleteModel(name="AdmissionRound"),
        migrations.DeleteModel(name="Cohort"),
        migrations.DeleteModel(name="Program"),
        migrations.DeleteModel(name="TeacherProfile"),
        migrations.AddField(
            model_name="person",
            name="line_id",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="person",
            name="nickname",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name="person",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="person",
            constraint=models.UniqueConstraint(
                condition=~models.Q(line_id=""),
                fields=("line_id",),
                name="uniq_person_line_id_when_present",
            ),
        ),
        migrations.CreateModel(
            name="Registration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("registration_no", models.CharField(max_length=50, unique=True)),
                ("program_name", models.CharField(max_length=255)),
                ("round_name", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("passed", "Passed"),
                            ("rejected", "Rejected"),
                            ("waitlisted", "Waitlisted"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("extra_data", models.JSONField(blank=True, default=dict)),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="registrations",
                        to="school.person",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("person", "program_name", "round_name"),
                        name="uniq_registration_person_program_round",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="TeacherGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group_name", models.CharField(max_length=255)),
                ("grade_level", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="teacher_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Student",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("grade", models.CharField(blank=True, max_length=100)),
                (
                    "admin_validation_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("needs_fix", "Needs fix"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="students",
                        to="school.teachergroup",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="students",
                        to="school.person",
                    ),
                ),
                (
                    "registration",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="student",
                        to="school.registration",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AttendanceSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_sessions",
                        to="school.teachergroup",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("group", "date"), name="uniq_attendance_session_group_date")
                ],
            },
        ),
        migrations.CreateModel(
            name="AttendanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("present", "Present"), ("absent", "Absent"), ("late", "Late")],
                        max_length=20,
                    ),
                ),
                (
                    "attendance_session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to="school.attendancesession",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to="school.student",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("attendance_session", "student"),
                        name="uniq_attendance_record_session_student",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="HomeworkAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=255)),
                ("due_date", models.DateField()),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="homework_assignments",
                        to="school.teachergroup",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HomeworkSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("submitted", "Submitted"), ("late", "Late")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("submitted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "homework_assignment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="homework_submissions",
                        to="school.homeworkassignment",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="homework_submissions",
                        to="school.student",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("homework_assignment", "student"),
                        name="uniq_homework_submission_assignment_student",
                    )
                ],
            },
        ),
    ]
