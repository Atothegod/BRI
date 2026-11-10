from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import AttendanceRecord, AttendanceSession, Person, Student, TeacherGroup
from .views import ATTENDANCE_SIGNING_SALT


@override_settings(LINE_LIFF_ENABLED=True, LINE_LIFF_ID="1234567890-Attendance")
class SchoolwideAttendanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="attendance-admin", password="pass")
        self.teacher = User.objects.create_user(
            username="attendance-teacher",
            nickname="เช็กชื่อ",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.other_teacher = User.objects.create_user(
            username="other-teacher",
            nickname="อื่น",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        self.group = TeacherGroup.objects.create(group_name="Moses", teacher=self.teacher)
        self.group.teachers.add(self.teacher)
        self.other_group = TeacherGroup.objects.create(group_name="Joshua", teacher=self.other_teacher)
        self.other_group.teachers.add(self.other_teacher)
        self.student = self.make_student("Student", "One", "Uattendance-one", self.group)
        self.other_student = self.make_student("Student", "Two", "Uattendance-two", self.other_group)

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

    def make_session(self, *, minutes_ago=0, ends_in_minutes=120):
        now = timezone.now()
        return AttendanceSession.objects.create(
            title="BRI Schoolwide Class",
            topic="Identity",
            date=timezone.localdate(),
            starts_at=now - timedelta(minutes=minutes_ago),
            ends_at=now + timedelta(minutes=ends_in_minutes),
            created_by=self.admin,
        )

    def set_line_profile(self, student):
        session = self.client.session
        session["line_profile"] = {
            "line_user_id": student.person.line_user_id,
            "line_display_name": student.person.full_name,
            "line_picture_url": "",
            "verified": True,
        }
        session.save()

    def check_in_url(self, attendance_session):
        token = signing.dumps({"session_id": attendance_session.pk}, salt=ATTENDANCE_SIGNING_SALT)
        return reverse("school:attendance_check_in", kwargs={"token": token})

    def test_school_admin_creates_one_schoolwide_class(self):
        self.client.force_login(self.admin)

        response = self.client.post(reverse("school:admin_attendance_qr"), {
            "title": "คาบรวม BRI",
            "topic": "ตัวตนที่แท้จริง",
            "date": timezone.localdate().isoformat(),
            "start_time": "09:00",
            "end_time": "12:00",
        })

        self.assertEqual(response.status_code, 200)
        attendance_session = AttendanceSession.objects.get(title="คาบรวม BRI")
        self.assertIsNone(attendance_session.group_id)
        self.assertEqual(attendance_session.created_by, self.admin)
        self.assertContains(response, "QR สำหรับทั้งโรงเรียน")
        self.assertContains(
            response,
            f"https://liff.line.me/1234567890-Attendance/attendance/check-in/",
        )
        self.assertContains(response, reverse("school:attendance_session_detail", args=[attendance_session.pk]))

    def test_scan_within_sixty_minutes_marks_present_for_any_group(self):
        attendance_session = self.make_session(minutes_ago=59)
        self.set_line_profile(self.other_student)

        response = self.client.get(self.check_in_url(attendance_session))

        record = AttendanceRecord.objects.get(attendance_session=attendance_session, student=self.other_student)
        self.assertEqual(record.status, AttendanceRecord.Status.PRESENT)
        self.assertIsNotNone(record.checked_in_at)
        self.assertContains(response, "เช็กชื่อเรียบร้อย")

    def test_scan_after_sixty_minutes_marks_late(self):
        attendance_session = self.make_session(minutes_ago=61)
        self.set_line_profile(self.student)

        response = self.client.get(self.check_in_url(attendance_session))

        record = AttendanceRecord.objects.get(attendance_session=attendance_session, student=self.student)
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)
        self.assertContains(response, "มาสาย")

    def test_schoolwide_checkin_updates_dashboard_without_student_group(self):
        self.student.group = None
        self.student.save(update_fields=["group"])
        attendance_session = self.make_session(minutes_ago=10)
        self.set_line_profile(self.student)

        check_in_response = self.client.get(self.check_in_url(attendance_session))
        dashboard_response = self.client.get(reverse("school:student_dashboard"))

        self.assertContains(check_in_response, "เช็กชื่อเรียบร้อย")
        self.assertEqual(dashboard_response.context["attendance_summary"]["present"], 1)
        self.assertEqual(dashboard_response.context["attendance_summary"]["total"], 1)
        self.assertEqual(len(dashboard_response.context["recent_attendance"]), 1)

    def test_repeat_scan_does_not_overwrite_manual_leave(self):
        attendance_session = self.make_session(minutes_ago=10)
        AttendanceRecord.objects.create(
            attendance_session=attendance_session,
            student=self.student,
            status=AttendanceRecord.Status.LEAVE,
            marked_by=self.teacher,
        )
        self.set_line_profile(self.student)

        response = self.client.get(self.check_in_url(attendance_session))

        record = AttendanceRecord.objects.get(attendance_session=attendance_session, student=self.student)
        self.assertEqual(record.status, AttendanceRecord.Status.LEAVE)
        self.assertIsNone(record.checked_in_at)
        self.assertContains(response, "ไม่เปลี่ยนสถานะจากการสแกนซ้ำ")

    def test_teacher_roster_only_contains_students_in_managed_groups(self):
        attendance_session = self.make_session()
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("school:attendance_session_detail", args=[attendance_session.pk]))

        self.assertContains(response, self.student.person.full_name)
        self.assertNotContains(response, self.other_student.person.full_name)

    def test_teacher_can_mark_non_checkin_student_absent_or_leave(self):
        attendance_session = self.make_session()
        self.client.force_login(self.teacher)
        url = reverse("school:attendance_session_detail", args=[attendance_session.pk])

        response = self.client.post(url, {"student": self.student.pk, "status": "leave"})

        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(attendance_session=attendance_session, student=self.student)
        self.assertEqual(record.status, AttendanceRecord.Status.LEAVE)
        self.assertEqual(record.marked_by, self.teacher)

    def test_teacher_cannot_overwrite_scanned_status(self):
        attendance_session = self.make_session()
        AttendanceRecord.objects.create(
            attendance_session=attendance_session,
            student=self.student,
            status=AttendanceRecord.Status.PRESENT,
            checked_in_at=timezone.now(),
        )
        self.client.force_login(self.teacher)

        response = self.client.post(
            reverse("school:attendance_session_detail", args=[attendance_session.pk]),
            {"student": self.student.pk, "status": "absent"},
        )

        self.assertEqual(response.status_code, 400)
        record = AttendanceRecord.objects.get(attendance_session=attendance_session, student=self.student)
        self.assertEqual(record.status, AttendanceRecord.Status.PRESENT)
