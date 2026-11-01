from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0018_person_interview_grade"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointmentslot",
            name="interview_mode",
            field=models.CharField(
                choices=[("onsite", "Onsite"), ("online", "Online")],
                default="onsite",
                max_length=20,
            ),
        ),
    ]
