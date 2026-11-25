from django.db import migrations
from django.db.models import Exists, OuterRef


def recover_admin_payment_slips(apps, schema_editor):
    Student = apps.get_model("school", "Student")
    PaymentSlip = apps.get_model("school", "PaymentSlip")
    database = schema_editor.connection.alias
    slips = PaymentSlip.objects.using(database)
    matching_slip = slips.filter(student_id=OuterRef("pk"), image=OuterRef("payment_slip"))
    students = (
        Student.objects.using(database)
        .exclude(payment_slip="")
        .exclude(payment_slip__isnull=True)
        .filter(~Exists(matching_slip))
    )
    for student in students.iterator():
        if student.is_paid:
            status = "approved"
        elif student.admin_validation_status == "needs_fix":
            status = "needs_fix"
        else:
            status = "pending"
        slips.create(student_id=student.pk, image=student.payment_slip.name, status=status)


class Migration(migrations.Migration):
    dependencies = [("school", "0026_person_interview_decision")]

    operations = [migrations.RunPython(recover_admin_payment_slips, migrations.RunPython.noop)]
