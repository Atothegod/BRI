from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AttendanceRecord,
    AttendanceSession,
    HomeworkAssignment,
    HomeworkSubmission,
    Person,
    Student,
    TeacherGroup,
    TeacherStudentAssessment,
)


class AdminLearningDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="learning-admin", password="pass")
        self.teacher = User.objects.create_user(
            username="learning-teacher",
            nickname="ดูแล",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.group = TeacherGroup.objects.create(group_name="Moses", teacher=self.teacher)
        self.group.teachers.add(self.teacher)
        self.other_group = TeacherGroup.objects.create(group_name="Joshua")
        person = Person.objects.create(first_name="Learning", last_name="Student", nickname="เลิร์น", status=Person.Status.PASSED)
        self.student = Student.objects.get(person=person)
        self.student.group = self.group
        self.student.save(update_fields=["group"])

    def test_admin_sees_real_attendance_homework_and_manual_care(self):
        session = AttendanceSession.objects.create(title="บทเรียน 1", date=timezone.localdate(), created_by=self.admin)
        AttendanceRecord.objects.create(attendance_session=session, student=self.student, status=AttendanceRecord.Status.LATE)
        assignment = HomeworkAssignment.objects.create(
            group=self.group,
            title="งาน 1",
            due_date=timezone.localdate() + timedelta(days=1),
            created_by=self.admin,
        )
        HomeworkSubmission.objects.create(
            homework_assignment=assignment,
            student=self.student,
            status=HomeworkSubmission.Status.SUBMITTED,
        )
        TeacherStudentAssessment.objects.create(teacher=self.teacher, student=self.student, needs_care=True)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("school:admin_learning_dashboard"))

        self.assertEqual(response.status_code, 200)
        row = response.context["students"][0]
        self.assertEqual(row.late_count, 1)
        self.assertEqual(row.homework_submitted, 1)
        self.assertTrue(row.manual_care)
        self.assertTrue(row.needs_follow_up)
        self.assertContains(response, "💔 ครูระบุติดตาม")

    def test_group_filter_limits_students(self):
        other_person = Person.objects.create(first_name="Other", last_name="Student", status=Person.Status.PASSED)
        other_student = Student.objects.get(person=other_person)
        other_student.group = self.other_group
        other_student.save(update_fields=["group"])
        self.client.force_login(self.admin)

        response = self.client.get(reverse("school:admin_learning_dashboard"), {"group": self.group.pk})

        self.assertEqual(response.context["student_count"], 1)
        self.assertEqual(response.context["students"][0], self.student)

    def test_teacher_cannot_open_school_admin_learning_dashboard(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("school:admin_learning_dashboard"))
        self.assertEqual(response.status_code, 403)
