from django.conf import settings
from django.db import migrations


def default_group_name(user):
    nickname = (getattr(user, "nickname", "") or "").strip()
    if nickname:
        return nickname

    full_name = " ".join(
        part
        for part in (
            (getattr(user, "first_name", "") or "").strip(),
            (getattr(user, "last_name", "") or "").strip(),
        )
        if part
    )
    return full_name or (getattr(user, "username", "") or "").strip()


def create_missing_teacher_groups(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    TeacherGroup = apps.get_model("school", "TeacherGroup")

    for teacher in User.objects.filter(role="TEACHER", is_active=True):
        if TeacherGroup.objects.filter(teacher=teacher).exists():
            continue

        group_name = default_group_name(teacher)
        if not group_name:
            continue

        TeacherGroup.objects.create(
            teacher=teacher,
            group_name=group_name,
            is_active=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0006_user_nickname"),
        ("school", "0011_appointment_appointmentparticipant"),
    ]

    operations = [
        migrations.RunPython(create_missing_teacher_groups, migrations.RunPython.noop),
    ]
