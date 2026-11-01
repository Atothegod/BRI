from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0017_appointmentparticipant_invitation_message_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="interview_grade",
            field=models.CharField(
                blank=True,
                choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")],
                max_length=1,
            ),
        ),
    ]
