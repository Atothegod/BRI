from datetime import timedelta
from pathlib import PurePath

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import HomeworkAssignment, HomeworkSubmission, Person, Student, TeacherGroup


class HomeworkWorkspaceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="homework-admin", password="pass")
        self.teacher = User.objects.create_user(
            username="homework-teacher",
            nickname="มอส",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.group = TeacherGroup.objects.create(group_name="Moses", teacher=self.teacher)
        self.group.teachers.add(self.teacher)
        self.other_group = TeacherGroup.objects.create(group_name="Joshua")
        self.student = self.make_student("Homework", "Student", "Uhomeworkstudent", self.group)
        self.other_student = self.make_student("Other", "Student", "Uotherstudent", self.other_group)

    def make_student(self, first_name, last_name, line_user_id, group):
        person = Person.objects.create(
            first_name=first_name,
            last_name=last_name,
            line_user_id=line_user_id,
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        student.group = group
        student.save(update_fields=["group"])
        return student

    def set_line_student(self, student):
        session = self.client.session
        session["line_profile"] = {
            "line_user_id": student.person.line_user_id,
            "line_display_name": student.person.full_name,
            "line_picture_url": "",
            "verified": True,
        }
        session.save()

    def make_assignment(self, **kwargs):
        defaults = {
            "group": self.group,
            "title": "การบ้านครั้งที่ 1",
            "description": "เขียน Reflection จากบทเรียนอย่างน้อยหนึ่งหน้า",
            "due_date": timezone.localdate() + timedelta(days=7),
            "created_by": self.admin,
        }
        defaults.update(kwargs)
        return HomeworkAssignment.objects.create(**defaults)

    def test_school_admin_creates_assignment_for_group(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("school:admin_homework"), {
            "group": self.group.pk,
            "title": "  การบ้านครั้งที่ 1   ",
            "description": "รายละเอียดงานสำหรับกลุ่ม Moses",
            "due_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
        })

        self.assertRedirects(response, reverse("school:admin_homework"))
        assignment = HomeworkAssignment.objects.get()
        self.assertEqual(assignment.title, "การบ้านครั้งที่ 1")
        self.assertEqual(assignment.group, self.group)
        self.assertEqual(assignment.created_by, self.admin)

    def test_non_admin_cannot_open_admin_homework(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("school:admin_homework"))
        self.assertEqual(response.status_code, 403)

    def test_student_sees_assignment_card_and_detail(self):
        assignment = self.make_assignment()
        self.set_line_student(self.student)

        list_response = self.client.get(reverse("school:student_homework_upload"))
        detail_response = self.client.get(reverse("school:student_homework_detail", args=[assignment.pk]))

        self.assertContains(list_response, assignment.title)
        self.assertContains(list_response, "มอบหมายแล้ว")
        self.assertContains(detail_response, assignment.description)
        self.assertContains(detail_response, "Turn in")

    def test_student_cannot_open_assignment_from_another_group(self):
        assignment = self.make_assignment(group=self.other_group)
        self.set_line_student(self.student)
        response = self.client.get(reverse("school:student_homework_detail", args=[assignment.pk]))
        self.assertEqual(response.status_code, 404)

    def test_student_turns_in_file_and_teacher_dashboard_tracks_it(self):
        assignment = self.make_assignment()
        self.set_line_student(self.student)
        upload = SimpleUploadedFile("reflection.pdf", b"homework-content", content_type="application/pdf")

        response = self.client.post(
            reverse("school:student_homework_detail", args=[assignment.pk]),
            {"homework_file": upload, "student_note": "ส่งงานเรียบร้อยครับ"},
        )

        self.assertRedirects(response, reverse("school:student_homework_detail", args=[assignment.pk]))
        submission = HomeworkSubmission.objects.get(homework_assignment=assignment, student=self.student)
        self.assertEqual(submission.status, HomeworkSubmission.Status.SUBMITTED)
        self.assertEqual(submission.student_note, "ส่งงานเรียบร้อยครับ")
        uploaded_name = PurePath(submission.submission_file.name)
        self.assertTrue(uploaded_name.stem.startswith("reflection"))
        self.assertEqual(uploaded_name.suffix, ".pdf")

        self.client.force_login(self.teacher)
        teacher_response = self.client.get(reverse("school:teacher_dashboard"))
        self.assertContains(teacher_response, assignment.title)
        self.assertContains(teacher_response, "ส่งแล้ว 1")
        self.assertContains(teacher_response, "เปิดงาน")

    def test_turn_in_after_due_date_is_late(self):
        assignment = self.make_assignment(due_date=timezone.localdate() - timedelta(days=1))
        self.set_line_student(self.student)
        upload = SimpleUploadedFile("late.pdf", b"late-homework", content_type="application/pdf")

        self.client.post(
            reverse("school:student_homework_detail", args=[assignment.pk]),
            {"homework_file": upload},
        )

        submission = HomeworkSubmission.objects.get(homework_assignment=assignment, student=self.student)
        self.assertEqual(submission.status, HomeworkSubmission.Status.LATE)
