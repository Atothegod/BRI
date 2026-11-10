from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Person, Student, TeacherGroup


class TeacherGroupManagementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="structure-admin", password="pass")
        self.teacher_one = User.objects.create_user(
            username="teacher-one",
            email="one@example.com",
            nickname="หนึ่ง",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.teacher_two = User.objects.create_user(
            username="teacher-two",
            email="two@example.com",
            nickname="สอง",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.first_group = TeacherGroup.objects.create(group_name="Moses")
        self.second_group = TeacherGroup.objects.create(group_name="Joshua")
        self.first_group.teachers.add(self.teacher_one)
        self.first_group.teacher = self.teacher_one
        self.first_group.save(update_fields=["teacher"])
        self.url = reverse("school:teacher_group_management")
        self.client.force_login(self.admin)

    def test_admin_page_shows_hierarchy_and_multiple_teachers(self):
        self.first_group.teachers.add(self.teacher_two)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/teacher_group_management.html")
        self.assertContains(response, "ผังทีมผู้สอน")
        self.assertContains(response, "อาจารย์หนึ่ง")
        self.assertContains(response, "อาจารย์สอง")
        self.assertContains(response, 'data-teacher-board')
        self.assertContains(response, 'data-teacher-card', count=2)

    def test_admin_can_create_group(self):
        response = self.client.post(self.url, {"group_name": "  กลุ่ม Revelation  "})

        self.assertRedirects(response, self.url)
        self.assertTrue(TeacherGroup.objects.filter(group_name="กลุ่ม Revelation").exists())

    def test_ajax_move_is_exclusive_and_preserves_multiple_teachers(self):
        self.first_group.teachers.add(self.teacher_two)

        response = self.client.post(
            self.url,
            {"teacher": self.teacher_one.pk, "group": self.second_group.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(self.first_group.teachers.filter(pk=self.teacher_one.pk).exists())
        self.assertTrue(self.first_group.teachers.filter(pk=self.teacher_two.pk).exists())
        self.assertTrue(self.second_group.teachers.filter(pk=self.teacher_one.pk).exists())
        self.first_group.refresh_from_db()
        self.second_group.refresh_from_db()
        self.assertEqual(self.first_group.teacher, self.teacher_two)
        self.assertEqual(self.second_group.teacher, self.teacher_one)

    def test_pending_teacher_cannot_be_moved(self):
        User = get_user_model()
        pending = User.objects.create_user(
            username="pending-teacher",
            role=User.Role.TEACHER,
            is_teacher_approved=False,
        )

        response = self.client.post(
            self.url,
            {"teacher": pending.pk, "group": self.first_group.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_student_assignment_page_shows_group_teacher_student_hierarchy(self):
        person = Person.objects.create(first_name="Student", last_name="Hierarchy", status=Person.Status.PASSED)
        student = Student.objects.get(person=person)
        student.group = self.first_group
        student.save(update_fields=["group"])

        response = self.client.get(reverse("school:student_group_assignment"))

        self.assertContains(response, "TEACHING GROUP 01")
        self.assertContains(response, "อาจารย์หนึ่ง")
        self.assertContains(response, "นักศึกษาในกลุ่ม")
        self.assertContains(response, "Student Hierarchy")
        self.assertContains(response, "Assign")

    def test_requires_school_admin(self):
        self.client.force_login(self.teacher_one)
        self.assertEqual(self.client.get(self.url).status_code, 403)
