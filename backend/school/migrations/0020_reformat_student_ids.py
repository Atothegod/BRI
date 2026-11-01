from django.db import migrations


def reformat_student_ids(apps, schema_editor):
    Student = apps.get_model("school", "Student")
    student_ids = list(
        Student.objects.order_by("created_at", "pk").values_list("pk", flat=True)
    )

    # Move every value out of the final namespace first so the unique constraint
    # cannot collide while existing IDs are being reordered.
    for student_pk in student_ids:
        Student.objects.filter(pk=student_pk).update(student_id=f"tmp-{student_pk}")

    for offset, student_pk in enumerate(student_ids, start=5001):
        Student.objects.filter(pk=student_pk).update(student_id=f"BRI {offset}")


class Migration(migrations.Migration):

    dependencies = [
        ("school", "0019_appointmentslot_interview_mode"),
    ]

    operations = [
        migrations.RunPython(reformat_student_ids, migrations.RunPython.noop),
    ]
