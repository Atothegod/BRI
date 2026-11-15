from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("school", "0024_teacher_student_assessment")]

    operations = [
        migrations.AlterField(
            model_name="homeworkassignment",
            name="group",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="homework_assignments",
                to="school.teachergroup",
            ),
        ),
    ]
