from django.db import migrations


def create_role_groups(apps, schema_editor):
    group = apps.get_model("auth", "Group")
    for name in ("ADMIN", "TEACHER", "STUDENT"):
        group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_role_groups, migrations.RunPython.noop),
    ]
