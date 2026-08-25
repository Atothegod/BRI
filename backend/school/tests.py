import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Person, Student, TeacherGroup


class PersonViewTests(TestCase):
    def valid_form_data(self):
        return {
            "first_name": "สมชาย",
            "last_name": "ใจดี",
            "nickname": "ชาย",
            "gender": "male",
            "date_of_birth": "1990-01-15",
            "phone": "0812345678",
            "email": "somchai@example.com",
            "line_id": "somchai.line",
            "line_user_id": "U1234567890",
            "line_display_name": "Somchai LINE",
            "line_picture_url": "https://example.com/line-picture.jpg",
            "occupation": "นักออกแบบ",
            "region": "central",
            "province": "กรุงเทพมหานคร",
            "district": "บางรัก",
            "sub_district": "สีลม",
            "address": "123 ถนนตัวอย่าง",
            "is_pastor": "false",
            "has_studied_bri": "true",
            "facebook_link": "https://facebook.com/somchai",
            "church": "คริสตจักรตัวอย่าง",
            "serving_position": "ทีมสื่อสาร",
            "mentor_name": "สมศรี ใจดี",
            "believer_years": "12",
            "goal": "ต้องการเติบโตในการรับใช้และเข้าใจของประทานมากขึ้น",
            "vision_calling": "อยากสร้างคนรุ่นใหม่ให้เติบโตอย่างมั่นคง",
            "privacy_consent": "true",
        }

    def test_registration_page_renders(self):
        response = self.client.get(reverse("school:registration"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/registration.html")
        self.assertContains(response, "ใบสมัครเรียน")
        self.assertContains(response, "เพศ")
        self.assertNotContains(response, "รูปโปรไฟล์")

    def test_valid_registration_creates_person(self):
        response = self.client.post(reverse("school:registration"), self.valid_form_data())

        self.assertRedirects(response, reverse("school:registration_success"))
        self.assertEqual(Person.objects.count(), 1)

        person = Person.objects.get()
        self.assertEqual(person.full_name, "สมชาย ใจดี")
        self.assertEqual(person.nickname, "ชาย")
        self.assertEqual(person.gender, "male")
        self.assertEqual(person.line_id, "somchai.line")
        self.assertEqual(person.line_user_id, "U1234567890")
        self.assertEqual(person.line_display_name, "Somchai LINE")
        self.assertIsNotNone(person.line_connected_at)
        self.assertEqual(person.status, Person.Status.IN_PROGRESS)
        self.assertFalse(person.extra_data["is_pastor"])
        self.assertTrue(person.extra_data["has_studied_bri"])

        success_response = self.client.get(reverse("school:registration_success"))
        self.assertContains(success_response, person.get_status_display())
        self.assertContains(success_response, f"#{person.pk}")

    def test_registration_can_receive_line_profile_from_query_string(self):
        response = self.client.get(
            reverse("school:registration"),
            {
                "line_user_id": "Uquery",
                "line_display_name": "Query LINE",
                "line_picture_url": "https://example.com/query.jpg",
            },
        )

        self.assertContains(response, 'value="Uquery"')

    def test_student_id_auto_increments(self):
        first_person = Person.objects.create(first_name="สมชาย", last_name="ใจดี")
        second_person = Person.objects.create(first_name="สมหญิง", last_name="ใจงาม")

        first_student = Student.objects.create(person=first_person)
        second_student = Student.objects.create(person=second_person)

        self.assertEqual(first_student.student_id, "bri-0001")
        self.assertEqual(second_student.student_id, "bri-0002")

    def test_passed_person_creates_student_with_payment_fields(self):
        person = Person.objects.create(first_name="สมชาย", last_name="ใจดี")

        person.status = Person.Status.PASSED
        person.save(update_fields=["status"])

        student = Student.objects.get(person=person)
        self.assertEqual(student.student_id, "bri-0001")
        self.assertFalse(student.is_paid)
        self.assertFalse(student.payment_slip)

    def test_success_page_requires_a_person_receipt(self):
        response = self.client.get(reverse("school:registration_success"))

        self.assertRedirects(response, reverse("school:registration"))


class AgentNotificationEndpointTests(TestCase):
    def test_notifications_endpoint_returns_empty_payload(self):
        response = self.client.get(
            reverse("school:agent_notifications", kwargs={"user_key": "user_scnhpmzh3"}),
            {"ca_number": "020000928740"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "user_key": "user_scnhpmzh3",
                "ca_number": "020000928740",
                "notifications": [],
            },
        )

    def test_latest_closed_loop_endpoint_returns_empty_payload(self):
        response = self.client.get(
            reverse(
                "school:latest_closed_loop_notification",
                kwargs={"user_key": "user_scnhpmzh3"},
            ),
            {"ca_number": "020000928740"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["latest_closed_loop"], None)
        self.assertEqual(response.json()["notifications"], [])


class TeacherFlowTests(TestCase):
    def test_teacher_signup_creates_teacher_user_and_group(self):
        response = self.client.post(
            reverse("school:teacher_register"),
            {
                "username": "teacher1",
                "email": "teacher@example.com",
                "first_name": "Teacher",
                "last_name": "One",
                "google_email": "teacher@gmail.com",
                "group_name": "กลุ่ม A",
                "grade_level": "รุ่น 1",
                "password1": "StrongPass12345",
                "password2": "StrongPass12345",
            },
        )

        self.assertRedirects(response, reverse("school:teacher_dashboard"))
        user = get_user_model().objects.get(username="teacher1")
        self.assertEqual(user.role, user.Role.TEACHER)
        self.assertEqual(user.google_email, "teacher@gmail.com")
        self.assertIsNone(user.google_connected_at)
        self.assertTrue(TeacherGroup.objects.filter(teacher=user, group_name="กลุ่ม A").exists())

    def test_teacher_dashboard_shows_only_students_in_teacher_groups(self):
        User = get_user_model()
        teacher = User.objects.create_user(username="teacher1", password="pass", role=User.Role.TEACHER)
        other_teacher = User.objects.create_user(
            username="teacher2",
            password="pass",
            role=User.Role.TEACHER,
        )
        group = TeacherGroup.objects.create(teacher=teacher, group_name="กลุ่ม A")
        other_group = TeacherGroup.objects.create(teacher=other_teacher, group_name="กลุ่ม B")
        visible_person = Person.objects.create(first_name="Visible", last_name="Student")
        hidden_person = Person.objects.create(first_name="Hidden", last_name="Student")
        Student.objects.create(person=visible_person, group=group)
        Student.objects.create(person=hidden_person, group=other_group)

        self.client.force_login(teacher)
        response = self.client.get(reverse("school:teacher_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Visible Student")
        self.assertNotContains(response, "Hidden Student")

    def test_student_payment_upload_page_hides_student_id_field(self):
        response = self.client.get(reverse("school:student_payment_upload"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "รหัสนักศึกษา")
        self.assertNotContains(response, 'name="student_id"')

    def test_student_payment_upload_requires_line_session(self):
        person = Person.objects.create(first_name="Paid", last_name="Student")
        student = Student.objects.create(person=person)
        slip = SimpleUploadedFile(
            "slip.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("school:student_payment_upload"),
            {
                "line_user_id": person.line_user_id or "Uspoofedpayment",
                "payment_slip": slip,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "กรุณาเปิดหน้านี้ผ่าน LINE")
        student.refresh_from_db()
        self.assertFalse(student.payment_slip)

    def test_student_payment_upload_uses_line_session(self):
        person = Person.objects.create(
            first_name="Line",
            last_name="Student",
            line_user_id="Ulinepayment",
            line_display_name="Line Student",
        )
        student = Student.objects.create(person=person)
        session = self.client.session
        session["line_profile"] = {
            "line_user_id": "Ulinepayment",
            "line_display_name": "Line Student",
            "line_picture_url": "",
            "verified": True,
        }
        session.save()
        slip = SimpleUploadedFile(
            "line-slip.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("school:student_payment_upload"),
            {"payment_slip": slip},
        )

        self.assertRedirects(response, reverse("school:student_payment_upload"))
        student.refresh_from_db()
        self.assertTrue(student.payment_slip.name.startswith("payment_slips/"))

    def test_person_knows_student_and_payment_status_through_line_account(self):
        person = Person.objects.create(
            first_name="Announce",
            last_name="Student",
            line_user_id="Uannounce",
            line_display_name="Announce LINE",
        )
        student = Student.objects.create(person=person, is_paid=True)

        self.assertEqual(person.line_name, "Announce LINE")
        self.assertEqual(person.student_code, student.student_id)
        self.assertTrue(person.has_paid)


class AnnouncementResultTests(TestCase):
    @override_settings(LINE_RETURN_URL="https://line.me/R/")
    def test_passed_line_account_sees_interview_passed_result(self):
        person = Person.objects.create(
            first_name="Passed",
            last_name="Person",
            line_user_id="Upassed",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)

        response = self.client.get(
            reverse("school:announcement_result"),
            {"line_user_id": "Upassed"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/announcement_result.html")
        self.assertContains(response, "ผ่านการสัมภาษณ์")
        self.assertContains(response, student.student_id)
        self.assertContains(response, 'href="https://line.me/R/"')

    def test_existing_student_is_treated_as_passed_result(self):
        person = Person.objects.create(
            first_name="Student",
            last_name="Only",
            line_user_id="Ustudent",
        )
        student = Student.objects.create(person=person)

        response = self.client.get(
            reverse("school:announcement_result"),
            {"line_user_id": "Ustudent"},
        )

        self.assertContains(response, "ผ่านการสัมภาษณ์")
        self.assertContains(response, student.student_id)

    def test_failed_line_account_sees_failed_result(self):
        Person.objects.create(
            first_name="Failed",
            last_name="Person",
            line_user_id="Ufailed",
            status=Person.Status.FAILED,
        )

        response = self.client.get(
            reverse("school:announcement_result"),
            {"line_user_id": "Ufailed"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ไม่ผ่านการสัมภาษณ์")
        self.assertContains(response, "กลับไปยัง LINE")

    def test_missing_line_account_shows_not_found_message(self):
        response = self.client.get(reverse("school:announcement_result"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ไม่พบข้อมูล LINE นี้")


@override_settings(
    LINE_LIFF_ALLOW_UNVERIFIED_PROFILE=True,
    LINE_LOGIN_CHANNEL_ID="",
    LINE_LIFF_ID="1234567890-AbCdEf",
)
class LiffFlowTests(TestCase):
    def sync_line_profile(self, user_id="Uliffuser", display_name="LIFF User"):
        return self.client.post(
            reverse("school:liff_profile_sync"),
            data=json.dumps(
                {
                    "profile": {
                        "userId": user_id,
                        "displayName": display_name,
                        "pictureUrl": "https://example.com/liff.jpg",
                    }
                }
            ),
            content_type="application/json",
        )

    def test_liff_profile_sync_stores_profile_in_session(self):
        response = self.sync_line_profile()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        session = self.client.session
        self.assertEqual(session["line_profile"]["line_user_id"], "Uliffuser")
        self.assertEqual(session["line_profile"]["line_display_name"], "LIFF User")

    def test_registration_uses_liff_session_profile_over_hidden_fields(self):
        self.sync_line_profile(user_id="Usession", display_name="Session LINE")
        data = PersonViewTests.valid_form_data(self)
        data["line_user_id"] = "Uspoofed"
        data["line_display_name"] = "Spoofed LINE"

        response = self.client.post(reverse("school:registration"), data)

        self.assertRedirects(response, reverse("school:registration_success"))
        person = Person.objects.get(line_user_id="Usession")
        self.assertEqual(person.line_display_name, "Session LINE")
        self.assertFalse(Person.objects.filter(line_user_id="Uspoofed").exists())

    def test_result_page_uses_liff_session_profile_for_pending_user(self):
        Person.objects.create(
            first_name="Pending",
            last_name="Person",
            line_user_id="Upendingliff",
            status=Person.Status.IN_PROGRESS,
        )
        self.sync_line_profile(user_id="Upendingliff", display_name="Pending LINE")

        response = self.client.get(reverse("school:announcement_result"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ยังไม่พบผลประกาศ")
        self.assertContains(response, "อยู่ระหว่างดำเนินการ")

    def test_liff_bridge_is_loaded_when_liff_id_is_configured(self):
        response = self.client.get(reverse("school:registration"))

        self.assertContains(response, "https://static.line-scdn.net/liff/edge/2/sdk.js")
        self.assertContains(response, "school/js/liff_bridge.js")
        self.assertContains(response, 'data-reload-on-sync="true"')

    @override_settings(LINE_RETURN_URL="https://line.me/R/nv/chat")
    def test_registered_line_account_sees_already_registered_page(self):
        person = Person.objects.create(
            first_name="Existing",
            last_name="Applicant",
            line_user_id="Uexisting",
            status=Person.Status.IN_PROGRESS,
        )
        self.sync_line_profile(user_id="Uexisting", display_name="Existing LINE")

        response = self.client.get(reverse("school:registration"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/already_registered.html")
        self.assertContains(response, "คุณสมัครเรียนแล้ว")
        self.assertContains(response, person.get_status_display())
        self.assertContains(response, 'href="https://line.me/R/nv/chat"')
        self.assertNotContains(response, "registration-form")

    def test_registered_student_sees_student_id_on_already_registered_page(self):
        person = Person.objects.create(
            first_name="Existing",
            last_name="Student",
            line_user_id="Uexistingstudent",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        self.sync_line_profile(user_id="Uexistingstudent", display_name="Existing Student")

        response = self.client.get(reverse("school:registration"))

        self.assertTemplateUsed(response, "school/already_registered.html")
        self.assertContains(response, student.student_id)

    def test_registration_endpoint_with_liff_state_renders_boot_page(self):
        response = self.client.get(
            reverse("school:registration"),
            {"liff.state": "/results/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/liff_boot.html")
        self.assertContains(response, "กำลังเปิดหน้าที่เลือก")
        self.assertContains(response, "liff_bridge.js")
        self.assertNotContains(response, "registration-form")

    def test_payment_liff_state_uses_boot_page_before_liff_redirect(self):
        response = self.client.get(
            reverse("school:registration"),
            {"liff.state": "/students/payment/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/liff_boot.html")
        self.assertContains(response, "กำลังเปิดหน้าที่เลือก")
        self.assertNotContains(response, "registration-form")
