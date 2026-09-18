from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0012_backfill_teacher_groups"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appointment",
            name="appointment_type",
            field=models.CharField(
                choices=[
                    ("interview", "สัมภาษณ์"),
                    ("orientation", "ปฐมนิเทศ"),
                    ("class", "นัดเรียน"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="homeworksubmission",
            name="student_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="homeworksubmission",
            name="submission_file",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="homework_submissions/",
            ),
        ),
    ]
