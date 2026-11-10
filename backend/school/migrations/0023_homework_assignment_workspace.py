from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("school", "0022_schoolwide_attendance"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="homeworkassignment",
            name="description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="homeworkassignment",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_homework_assignments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
