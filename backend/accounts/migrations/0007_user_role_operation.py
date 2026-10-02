from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_user_nickname"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("TEACHER", "Teacher"),
                    ("OPERATION", "Operation"),
                    ("STUDENT", "Student"),
                ],
                default="STUDENT",
                help_text="App role for teacher/student/operation flows. Django admin access is controlled by superuser status.",
                max_length=20,
            ),
        ),
    ]
