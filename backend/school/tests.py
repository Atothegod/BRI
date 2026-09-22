import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from allauth.socialaccount.models import SocialAccount, SocialLogin

from accounts.adapters import TeacherGoogleSocialAccountAdapter

from .admin import BRIStudyHistoryFilter, CountryCodeFilter, PersonAdmin
from .models import (
    AttendanceRecord,
    AttendanceSession,
    HomeworkAssignment,
    HomeworkSubmission,
    Person,
    Student,
    TeacherGroup,
)


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
            "line_user_id": "U1234567890",
            "line_display_name": "Somchai LINE",
            "line_picture_url": "https://example.com/line-picture.jpg",
            "occupation": "นักออกแบบ",
            "region": "central",
            "province": "กรุงเทพมหานคร",
            "district": "เขตบางรัก",
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
        self.assertContains(response, "data-language-switch")
        self.assertContains(response, 'data-language-option="en"')
        self.assertContains(response, "data-country-data-url")
        self.assertContains(response, "data-country-search")
        self.assertContains(response, "data-foreign-address")
        self.assertContains(response, "เพศ")
        self.assertContains(response, "data-address-data-url")
        self.assertContains(response, "data-date-mask")
        self.assertContains(response, 'placeholder="วว/ดด/ปปปป"')
        self.assertContains(response, "data-address-province")
        self.assertContains(response, "data-address-province-suggestions")
        self.assertContains(response, 'placeholder="พิมพ์ชื่อจังหวัด"')
        self.assertContains(response, 'role="combobox"')
        self.assertContains(response, "data-address-district")
        self.assertContains(response, "data-address-district-suggestions")
        self.assertContains(response, 'placeholder="พิมพ์ชื่ออำเภอ / เขต"')
        self.assertContains(response, "data-address-subdistrict")
        self.assertContains(response, "data-address-subdistrict-suggestions")
        self.assertContains(response, 'placeholder="พิมพ์ชื่อตำบล / แขวง"')
        self.assertContains(response, 'value="eastern"')
        self.assertContains(response, "ตะวันออก")
        self.assertContains(response, 'value="western"')
        self.assertContains(response, "ตะวันตก")
        self.assertNotContains(response, "LINE ID")
        self.assertNotContains(response, 'value="unspecified"')
        self.assertNotContains(response, "รูปโปรไฟล์")

    def test_valid_registration_creates_person(self):
        response = self.client.post(reverse("school:registration"), self.valid_form_data())

        self.assertRedirects(response, reverse("school:registration_success"))
        self.assertEqual(Person.objects.count(), 1)

        person = Person.objects.get()
        self.assertEqual(person.full_name, "สมชาย ใจดี")
        self.assertEqual(person.nickname, "ชาย")
        self.assertEqual(person.gender, "male")
        self.assertEqual(person.line_user_id, "U1234567890")
        self.assertEqual(person.line_display_name, "Somchai LINE")
        self.assertIsNotNone(person.line_connected_at)
        self.assertEqual(person.status, Person.Status.IN_PROGRESS)
        self.assertEqual(person.extra_data["preferred_language"], "th")
        self.assertEqual(person.extra_data["country_code"], "TH")
        self.assertEqual(person.extra_data["country_name_en"], "Thailand")
        self.assertEqual(person.extra_data["country_name_th"], "ไทย")
        self.assertEqual(person.extra_data["address_th"]["province"], "กรุงเทพมหานคร")
        self.assertEqual(person.extra_data["address_en"], {})
        self.assertFalse(person.extra_data["is_pastor"])
        self.assertTrue(person.extra_data["has_studied_bri"])
        self.assertEqual(person.extra_data["district"], "เขตบางรัก")

        success_response = self.client.get(reverse("school:registration_success"))
        self.assertContains(success_response, person.get_status_display())
        self.assertNotContains(success_response, "รหัสข้อมูล")
        self.assertContains(success_response, "#clock")
        self.assertContains(success_response, "รอตรวจสอบข้อมูลของคุณ")
        self.assertContains(
            success_response,
            "รอนัดหมายสัมภาษณ์ สถานที่ คริสตจักรไบร์ทโรแมนซ์",
        )
        self.assertContains(success_response, "ประกาศผลผู้ที่ผ่านสัมภาษณ์")
        self.assertContains(success_response, "ยืนยันการเข้าเรียน ด้วยการชำระค่าเทอม")
        self.assertContains(success_response, "รับรหัสนักเรียนรอปฐมนิเทศน์")

    def test_registration_accepts_buddhist_birth_year(self):
        form_data = self.valid_form_data()
        form_data["date_of_birth"] = "15/01/2533"

        self.client.post(reverse("school:registration"), form_data)

        person = Person.objects.get()
        self.assertEqual(person.date_of_birth.isoformat(), "1990-01-15")

    def test_registration_accepts_compact_buddhist_birth_date(self):
        form_data = self.valid_form_data()
        form_data["date_of_birth"] = "15012533"

        self.client.post(reverse("school:registration"), form_data)

        person = Person.objects.get()
        self.assertEqual(person.date_of_birth.isoformat(), "1990-01-15")

    def test_registration_normalizes_address_prefixes(self):
        form_data = self.valid_form_data()
        form_data["district"] = "บางรัก"
        form_data["sub_district"] = "แขวงสีลม"

        response = self.client.post(reverse("school:registration"), form_data)

        self.assertRedirects(response, reverse("school:registration_success"))
        person = Person.objects.get()
        self.assertEqual(person.extra_data["district"], "เขตบางรัก")
        self.assertEqual(person.extra_data["sub_district"], "สีลม")

    def test_registration_rejects_invalid_address_values(self):
        form_data = self.valid_form_data()
        form_data["district"] = "เขตไม่มีจริง"

        response = self.client.post(reverse("school:registration"), form_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "กรุณาเลือกอำเภอ / เขตจากรายการ")
        self.assertEqual(Person.objects.count(), 0)

    def test_foreign_registration_skips_thai_address_validation(self):
        form_data = self.valid_form_data()
        form_data.update(
            {
                "preferred_language": "en",
                "country_code": "US",
                "country_name_en": "United States",
                "country_name_th": "สหรัฐอเมริกา",
                "region": "",
                "province": "",
                "district": "",
                "sub_district": "",
                "address": "",
                "address_line": "123 Main Street",
                "city": "Los Angeles",
                "state_province": "California",
                "postal_code": "90001",
            }
        )

        response = self.client.post(reverse("school:registration"), form_data)

        self.assertRedirects(response, reverse("school:registration_success"))
        person = Person.objects.get()
        self.assertEqual(person.extra_data["preferred_language"], "en")
        self.assertEqual(person.extra_data["country_code"], "US")
        self.assertEqual(person.extra_data["country_name_en"], "United States")
        self.assertEqual(person.extra_data["country_name_th"], "สหรัฐอเมริกา")
        self.assertEqual(person.extra_data["address_th"], {})
        self.assertEqual(person.extra_data["address_en"]["city"], "Los Angeles")
        self.assertEqual(person.extra_data["address_en"]["state_province"], "California")

    def test_foreign_registration_requires_address_and_city(self):
        form_data = self.valid_form_data()
        form_data.update(
            {
                "country_code": "GB",
                "country_name_en": "United Kingdom",
                "region": "",
                "province": "",
                "district": "",
                "sub_district": "",
                "address": "",
                "address_line": "",
                "city": "",
            }
        )

        response = self.client.post(reverse("school:registration"), form_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "กรุณากรอกที่อยู่")
        self.assertContains(response, "กรุณากรอกเมือง")

    def test_registration_rejects_unknown_country_name_without_fallback(self):
        form_data = self.valid_form_data()
        form_data.update(
            {
                "country_code": "",
                "country_name_en": "Uni",
                "country_name_th": "",
            }
        )

        response = self.client.post(reverse("school:registration"), form_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "กรุณาเลือกประเทศจากรายการ")
        self.assertEqual(Person.objects.count(), 0)
        self.assertEqual(Person.objects.count(), 0)

    def test_person_admin_exposes_extra_data_display_and_filters(self):
        person = Person.objects.create(
            first_name="Country",
            last_name="Applicant",
            extra_data={
                "country_code": "US",
                "country_name_en": "United States",
                "has_studied_bri": True,
                "goal": "อยากเติบโตในของประทาน",
                "vision_calling": "รับใช้คนรุ่นใหม่",
            },
        )
        Person.objects.create(
            first_name="New",
            last_name="Applicant",
            extra_data={"has_studied_bri": False},
        )
        Person.objects.create(first_name="Unknown", last_name="Applicant")
        model_admin = PersonAdmin(Person, admin.site)

        self.assertIn("applicant_display", model_admin.list_display)
        self.assertIn("contact_display", model_admin.list_display)
        self.assertIn("line_account_display", model_admin.list_display)
        self.assertNotIn("line_user_id", model_admin.list_display)
        self.assertNotIn("admission_type_display", model_admin.list_display)
        self.assertNotIn("student_code_display", model_admin.list_display)
        self.assertNotIn("paid_display", model_admin.list_display)
        self.assertEqual(model_admin.ordering, ("-created_at", "-id"))
        self.assertEqual(model_admin.country_display(person), "United States")
        self.assertEqual(model_admin.studied_bri_display(person), "เคย")
        self.assertEqual(model_admin.goal_display(person), "อยากเติบโตในของประทาน")
        self.assertEqual(model_admin.vision_calling_display(person), "รับใช้คนรุ่นใหม่")
        self.assertIn(CountryCodeFilter, model_admin.list_filter)
        self.assertIn(BRIStudyHistoryFilter, model_admin.list_filter)

        request = RequestFactory().get("/admin/school/person/", {"studied_bri": "yes"})
        filter_spec = BRIStudyHistoryFilter(request, request.GET.copy(), Person, model_admin)
        self.assertEqual(list(filter_spec.queryset(request, Person.objects.all())), [person])

    def test_person_admin_display_prioritizes_nickname(self):
        person = Person.objects.create(
            first_name="Somchai",
            last_name="Applicant",
            nickname="ชาย",
            phone="0812345678",
            email="somchai@example.com",
            line_user_id="Uadminline",
            line_display_name="Somchai LINE",
        )
        model_admin = PersonAdmin(Person, admin.site)

        applicant_html = str(model_admin.applicant_display(person))
        contact_html = str(model_admin.contact_display(person))
        line_html = str(model_admin.line_account_display(person))

        self.assertIn("ชาย", applicant_html)
        self.assertIn("Somchai Applicant", applicant_html)
        self.assertIn("0812345678", contact_html)
        self.assertIn("somchai@example.com", contact_html)
        self.assertIn("Somchai LINE", line_html)
        self.assertIn("เชื่อมต่อแล้ว", line_html)

    def test_registration_allows_blank_mentor_name(self):
        form_data = self.valid_form_data()
        form_data["mentor_name"] = ""

        response = self.client.post(reverse("school:registration"), form_data)

        self.assertRedirects(response, reverse("school:registration_success"))
        self.assertEqual(Person.objects.get().extra_data["mentor_name"], "")

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
        self.assertEqual(person.admission_type, Person.AdmissionType.INTERVIEW)

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


