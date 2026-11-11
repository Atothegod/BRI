from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Person, Student, TeacherGroup, TeacherStudentAssessment


class TeacherStudentAssessmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create_user(
            username="care-teacher",
            nickname="แคร์",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.co_teacher = User.objects.create_user(
            username="co-care-teacher",
            nickname="ร่วมดูแล",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.outside_teacher = User.objects.create_user(
            username="outside-teacher",
            nickname="นอกกลุ่ม",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.group = TeacherGroup.objects.create(group_name="Moses", teacher=self.teacher)
        self.group.teachers.add(self.teacher, self.co_teacher)
        self.outside_group = TeacherGroup.objects.create(group_name="Joshua", teacher=self.outside_teacher)
        self.outside_group.teachers.add(self.outside_teacher)
        person = Person.objects.create(first_name="Care", last_name="Student", status=Person.Status.PASSED)
        self.student = Student.objects.get(person=person)
        self.student.group = self.group
        self.student.save(update_fields=["group"])

    def assessment_url(self):
        return reverse("school:teacher_student_assessment", args=[self.student.pk])

    def test_teacher_can_save_grade_comment_and_broken_heart(self):
        self.client.force_login(self.teacher)

        response = self.client.post(self.assessment_url(), {
            "grade": "B",
            "comment": "พัฒนาขึ้นมาก แต่ควรติดตามเรื่องการส่งงาน",
            "needs_care": "1",
        })

        self.assertEqual(response.status_code, 200)
        assessment = TeacherStudentAssessment.objects.get(teacher=self.teacher, student=self.student)
        self.assertEqual(assessment.grade, "B")
        self.assertEqual(assessment.comment, "พัฒนาขึ้นมาก แต่ควรติดตามเรื่องการส่งงาน")
        self.assertTrue(assessment.needs_care)
        self.assertTrue(response.json()["assessment"]["needs_care"])

    def test_assessments_are_separate_for_each_teacher(self):
        TeacherStudentAssessment.objects.create(
            teacher=self.teacher,
            student=self.student,
            grade="B",
            comment="ความเห็นคนแรก",
        )
        self.client.force_login(self.co_teacher)

        self.client.post(self.assessment_url(), {"grade": "A", "comment": "ความเห็นคนที่สอง"})

        self.assertEqual(TeacherStudentAssessment.objects.count(), 2)
        self.assertEqual(
            TeacherStudentAssessment.objects.get(teacher=self.teacher, student=self.student).comment,
            "ความเห็นคนแรก",
        )

    def test_teacher_outside_group_cannot_assess_student(self):
        self.client.force_login(self.outside_teacher)
        response = self.client.post(self.assessment_url(), {"grade": "A"})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(TeacherStudentAssessment.objects.exists())

    def test_invalid_grade_is_rejected(self):
        self.client.force_login(self.teacher)
        response = self.client.post(self.assessment_url(), {"grade": "Z"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(TeacherStudentAssessment.objects.exists())

    def test_broken_heart_appears_in_dashboard_attention(self):
        TeacherStudentAssessment.objects.create(
            teacher=self.teacher,
            student=self.student,
            grade="C",
            comment="ขอคุยเพิ่มเติม",
            needs_care=True,
        )
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("school:teacher_dashboard"))

        self.assertEqual(response.context["needs_attention_count"], 1)
        self.assertContains(response, "💔")
        self.assertContains(response, "ขอคุยเพิ่มเติม")
        self.assertContains(response, "บันทึกเกรดและความคิดเห็น")
