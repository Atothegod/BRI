from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Person, Student


@override_settings(
    LINE_LIFF_ENABLED=True,
    LINE_LIFF_ID="1234567890-Main",
    LINE_DASHBOARD_LIFF_ID="1234567890-Dashboard",
    LINE_LIFF_ALLOW_UNVERIFIED_PROFILE=False,
)
class LineDashboardRouterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="line-admin", password="pass")
        self.teacher = User.objects.create_user(
            username="line-teacher", nickname="ไลน์", role=User.Role.TEACHER,
            is_teacher_approved=True,
        )

    def set_line_profile(self, user_id, *, verified=True):
        session = self.client.session
        session["line_profile"] = {
            "line_user_id": user_id,
            "line_display_name": "LINE User",
            "line_picture_url": "https://example.com/picture.jpg",
            "verified": verified,
        }
        session.save()

    def test_admin_page_has_one_shared_teacher_registration_link(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("school:teacher_group_management"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "คัดลอกลิงก์สมัคร Teacher")
        self.assertContains(response, "https://liff.line.me/1234567890-Dashboard/line/teachers/register/")

    def test_verified_line_can_create_pending_teacher(self):
        self.set_line_profile("Unewteacher")
        response = self.client.post(reverse("school:teacher_line_register"), {"nickname": "อาจารย์ เอก"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "สมัครบัญชีผู้สอนสำเร็จ")
        teacher = get_user_model().objects.get(line_user_id="Unewteacher")
        self.assertEqual(teacher.nickname, "เอก")
        self.assertEqual(teacher.role, teacher.Role.TEACHER)
        self.assertFalse(teacher.is_teacher_approved)
        self.assertEqual(teacher.line_display_name, "LINE User")
        self.assertEqual(int(self.client.session["_auth_user_id"]), teacher.pk)

    def test_registration_waits_for_liff_profile_sync(self):
        response = self.client.get(reverse("school:teacher_line_register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "กำลังยืนยันบัญชี LINE")
        self.assertContains(response, 'data-liff-id="1234567890-Dashboard"')
        self.assertContains(response, 'data-reload-on-sync="true"')

    def test_unverified_line_cannot_register_teacher(self):
        self.set_line_profile("Uunverified", verified=False)
        response = self.client.post(reverse("school:teacher_line_register"), {"nickname": "เอก"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(get_user_model().objects.filter(line_user_id="Uunverified").exists())

    def test_student_line_cannot_also_register_as_teacher(self):
        Person.objects.create(
            first_name="LINE", last_name="Student", line_user_id="Ustudentline",
            status=Person.Status.PASSED,
        )
        self.set_line_profile("Ustudentline")
        response = self.client.post(reverse("school:teacher_line_register"), {"nickname": "เอก"})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, "LINE นี้ผูกกับบัญชีประเภทอื่นแล้ว", status_code=409)
        self.assertFalse(get_user_model().objects.filter(line_user_id="Ustudentline").exists())

    def test_existing_teacher_registration_link_opens_teacher_dashboard(self):
        self.teacher.line_user_id = "Uteacherline"
        self.teacher.save(update_fields=["line_user_id"])
        self.set_line_profile("Uteacherline")
        response = self.client.get(reverse("school:teacher_line_register"))
        self.assertRedirects(response, reverse("school:teacher_dashboard"), fetch_redirect_response=False)

    def test_dashboard_router_sends_connected_teacher_to_teacher_dashboard(self):
        self.teacher.line_user_id = "Uteacherline"
        self.teacher.save(update_fields=["line_user_id"])
        self.set_line_profile("Uteacherline")
        response = self.client.get(reverse("school:line_dashboard_router"))
        self.assertRedirects(response, reverse("school:teacher_dashboard"), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.teacher.pk)

    def test_dashboard_router_sends_student_to_student_dashboard(self):
        person = Person.objects.create(
            first_name="LINE", last_name="Student", line_user_id="Ustudentline", status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        student.is_active = True
        student.save(update_fields=["is_active"])
        self.set_line_profile("Ustudentline")
        response = self.client.get(reverse("school:line_dashboard_router"))
        self.assertRedirects(response, reverse("school:student_dashboard"), fetch_redirect_response=False)

    def test_unknown_line_user_goes_to_existing_registration(self):
        self.set_line_profile("Unewperson")
        response = self.client.get(reverse("school:line_dashboard_router"))
        self.assertRedirects(response, reverse("school:registration"), fetch_redirect_response=False)

    def test_router_waits_for_liff_profile_sync(self):
        response = self.client.get(reverse("school:line_dashboard_router"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "กำลังตรวจสอบบัญชี LINE")
        self.assertContains(response, 'data-reload-on-sync="true"')
