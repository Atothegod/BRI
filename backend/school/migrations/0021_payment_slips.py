from django.db import migrations, models
import django.db.models.deletion


def migrate_existing_slips(apps, schema_editor):
    Student = apps.get_model("school", "Student")
    PaymentSlip = apps.get_model("school", "PaymentSlip")
    for student in Student.objects.exclude(payment_slip="").exclude(payment_slip__isnull=True):
        PaymentSlip.objects.create(
            student=student,
            image=student.payment_slip.name,
            status="approved" if student.is_paid else "pending",
        )


class Migration(migrations.Migration):
    dependencies = [("school", "0020_reformat_student_ids")]

    operations = [
        migrations.CreateModel(
            name="PaymentSlip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("image", models.ImageField(upload_to="payment_slips/")),
                ("status", models.CharField(choices=[("pending", "รอตรวจ"), ("approved", "ยืนยันแล้ว"), ("needs_fix", "ต้องแก้ไข")], default="pending", max_length=20)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payment_slips", to="school.student")),
            ],
            options={"ordering": ("created_at", "pk")},
        ),
        migrations.RunPython(migrate_existing_slips, migrations.RunPython.noop),
    ]