@override_settings(
    LINE_ANNOUNCEMENT_LIFF_URL="https://liff.line.me/2011088039-52ryg2t9",
    LINE_PAYMENT_LIFF_URL="https://liff.line.me/2011088039-wZDRAbFk",
)
class LineProactiveNotificationTests(TestCase):
    @override_settings(
        LINE_MESSAGING_CHANNEL_ACCESS_TOKEN="line-token",
        PUBLIC_BASE_URL="https://bri.example",
    )
    @patch("school.line.request.urlopen")
    def test_passing_interview_creates_student_without_line_push(self, mock_urlopen):
        person = Person.objects.create(
            first_name="Notify",
            last_name="Passed",
            line_user_id="Unotifypass",
        )

        person.status = Person.Status.PASSED
        person.save(update_fields=["status"])

        student = Student.objects.get(person=person)
        self.assertFalse(mock_urlopen.called)
        person.refresh_from_db()
        self.assertNotIn("line_notifications", person.extra_data)
        self.assertTrue(student.student_id)

    @override_settings(
        LINE_MESSAGING_CHANNEL_ACCESS_TOKEN="line-token",
        PUBLIC_BASE_URL="https://bri.example",
    )
    @patch("school.line.request.urlopen")
    def test_payment_approval_pushes_student_id_to_line_user(self, mock_urlopen):
        with self.settings(LINE_MESSAGING_CHANNEL_ACCESS_TOKEN=""):
            person = Person.objects.create(
                first_name="Notify",
                last_name="Paid",
                line_user_id="Unotifypaid",
                status=Person.Status.PASSED,
            )
        student = Student.objects.get(person=person)

        student.is_paid = True
        student.save(update_fields=["is_paid"])

        self.assertTrue(mock_urlopen.called)
        line_request = mock_urlopen.call_args.args[0]
        payload = json.loads(line_request.data.decode("utf-8"))
        self.assertEqual(payload["to"], "Unotifypaid")
        self.assertEqual(payload["messages"][0]["type"], "flex")
        self.assertIn("ยืนยันการชำระเงิน", payload["messages"][0]["altText"])
        self.assertIn(student.student_id, json.dumps(payload["messages"][0], ensure_ascii=False))
        person.refresh_from_db()
        self.assertIn("payment_approved", person.extra_data["line_notifications"])


