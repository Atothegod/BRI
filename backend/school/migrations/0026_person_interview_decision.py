from django.db import migrations, models


def stage_unannounced_results(apps, schema_editor):
    Person = apps.get_model("school", "Person")
    Student = apps.get_model("school", "Student")
    database = schema_editor.connection.alias
    paid_people = Student.objects.using(database).filter(is_paid=True).values("person_id")
    people = (
        Person.objects.using(database)
        .filter(status__in=["passed", "failed"])
        .exclude(status="passed", pk__in=paid_people)
    )
    for person in people.iterator():
        key = "interview_passed" if person.status == "passed" else "interview_failed"
        if (person.extra_data or {}).get("line_notifications", {}).get(key):
            continue
        if person.status == "failed":
            decision = "fail"
        else:
            decision = "pass_online" if person.admission_type == "online" else "pass_onsite"
        people.filter(pk=person.pk).update(
            interview_decision=decision, status="in_progress", admission_type=""
        )


def restore_staged_results(apps, schema_editor):
    Person = apps.get_model("school", "Person")
    outcomes = {
        "pass_online": ("passed", "online"),
        "pass_onsite": ("passed", "interview"),
        "fail": ("failed", ""),
    }
    for decision, (status, admission_type) in outcomes.items():
        Person.objects.using(schema_editor.connection.alias).filter(
            interview_decision=decision
        ).update(status=status, admission_type=admission_type)


class Migration(migrations.Migration):
    dependencies = [("school", "0025_homeworkassignment_global")]

    operations = [
        migrations.AddField(
            model_name="person",
            name="interview_decision",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pass_online", "ผ่านแบบ online"),
                    ("pass_onsite", "ผ่านแบบ onsite"),
                    ("fail", "ไม่ผ่าน"),
                ],
                max_length=20,
            ),
        ),
        migrations.RunPython(stage_unannounced_results, restore_staged_results),
    ]
