import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from .line import (
    build_interview_passed_flex_message,
    build_payment_approved_flex_message,
    notify_payment_approved,
)
from .models import Person, Student


@override_settings(PUBLIC_BASE_URL="https://bri.example", LINE_LIFF_ENABLED=False)
class LineMessageContentTests(SimpleTestCase):
    def setUp(self):
        self.person = Person(first_name="Test", last_name="Student", status=Person.Status.PASSED)
        self.student = Student(person=self.person, student_id="bri-9876")

    def rows(self, message):
        return {
            row["contents"][0]["text"]: row["contents"][1]
            for row in message["contents"]["body"]["contents"][1]["contents"]
        }

    def test_interview_types_and_payment_states(self):
        for admission, result in [(Person.AdmissionType.INTERVIEW, "ผ่านสัมภาษณ์"), (Person.AdmissionType.ONLINE, "ผ่านสัมภาษณ์ (ออนไลน์)")]:
            for paid, slip, status in [(False, "", "รอชำระเงิน"), (False, "slips/test.jpg", "รอตรวจสอบการชำระเงิน"), (True, "slips/test.jpg", "ชำระเรียบร้อย")]:
                with self.subTest(admission=admission, paid=paid, slip=slip):
                    self.person.admission_type = admission
                    self.student.is_paid = paid
                    self.student.payment_slip = slip
                    message = build_interview_passed_flex_message(self.person, self.student)
                    rows = self.rows(message)
                    self.assertEqual(message["contents"]["header"]["backgroundColor"], "#12271D")
                    self.assertEqual(message["contents"]["footer"]["backgroundColor"], "#F3F0E8")
                    self.assertEqual(rows["ผลการคัดเลือก"]["text"], result)
                    self.assertEqual(rows["สถานะการชำระเงิน"]["text"], status)
                    self.assertEqual(rows["สถานะการชำระเงิน"]["color"], "#425B46" if paid else "#A44928")
                    self.assertEqual(self.student.student_id in json.dumps(message), paid)
                    self.assertEqual("รหัสนักศึกษา" in rows, paid)

    def test_payment_confirmation_has_green_status_and_student_id(self):
        self.student.is_paid = True
        message = build_payment_approved_flex_message(self.person, self.student)
        rows = self.rows(message)
        self.assertEqual(message["contents"]["header"]["backgroundColor"], "#12271D")
        self.assertEqual(message["contents"]["footer"]["backgroundColor"], "#F3F0E8")
        self.assertEqual(rows["สถานะการชำระเงิน"]["text"], "ชำระเรียบร้อย")
        self.assertEqual(rows["สถานะการชำระเงิน"]["color"], "#425B46")
        self.assertEqual(rows["รหัสนักศึกษา"]["text"], self.student.student_id)
        self.assertIn("ยินดีด้วย", json.dumps(message, ensure_ascii=False))

    @patch("school.line.send_line_push_message")
    def test_unpaid_student_cannot_receive_payment_confirmation(self, send):
        self.assertFalse(notify_payment_approved(self.person, self.student))
        send.assert_not_called()
        with self.assertRaises(ValueError):
            build_payment_approved_flex_message(self.person, self.student)
