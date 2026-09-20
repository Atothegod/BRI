from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0009_person_interview_at_person_interview_details_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="interview_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