class TeacherFlowTests(TestCase):
    @override_settings(GOOGLE_OAUTH_ENABLED=True)
    def test_teacher_login_shows_google_oauth_button(self):
        response = self.client.get(reverse("school:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, reverse("google_login"))
        self.assertContains(response, "อีเมล")
        self.assertNotContains(response, "ชื่อผู้ใช้")
        self.assertContains(response, 'width="18" height="18"')
        self.assertContains(response, "school/css/teacher_auth.css")

    @override_settings(GOOGLE_OAUTH_ENABLED=True)
    def test_teacher_register_shows_google_oauth_button(self):
        response = self.client.get(reverse("school:teacher_register"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, reverse("google_login"))
        self.assertContains(response, "ชื่อเล่น")
        self.assertNotContains(response, "ชื่อผู้ใช้")
        self.assertNotContains(response, 'name="username"')

    def test_allauth_login_and_signup_redirect_to_teacher_pages(self):
        login_response = self.client.get("/accounts/login/")
        signup_response = self.client.get("/accounts/signup/")

        self.assertRedirects(login_response, reverse("school:login"))
        self.assertRedirects(signup_response, reverse("school:teacher_register"))

    def test_google_social_signup_populates_pending_teacher(self):
        request = RequestFactory().get(reverse("school:login"))
        User = get_user_model()
        sociallogin = SocialLogin(
            user=User(),
            account=SocialAccount(
                provider="google",
                uid="google-123",
                extra_data={"email": "teacher.google@example.com"},
            ),
        )

        user = TeacherGoogleSocialAccountAdapter().populate_user(
            request,
            sociallogin,
            {
                "email": "teacher.google@example.com",
                "first_name": "Google",
                "last_name": "Teacher",
            },
        )

        self.assertEqual(user.role, user.Role.TEACHER)
        self.assertFalse(user.is_teacher_approved)
        self.assertEqual(user.email, "teacher.google@example.com")
        self.assertEqual(user.google_email, "teacher.google@example.com")
        self.assertIsNotNone(user.google_connected_at)

    def test_google_social_login_matches_existing_teacher_google_email(self):
        request = RequestFactory().get(reverse("school:login"))
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher-google",
            email="teacher@example.com",
            password="pass",
            role=User.Role.TEACHER,
            google_email="teacher.google@example.com",
            is_teacher_approved=True,
        )
        sociallogin = SocialLogin(
            user=User(),
            account=SocialAccount(
                provider="google",
                uid="google-123",
                extra_data={"email": "TEACHER.GOOGLE@example.com"},
            ),
        )

        TeacherGoogleSocialAccountAdapter().pre_social_login(request, sociallogin)

        self.assertEqual(sociallogin.user, teacher)
        teacher.refresh_from_db()
        self.assertEqual(teacher.google_email, "teacher.google@example.com")
        self.assertIsNotNone(teacher.google_connected_at)
        self.assertTrue(teacher.is_teacher_approved)

    def test_teacher_signup_creates_pending_teacher_user(self):
        response = self.client.post(
            reverse("school:teacher_register"),
            {
                "email": "teacher@example.com",
                "nickname": "อ.เอก",
                "password1": "StrongPass12345",
                "password2": "StrongPass12345",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('school:login')}?teacher_status=registered_pending",
        )
        user = get_user_model().objects.get(username="teacher@example.com")
        self.assertEqual(user.role, user.Role.TEACHER)
        self.assertEqual(user.email, "teacher@example.com")
        self.assertEqual(user.nickname, "อ.เอก")
        self.assertEqual(user.google_email, "")
        self.assertIsNone(user.google_connected_at)
        self.assertFalse(user.is_teacher_approved)
        self.assertIsNone(user.teacher_approved_at)
        self.assertTrue(
            TeacherGroup.objects.filter(teacher=user, group_name="อ.เอก", is_active=True).exists()
        )

    def test_registered_pending_teacher_sees_login_notice(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher1",
            email="teacher@example.com",
            password="StrongPass12345",
            role=User.Role.TEACHER,
            is_teacher_approved=False,
        )
        self.client.force_login(teacher)

        response = self.client.get(
            f"{reverse('school:login')}?teacher_status=registered_pending"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ลงทะเบียนเรียบร้อยแล้ว")
        self.assertContains(response, "กำลังรอผู้ดูแลระบบอนุมัติ")

    def test_teacher_can_login_with_email_and_password(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher1",
            email="teacher@example.com",
            password="StrongPass12345",
            role=User.Role.TEACHER,
            is_teacher_approved=False,
        )

        response = self.client.post(
            reverse("school:login"),
            {
                "username": "teacher@example.com",
                "password": "StrongPass12345",
            },
        )

        self.assertRedirects(
            response,
            reverse("school:post_login_redirect"),
            fetch_redirect_response=False,
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), teacher.pk)

    def test_unapproved_teacher_login_flow_returns_to_login_with_notice(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher1",
            email="teacher@example.com",
            password="StrongPass12345",
            role=User.Role.TEACHER,
            is_teacher_approved=False,
        )

        response = self.client.post(
            reverse("school:login"),
            {
                "username": "teacher@example.com",
                "password": "StrongPass12345",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [
                (reverse("school:post_login_redirect"), 302),
                (f"{reverse('school:login')}?teacher_status=pending", 302),
            ],
        )
        self.assertEqual(int(self.client.session["_auth_user_id"]), teacher.pk)
        self.assertContains(response, "บัญชีผู้สอนยังไม่อนุมัติ")

    def test_approved_teacher_post_login_redirects_to_teacher_dashboard(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher1",
            password="pass",
            role=User.Role.TEACHER,
            is_staff=True,
            is_teacher_approved=True,
        )

        self.client.force_login(teacher)
        response = self.client.get(reverse("school:post_login_redirect"))

        self.assertRedirects(response, reverse("school:teacher_dashboard"))

    def test_approved_teacher_login_flow_reaches_teacher_dashboard(self):
        User = get_user_model()
        User.objects.create_user(
            username="teacher1",
            email="teacher@example.com",
            password="StrongPass12345",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )

        response = self.client.post(
            reverse("school:login"),
            {
                "username": "teacher@example.com",
                "password": "StrongPass12345",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [
                (reverse("school:post_login_redirect"), 302),
                (reverse("school:teacher_dashboard"), 302),
            ],
        )
        self.assertContains(response, "นักเรียนในกลุ่มของคุณ")

    def test_school_admin_login_flow_reaches_teacher_dashboard(self):
        User = get_user_model()
        User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="StrongPass12345",
        )

        response = self.client.post(
            reverse("school:login"),
            {
                "username": "admin",
                "password": "StrongPass12345",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [
                (reverse("school:post_login_redirect"), 302),
                (reverse("school:teacher_dashboard"), 302),
            ],
        )
        self.assertContains(response, "นักเรียนในกลุ่มของคุณ")

    def test_teacher_dashboard_requires_admin_approval(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher1",
            password="pass",
            role=User.Role.TEACHER,
            is_teacher_approved=False,
        )

        self.client.force_login(teacher)
        response = self.client.get(reverse("school:teacher_dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('school:login')}?teacher_status=pending",
        )

    def test_teacher_dashboard_shows_only_students_in_teacher_groups(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="teacher1",
            password="pass",
            role=User.Role.TEACHER,
            nickname="อ.เอก",
            is_teacher_approved=True,
        )
        other_teacher = User.objects.create_user(
            username="teacher2",
            password="pass",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
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
        self.assertTemplateUsed(response, "school/teacher_dashboard_base.html")
        self.assertContains(response, "สวัสดี อ.เอก")
        self.assertNotContains(response, "teacher1")
        self.assertContains(response, "Visible Student")
        self.assertNotContains(response, "Hidden Student")

    def test_teacher_dashboard_calculates_attendance_and_homework_percentages(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="metrics-teacher",
            password="pass",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        group = TeacherGroup.objects.create(teacher=teacher, group_name="Metrics Group")
        person = Person.objects.create(first_name="Metric", last_name="Student")
        student = Student.objects.create(person=person, group=group)

        first_session = AttendanceSession.objects.create(group=group, date=timezone.localdate())
        second_session = AttendanceSession.objects.create(
            group=group,
            date=timezone.localdate() - timedelta(days=7),
        )
        AttendanceRecord.objects.create(
            attendance_session=first_session,
            student=student,
            status=AttendanceRecord.Status.PRESENT,
        )
        AttendanceRecord.objects.create(
            attendance_session=second_session,
            student=student,
            status=AttendanceRecord.Status.ABSENT,
        )

        first_assignment = HomeworkAssignment.objects.create(
            group=group,
            title="First assignment",
            due_date=timezone.localdate() + timedelta(days=3),
        )
        HomeworkAssignment.objects.create(
            group=group,
            title="Second assignment",
            due_date=timezone.localdate() + timedelta(days=5),
        )
        HomeworkSubmission.objects.create(
            homework_assignment=first_assignment,
            student=student,
            status=HomeworkSubmission.Status.SUBMITTED,
        )

        self.client.force_login(teacher)
        response = self.client.get(reverse("school:teacher_dashboard"))

        dashboard_student = response.context["students"][0]
        self.assertEqual(dashboard_student.attendance_percent, 50)
        self.assertEqual(dashboard_student.homework_percent, 50)
        self.assertTrue(dashboard_student.needs_attention)
        self.assertEqual(response.context["average_attendance"], 50)
        self.assertEqual(response.context["average_homework"], 50)
        self.assertTrue(response.context["has_learning_data"])
        self.assertEqual(response.context["attention_students"][0].pk, student.pk)
        self.assertEqual(response.context["dashboard_groups"][0].dashboard_attendance, 50)
        self.assertEqual(response.context["dashboard_groups"][0].dashboard_homework, 50)
        self.assertEqual(response.context["dashboard_groups"][0].dashboard_attention_count, 1)
        self.assertContains(response, 'id="teacher-tab-overview"')
        self.assertContains(response, 'class="teacher-health-track"')

    def test_teacher_group_filter_cannot_select_another_teachers_group(self):
        User = get_user_model()
        teacher = User.objects.create_user(
            username="owner-teacher",
            password="pass",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        other_teacher = User.objects.create_user(
            username="other-owner",
            password="pass",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        own_group = TeacherGroup.objects.create(teacher=teacher, group_name="Own Group")
        other_group = TeacherGroup.objects.create(teacher=other_teacher, group_name="Private Group")
        Student.objects.create(
            person=Person.objects.create(first_name="Own", last_name="Student"),
            group=own_group,
        )
        Student.objects.create(
            person=Person.objects.create(first_name="Private", last_name="Student"),
            group=other_group,
        )

        self.client.force_login(teacher)
        response = self.client.get(
            reverse("school:teacher_dashboard"),
            {"group": other_group.pk},
        )

        self.assertIsNone(response.context["selected_group"])
        self.assertContains(response, "Own Student")
        self.assertNotContains(response, "Private Student")

    def test_admin_overview_dashboard_shows_school_summary(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass",
        )
        approved_teacher = User.objects.create_user(
            username="approved-teacher",
            password="pass",
            role=User.Role.TEACHER,
            is_teacher_approved=True,
        )
        User.objects.create_user(
            username="pending-teacher",
            email="pending@example.com",
            password="pass",
            role=User.Role.TEACHER,
        )
        group = TeacherGroup.objects.create(teacher=approved_teacher, group_name="กลุ่ม A")
        person = Person.objects.create(
            first_name="Recent",
            last_name="Student",
            status=Person.Status.PASSED,
            extra_data={
                "country_code": "TH",
                "region": "central",
                "province": "กรุงเทพมหานคร",
            },
        )
        student = Student.objects.get(person=person)
        student.group = group
        student.is_paid = True
        student.save(update_fields=["group", "is_paid"])

        self.client.force_login(admin)
        response = self.client.get(reverse("school:admin_overview_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/admin_overview_dashboard.html")
        self.assertContains(response, "ภาพรวมโรงเรียน")
        self.assertContains(response, "pending@example.com")
        self.assertContains(response, "Recent Student")
        self.assertContains(response, "พื้นที่และภูมิภาค")
        self.assertContains(response, "กรุงเทพมหานคร")
        self.assertNotContains(response, "ผู้สอนรออนุมัติ")
        self.assertEqual(response.context["stats"]["students_paid"], 1)
        self.assertEqual(response.context["stats"]["students_unpaid"], 0)
        self.assertEqual(response.context["stats"]["groups_total"], 1)
        self.assertEqual(response.context["geo_stats"]["thai"], 1)

    def test_legacy_admin_role_without_superuser_cannot_access_admin_overview(self):
        User = get_user_model()
        legacy_admin = User.objects.create_user(
            username="legacy-admin",
            password="pass",
            role="ADMIN",
            is_staff=True,
        )

        self.client.force_login(legacy_admin)
        response = self.client.get(reverse("school:admin_overview_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_visit_teacher_dashboard(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="pass",
        )

        self.client.force_login(admin)
        response = self.client.get(reverse("school:teacher_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/teacher_dashboard.html")

    def test_student_payment_upload_page_hides_student_id_field(self):
        response = self.client.get(reverse("school:student_payment_upload"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "รหัสนักศึกษา")
        self.assertNotContains(response, 'name="student_id"')
        self.assertContains(response, "ยังไม่พบใบสมัคร")
        self.assertContains(response, "สถานะใบสมัคร")
        self.assertNotContains(response, "กรุณาสมัครเรียนก่อน")
        self.assertNotContains(response, "กำลังตรวจสอบ LINE account")
        self.assertNotContains(response, "ส่งสลิปให้ตรวจสอบ")
        self.assertNotContains(response, 'name="payment_slip"')

    def test_student_payment_upload_ignores_query_line_user_id_until_liff_syncs(self):
        Person.objects.create(
            first_name="Passed",
            last_name="Spoof",
            line_user_id="Uquerypayment",
            status=Person.Status.PASSED,
        )

        response = self.client.get(
            reverse("school:student_payment_upload"),
            {"line_user_id": "Uquerypayment"},
        )

        self.assertContains(response, "ยังไม่พบใบสมัคร")
        self.assertNotContains(response, "ส่งสลิปให้ตรวจสอบ")
        self.assertNotContains(response, 'name="payment_slip"')

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
        self.assertContains(response, "ยังไม่พบใบสมัคร")
        self.assertNotContains(response, "ส่งสลิปให้ตรวจสอบ")
        student.refresh_from_db()
        self.assertFalse(student.payment_slip)

    def test_student_payment_upload_uses_line_session(self):
        person = Person.objects.create(
            first_name="Line",
            last_name="Student",
            line_user_id="Ulinepayment",
            line_display_name="Line Student",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
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

    def test_student_payment_upload_requires_student_status(self):
        person = Person.objects.create(
            first_name="Pending",
            last_name="Payment",
            line_user_id="Upendingpayment",
        )
        Student.objects.create(person=person)
        session = self.client.session
        session["line_profile"] = {
            "line_user_id": "Upendingpayment",
            "line_display_name": "Pending Payment",
            "line_picture_url": "",
            "verified": True,
        }
        session.save()
        slip = SimpleUploadedFile(
            "pending-slip.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        response = self.client.post(
            reverse("school:student_payment_upload"),
            {"payment_slip": slip},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ยังไม่เปิดให้ชำระเงิน")
        self.assertContains(response, "จ่ายเงินได้หลังสัมภาษณ์ผ่าน")
        self.assertNotContains(response, "ส่งสลิปให้ตรวจสอบ")
        self.assertNotContains(response, 'name="payment_slip"')

    def test_paid_student_payment_page_shows_student_id_instead_of_form(self):
        person = Person.objects.create(
            first_name="Paid",
            last_name="Complete",
            line_user_id="Upaidcomplete",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        student.is_paid = True
        student.save(update_fields=["is_paid"])
        session = self.client.session
        session["line_profile"] = {
            "line_user_id": "Upaidcomplete",
            "line_display_name": "Paid Complete",
            "line_picture_url": "",
            "verified": True,
        }
        session.save()

        response = self.client.get(reverse("school:student_payment_upload"))

        self.assertContains(response, "ยินดีด้วย คุณเป็นนักศึกษา BRI แล้ว")
        self.assertContains(response, "#check")
        self.assertContains(response, student.student_id)
        self.assertNotContains(response, "ส่งสลิปให้ตรวจสอบ")

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
        self.assertContains(response, "ผ่านสัมภาษณ์")
        self.assertNotContains(response, student.student_id)
        self.assertContains(response, "รอชำระเงิน")
        self.assertContains(response, reverse("school:student_payment_upload"))
        self.assertContains(response, "ไปหน้าแจ้งชำระเงิน")
        self.assertNotContains(response, "หน้าสมัครเรียน")
        self.assertContains(response, 'href="https://line.me/R/"')

    def test_paid_line_account_sees_completed_student_result(self):
        person = Person.objects.create(
            first_name="Paid",
            last_name="Person",
            line_user_id="Upaidresult",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        student.is_paid = True
        student.save(update_fields=["is_paid"])

        response = self.client.get(
            reverse("school:announcement_result"),
            {"line_user_id": "Upaidresult"},
        )

        self.assertContains(response, "ยินดีด้วย คุณเป็นนักศึกษา BRI แล้ว")
        self.assertContains(response, "#check")
        self.assertContains(response, student.student_id)
        self.assertNotContains(response, "ไปหน้าแจ้งชำระเงิน")

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

        self.assertContains(response, "ผ่านสัมภาษณ์")
        self.assertNotContains(response, student.student_id)

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
        self.assertContains(response, "ยังไม่พบใบสมัคร")
        self.assertContains(response, "สถานะใบสมัคร")
        self.assertNotContains(response, "กรุณาเปิดหน้านี้จาก LINE rich menu")
        self.assertNotContains(response, "LINE account")
        self.assertContains(response, "กลับไปยัง LINE")
        self.assertContains(response, "สมัครเรียน")


@override_settings(
    LINE_LIFF_ALLOW_UNVERIFIED_PROFILE=True,
    LINE_LIFF_ENABLED=True,
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

    def test_rich_menu_launch_urls_redirect_through_liff(self):
        result_response = self.client.get(reverse("school:liff_results_launch"))
        payment_response = self.client.get(reverse("school:liff_payment_launch"))

        self.assertRedirects(
            result_response,
            "https://liff.line.me/1234567890-AbCdEf/results/",
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            payment_response,
            "https://liff.line.me/1234567890-AbCdEf/students/payment/",
            fetch_redirect_response=False,
        )

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
        self.assertContains(response, "#clock")
        self.assertNotContains(response, "รหัสข้อมูล")
        self.assertContains(response, 'href="https://line.me/R/nv/chat"')
        self.assertNotContains(response, "registration-form")

    def test_unpaid_registered_student_cannot_see_student_id(self):
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
        self.assertNotContains(response, student.student_id)
        self.assertEqual(person.student_code, "")

    def test_paid_registered_student_sees_completed_status_on_registration_page(self):
        person = Person.objects.create(
            first_name="Paid",
            last_name="Existing",
            line_user_id="Upaidexisting",
            status=Person.Status.PASSED,
        )
        student = Student.objects.get(person=person)
        student.is_paid = True
        student.save(update_fields=["is_paid"])
        self.sync_line_profile(user_id="Upaidexisting", display_name="Paid Existing")

        response = self.client.get(reverse("school:registration"))

        self.assertTemplateUsed(response, "school/already_registered.html")
        self.assertContains(response, "ยินดีด้วย คุณเป็นนักศึกษา BRI แล้ว")
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


@override_settings(
    LINE_LIFF_ENABLED=False,
    LINE_LIFF_ID="1234567890-AbCdEf",
)
class LocalDevLiffDisabledTests(TestCase):
    def test_registration_does_not_load_liff_bridge_when_disabled(self):
        response = self.client.get(reverse("school:registration"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "https://static.line-scdn.net/liff/edge/2/sdk.js")
        self.assertNotContains(response, "school/js/liff_bridge.js")

    def test_rich_menu_launch_urls_stay_local_when_liff_is_disabled(self):
        response = self.client.get(reverse("school:liff_results_launch"))

        self.assertRedirects(response, reverse("school:announcement_result"))

    def test_liff_state_does_not_boot_when_liff_is_disabled(self):
        response = self.client.get(
            reverse("school:registration"),
            {"liff.state": "/results/"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "school/registration.html")
        self.assertNotContains(response, "กำลังเปิดหน้าที่เลือก")
