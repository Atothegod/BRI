from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, AppointmentParticipant, Person, Student, TeacherGroup


class TeacherGroupAppointmentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.teacher = User.objects.create_user(
            username="appointment-teacher",
            nickname="นัด",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
            line_user_id="Uteacher1",
        )
        self.co_teacher = User.objects.create_user(
            username="appointment-co-teacher",
            nickname="ร่วมนัด",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
            line_user_id="Uteacher2",
        )
        self.group = TeacherGroup.objects.create(group_name="Moses", teacher=self.teacher)
        self.group.teachers.add(self.teacher, self.co_teacher)
        self.students = []
        for index in range(2):
            person = Person.objects.create(
                first_name=f"Student {index}",
                last_name="Moses",
                line_user_id=f"Ustudent{index}",
                status=Person.Status.PASSED,
            )
            student = Student.objects.get(person=person)
            student.group = self.group
            student.save(update_fields=["group"])
            self.students.append(student)

    @patch("school.views.send_line_push_message", return_value=True)
    def test_creating_group_appointment_adds_every_student_and_notifies_teachers(self, send_line):
        self.client.force_login(self.teacher)
        start = timezone.localtime(timezone.now() + timedelta(days=2))

        response = self.client.post(reverse("school:teacher_calendar"), {
            "group": self.group.pk,
            "title": "เรียนเสริม",
            "date": start.strftime("%Y-%m-%d"),
            "time": start.strftime("%H:%M"),
            "location": "ห้อง A",
        })

        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get(title="เรียนเสริม")
        self.assertEqual(
            set(appointment.participants.values_list("person_id", flat=True)),
            {student.person_id for student in self.students},
        )
        self.assertEqual(send_line.call_count, 2)
        teacher_message = send_line.call_args.args[1][0]
        self.assertNotIn("ยืนยันเข้าร่วม", str(teacher_message))
        self.assertIn("อาจารย์ไม่ต้องกดยืนยัน", str(teacher_message))
        self.assertEqual(len(self.client.session["teacher_appointment_send_queue"]), 2)

    def test_group_is_required(self):
        self.client.force_login(self.teacher)
        start = timezone.localtime(timezone.now() + timedelta(days=2))
        response = self.client.post(reverse("school:teacher_calendar"), {
            "title": "นัดไม่มีกลุ่ม",
            "date": start.strftime("%Y-%m-%d"),
            "time": start.strftime("%H:%M"),
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Appointment.objects.exists())
        self.assertContains(response, "กรุณาเลือกกลุ่มที่ต้องการนัด")

    def test_teacher_dashboard_shows_confirmation_totals(self):
        appointment = Appointment.objects.create(
            appointment_type=Appointment.Type.CLASS,
            title="นัดรวมกลุ่ม",
            starts_at=timezone.now() + timedelta(days=1),
            created_by=self.teacher,
        )
        AppointmentParticipant.objects.create(
            appointment=appointment,
            person=self.students[0].person,
            response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
        )
        AppointmentParticipant.objects.create(appointment=appointment, person=self.students[1].person)
        self.client.force_login(self.co_teacher)

        response = self.client.get(reverse("school:teacher_dashboard"))

        self.assertEqual(response.context["dashboard_appointments"][0].confirmed_count, 1)
        self.assertEqual(response.context["dashboard_appointments"][0].waiting_count, 1)
        self.assertContains(response, "นัดรวมกลุ่ม")
        self.assertContains(response, "ยืนยัน 1")
