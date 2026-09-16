from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Person, Student, TeacherGroup


class StudentGroupAssignmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="group-admin", password="test-password")
        self.teacher = User.objects.create_user(
            username="approved-teacher",
            first_name="Approved",
            last_name="Teacher",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.group = TeacherGroup.objects.create(teacher=self.teacher, group_name="กลุ่ม A")
        self.students = [self.make_student(f"Student {index}", paid=True) for index in range(2)]
        self.unpaid_student = self.make_student("Unpaid Student", paid=False)
        self.url = reverse("school:student_group_assignment")
        self.client.force_login(self.admin)

    def make_student(self, first_name, *, paid):
        person = Person.objects.create(
            first_name=first_name,
            last_name="Test",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        student.is_paid = paid
        student.save(update_fields=["is_paid"])
        return student

    def test_page_defaults_to_unassigned_paid_students_with_student_ids(self):
        assigned_student = self.students[1]
        assigned_student.group = self.group
        assigned_student.save(update_fields=["group"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/student_group_assignment.html")
        self.assertContains(response, self.students[0].student_id)
        self.assertNotContains(response, assigned_student.student_id)
        self.assertNotContains(response, self.unpaid_student.student_id)
        self.assertContains(response, "Approved Teacher")
        self.assertContains(response, 'class="assignment-steps"')
        self.assertContains(response, 'class="destination-group-option"')
        self.assertContains(response, 'id="assignment-review-dialog"')

    def test_superuser_can_assign_multiple_students_to_teacher_group(self):
        response = self.client.post(self.url, {
            "students": [student.pk for student in self.students],
            "group": self.group.pk,
        })

        self.assertRedirects(response, self.url)
        self.assertEqual(
            Student.objects.filter(pk__in=[student.pk for student in self.students], group=self.group).count(),
            2,
        )

    def test_spoofed_ineligible_student_is_rejected(self):
        response = self.client.post(self.url, {
            "students": [self.unpaid_student.pk],
            "group": self.group.pk,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "มีนักศึกษาที่ไม่ตรงเงื่อนไข")
        self.unpaid_student.refresh_from_db()
        self.assertIsNone(self.unpaid_student.group)

    def test_group_without_approved_teacher_is_not_assignable(self):
        User = get_user_model()
        pending_teacher = User.objects.create_user(
            username="pending-teacher",
            role=User.Role.TEACHER,
            is_teacher_approved=False,
        )
        pending_group = TeacherGroup.objects.create(teacher=pending_teacher, group_name="Pending Group")

        response = self.client.post(self.url, {
            "students": [self.students[0].pk],
            "group": pending_group.pk,
        })

        self.assertContains(response, "กลุ่มเรียนนี้ไม่พร้อมใช้งาน")
        self.students[0].refresh_from_db()
        self.assertIsNone(self.students[0].group)

    def test_filters_can_show_assigned_students(self):
        self.students[0].group = self.group
        self.students[0].save(update_fields=["group"])

        response = self.client.get(self.url, {
            "assignment": "assigned",
            "teacher": self.teacher.pk,
            "group": self.group.pk,
            "q": self.students[0].student_id,
        })

        self.assertContains(response, self.students[0].student_id)
        self.assertNotContains(response, self.students[1].student_id)

    def test_requires_superuser_and_uses_django_admin_login(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff", password="test-password", is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('admin:login')}?next={self.url}")

    def test_admin_index_links_to_assignment_page(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "จัดนักศึกษาเข้ากลุ่มผู้สอน")
        self.assertContains(response, self.url)
