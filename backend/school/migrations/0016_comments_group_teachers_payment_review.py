from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_group_teachers(apps, schema_editor):
    TeacherGroup = apps.get_model("school", "TeacherGroup")
    through_model = TeacherGroup.teachers.through
    memberships = []
    existing = set(
        through_model.objects.values_list("teachergroup_id", "user_id")
    )
    for group in TeacherGroup.objects.exclude(teacher_id__isnull=True):
        key = (group.pk, group.teacher_id)
        if key in existing:
            continue
        memberships.append(
            through_model(teachergroup_id=group.pk, user_id=group.teacher_id)
        )
    through_model.objects.bulk_create(memberships, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("school", "0015_remove_person_uniq_person_line_id_when_present_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="interview_comment",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="teachergroup",
            name="teacher",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="legacy_teacher_groups",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="teachergroup",
            name="teachers",
            field=models.ManyToManyField(
                blank=True,
                related_name="teacher_groups",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_group_teachers, migrations.RunPython.noop),
        migrations.AddField(
            model_name="student",
            name="payment_review_note",
            field=models.TextField(blank=True),
        ),
    ]
