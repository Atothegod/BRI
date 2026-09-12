import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .line import build_interview_invitation_flex_message
from .models import Person


class InterviewScheduleTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="scheduler", password="test-password")
        self.client.force_login(self.admin)
        self.people = [Person.objects.create(first_name=f"Applicant {i}", last_name="Test", line_user_id=f"Utest{i}") for i in range(2)]
        self.at = (timezone.now() + timedelta(days=2)).astimezone(ZoneInfo("Asia/Bangkok")).replace(hour=9, minute=30, second=0, microsecond=0)
        self.url = reverse("school:interview_schedule")

    def schedule(self, **changes):
        data = {"people": [p.pk for p in self.people], "date": self.at.strftime("%Y-%m-%d"), "time": "09:30", "details": "Online interview"}
        data.update(changes)
        return self.client.post(self.url, data)

    def notify(self, person, at=None):
        return self.client.post(reverse("school:interview_notify", args=[person.pk]), {"at": (at or self.at).isoformat()})

    def confirmation_url(self, person):
        message = build_interview_invitation_flex_message(person)
        return message["contents"]["footer"]["contents"][0]["action"]["uri"]

    @override_settings(TIME_ZONE="UTC")
    @patch("school.interviews.send_line_push_message")
    def test_bulk_schedule_saves_thai_time_before_sending(self, send):
        self.assertEqual(self.schedule().status_code, 302)
        for person in self.people:
            person.refresh_from_db()
            self.assertEqual(person.interview_at, self.at)
            self.assertEqual(person.interview_notification_state, "pending")
            self.assertEqual(person.status, Person.Status.IN_PROGRESS)
        self.assertEqual(len(self.client.session["interview_send_queue"]), 2)
        send.assert_not_called()

    @patch("school.interviews.send_line_push_message", return_value=True)
    def test_notify_is_idempotent_and_contains_correct_appointment(self, send):
        self.schedule()
        self.assertTrue(self.notify(self.people[0]).json()["sent"])
        self.assertTrue(self.notify(self.people[0]).json()["sent"])
        send.assert_called_once()
        content = json.dumps(send.call_args.args[1], ensure_ascii=False)
        self.assertIn("09:30", content)
        self.assertIn(self.at.strftime("%d/%m/%Y"), content)
        self.assertIn("Online interview", content)
        self.assertNotIn("รหัสนักศึกษา", content)
        self.people[0].refresh_from_db()
        self.assertIsNotNone(self.people[0].interview_notified_at)

    @patch("school.interviews.send_line_push_message", side_effect=[False, True])
    def test_failure_keeps_appointment_and_can_be_retried(self, send):
        self.schedule()
        self.assertFalse(self.notify(self.people[0]).json()["sent"])
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_at, self.at)
        self.assertEqual(self.people[0].interview_notification_state, "failed")
        self.assertTrue(self.notify(self.people[0]).json()["sent"])

    @patch("school.interviews.send_line_push_message", return_value=True)
    def test_reschedule_resets_notification_and_rejects_stale_requests(self, send):
        self.schedule()
        self.notify(self.people[0])
        Person.objects.filter(pk=self.people[0].pk).update(interview_confirmed_at=timezone.now())
        self.schedule(time="10:30")
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_notification_state, "pending")
        self.assertIsNone(self.people[0].interview_notified_at)
        self.assertIsNone(self.people[0].interview_confirmed_at)
        self.assertEqual(self.notify(self.people[0]).status_code, 409)
        self.assertEqual(send.call_count, 1)

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_line_message_links_to_signed_confirmation_page(self):
        self.schedule()
        self.people[0].refresh_from_db()
        url = self.confirmation_url(self.people[0])
        parsed = urlsplit(url)
        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}", "https://bri.example")
        self.assertEqual(parsed.path, reverse("school:interview_confirmation"))
        self.assertTrue(parse_qs(parsed.query)["token"][0])
        self.assertIn("ยืนยันนัดสัมภาษณ์", json.dumps(build_interview_invitation_flex_message(self.people[0]), ensure_ascii=False))

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_applicant_reviews_then_confirms_appointment(self):
        self.schedule()
        self.people[0].refresh_from_db()
        parsed = urlsplit(self.confirmation_url(self.people[0]))
        token = parse_qs(parsed.query)["token"][0]

        preview = self.client.get(parsed.path, {"token": token})
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Applicant 0 Test")
        self.assertContains(preview, "09:30")
        self.assertContains(preview, "Online interview")
        self.people[0].refresh_from_db()
        self.assertIsNone(self.people[0].interview_confirmed_at)

        confirmation = self.client.post(parsed.path, {"token": token})
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "ยืนยันนัดสัมภาษณ์แล้ว")
        self.people[0].refresh_from_db()
        self.assertIsNotNone(self.people[0].interview_confirmed_at)

        repeated = self.client.post(parsed.path, {"token": token})
        self.assertEqual(repeated.status_code, 200)

        status = self.client.post(reverse("school:interview_confirmation_status"), {
            "people": [self.people[0].pk, self.people[1].pk],
        })
        self.assertTrue(status.json()["people"][str(self.people[0].pk)])
        self.assertIsNone(status.json()["people"][str(self.people[1].pk)])

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_invalid_stale_and_expired_confirmations_are_rejected(self):
        invalid = self.client.get(reverse("school:interview_confirmation"), {"token": "changed-token"})
        self.assertEqual(invalid.status_code, 400)

        self.schedule()
        self.people[0].refresh_from_db()
        parsed = urlsplit(self.confirmation_url(self.people[0]))
        token = parse_qs(parsed.query)["token"][0]
        Person.objects.filter(pk=self.people[0].pk).update(interview_at=self.at + timedelta(hours=1))
        self.assertEqual(self.client.post(parsed.path, {"token": token}).status_code, 409)

        self.people[1].refresh_from_db()
        expired_url = urlsplit(self.confirmation_url(self.people[1]))
        expired_token = parse_qs(expired_url.query)["token"][0]
        Person.objects.filter(pk=self.people[1].pk).update(interview_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.client.post(expired_url.path, {"token": expired_token}).status_code, 409)

    def test_rejects_empty_selection_past_time_and_ineligible_person(self):
        for changes in [{"people": []}, {"date": "2000-01-01"}]:
            self.assertEqual(self.schedule(**changes).status_code, 200)
        Person.objects.filter(pk=self.people[0].pk).update(status=Person.Status.FAILED)
        self.assertEqual(self.schedule().status_code, 200)
        self.assertFalse(Person.objects.filter(interview_at__isnull=False).exists())

    def test_requires_school_admin_for_page_and_notifications(self):
        user = get_user_model().objects.create_user(username="teacher", password="test-password", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.schedule().status_code, 403)
        self.assertEqual(self.notify(self.people[0]).status_code, 403)
        self.assertEqual(self.client.post(reverse("school:interview_confirmation_status"), {"people": [self.people[0].pk]}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_anonymous_admin_pages_use_django_admin_login(self):
        self.client.logout()
        for name in ["school:interview_schedule", "school:admin_overview_dashboard"]:
            path = reverse(name)
            self.assertRedirects(self.client.get(path), f"{reverse('admin:login')}?next={path}")
        path = reverse("school:interview_notify", args=[self.people[0].pk])
        self.assertRedirects(self.client.post(path), f"{reverse('admin:login')}?next={path}")

    def test_django_admin_login_returns_to_scheduler(self):
        self.client.logout()
        response = self.client.post(reverse("admin:login"), {
            "username": "scheduler", "password": "test-password", "next": self.url,
        })
        self.assertRedirects(response, self.url)

    def test_django_admin_has_scheduler_entry(self):
        self.assertContains(self.client.get(reverse("admin:index")), self.url)

    def test_approved_teacher_cannot_access_scheduler(self):
        User = get_user_model()
        teacher = User.objects.create_user(username="approved", role=User.Role.TEACHER, is_teacher_approved=True)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.schedule().status_code, 403)
        self.assertEqual(self.notify(self.people[0]).status_code, 403)

    def test_page_search_and_saved_appointments_render(self):
        self.schedule()
        response = self.client.get(self.url, {"q": "Applicant 0"})
        self.assertContains(response, "Applicant 0")
        self.assertNotContains(response, "Applicant 1")
        self.assertContains(response, "09:30")
        self.assertContains(response, "interview-queue")

    @patch("school.interviews.send_line_push_message")
    def test_cannot_notify_after_status_changed_or_appointment_passed(self, send):
        self.schedule()
        Person.objects.filter(pk=self.people[0].pk).update(status=Person.Status.FAILED)
        self.assertEqual(self.notify(self.people[0]).status_code, 409)
        Person.objects.filter(pk=self.people[1].pk).update(interview_at=timezone.now() - timedelta(days=1))
        self.assertEqual(self.notify(self.people[1]).status_code, 409)
        send.assert_not_called()
