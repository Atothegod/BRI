import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .date_formats import thai_date
from .line import build_appointment_invitation_flex_message
from .models import Appointment, AppointmentParticipant, AppointmentSlot, Person, Student


class AppointmentScheduleTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="scheduler", password="test-password")
        self.client.force_login(self.admin)
        self.people = [
            Person.objects.create(first_name=f"Applicant {index}", last_name="Test", line_user_id=f"Utest{index}")
            for index in range(2)
        ]
        self.at = (timezone.now() + timedelta(days=2)).astimezone(ZoneInfo("Asia/Bangkok")).replace(hour=9, minute=30, second=0, microsecond=0)
        self.url = reverse("school:appointment_schedule")

    def schedule(self, appointment_type="interview", people=None, **changes):
        data = {
            "appointment_type": appointment_type,
            "people": people if people is not None else [person.pk for person in self.people],
            "title": "สัมภาษณ์รุ่นใหม่" if appointment_type == "interview" else "ปฐมนิเทศนักศึกษาใหม่",
            "date": self.at.strftime("%Y-%m-%d"), "time": "09:30",
            "location": "ห้องประชุม BRI", "meeting_url": "https://meet.example/session",
            "details": "กรุณามาก่อนเวลา 15 นาที",
        }
        if appointment_type == "interview":
            data.update({
                "slot_start": ["09:30"],
                "slot_end": ["10:30"],
                "slot_capacity": ["2"],
            })
        data.update(changes)
        return self.client.post(self.url, data)

    def latest_participant(self, person=None):
        return AppointmentParticipant.objects.select_related("appointment", "person").filter(
            person=person or self.people[0]
        ).latest("pk")

    def notify(self, participant, at=None):
        return self.client.post(reverse("school:appointment_notify", args=[participant.pk]), {
            "at": (at or participant.appointment.starts_at).isoformat()
        })

    def confirmation_url(self, participant):
        message = build_appointment_invitation_flex_message(participant)
        return message["contents"]["footer"]["contents"][0]["action"]["uri"]

    def invite_to_event(self, appointment, people):
        return self.client.post(self.url, {
            "appointment_type": appointment.appointment_type,
            "event_id": appointment.pk,
            "people": [person.pk for person in people],
        })

    @override_settings(TIME_ZONE="UTC")
    def test_bulk_interview_creates_appointment_participants_and_legacy_snapshot(self):
        self.assertEqual(self.schedule().status_code, 302)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.starts_at, self.at)
        self.assertEqual(appointment.slots.count(), 1)
        self.assertEqual(appointment.slots.get().capacity, 2)
        self.assertEqual(appointment.participants.count(), 2)
        self.assertEqual(len(self.client.session["appointment_send_queue"]), 2)
        for person in self.people:
            person.refresh_from_db()
            self.assertEqual(person.interview_at, self.at)
            self.assertEqual(person.interview_notification_state, "pending")

    def test_bulk_interview_can_prepare_more_than_one_hundred_people(self):
        people = [
            Person(first_name=f"Bulk {index:03d}", last_name="Applicant", line_user_id=f"Ubulk{index:03d}")
            for index in range(120)
        ]
        Person.objects.bulk_create(people)
        ids = list(Person.objects.filter(first_name__startswith="Bulk ").values_list("pk", flat=True))

        list_page = self.client.get(self.url, {"type": "interview", "event": "new"})
        self.assertEqual(list_page.context["page_obj"].paginator.per_page, 200)

        response = self.schedule(people=ids, slot_capacity=["120"])

        self.assertEqual(response.status_code, 302)
        appointment = Appointment.objects.get()
        self.assertEqual(appointment.participants.count(), 120)
        self.assertEqual(len(self.client.session["appointment_send_queue"]), 120)

    def test_appointment_people_are_sorted_newest_first(self):
        older = Person.objects.create(first_name="Older", last_name="Applicant", line_user_id="Uolder")
        newer = Person.objects.create(first_name="Newer", last_name="Applicant", line_user_id="Unewer")

        response = self.client.get(self.url, {"type": "interview", "event": "new"})

        page_people = list(response.context["page_obj"].object_list)
        self.assertLess(page_people.index(newer), page_people.index(older))

    def test_orientation_only_allows_paid_passed_students(self):
        Person.objects.filter(pk=self.people[0].pk).update(status=Person.Status.PASSED)
        Student.objects.create(person=self.people[0], is_paid=True)
        response = self.schedule("orientation", people=[self.people[0].pk])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.get().appointment_type, Appointment.Type.ORIENTATION)

        Person.objects.filter(pk=self.people[1].pk).update(status=Person.Status.PASSED)
        Student.objects.create(person=self.people[1], is_paid=False)
        self.assertEqual(self.schedule("orientation", people=[self.people[1].pk]).status_code, 200)
        self.assertEqual(Appointment.objects.count(), 1)

    @patch("school.interviews.send_line_push_message", return_value=True)
    def test_notify_is_idempotent_and_uses_event_message(self, send):
        self.schedule()
        participant = self.latest_participant()
        self.assertTrue(self.notify(participant).json()["sent"])
        self.assertTrue(self.notify(participant).json()["sent"])
        send.assert_called_once()
        content = json.dumps(send.call_args.args[1], ensure_ascii=False)
        self.assertIn("09:30", content)
        self.assertIn(thai_date(self.at, include_weekday=True), content)
        self.assertNotIn(self.at.strftime("%d/%m/%Y"), content)
        self.assertIn("เลือกช่วงเวลา", content)
        self.assertIn("ห้องประชุม BRI", content)
        self.assertIn("เลือกเวลา", content)
        participant.refresh_from_db()
        self.assertEqual(participant.notification_status, "sent")

    @patch("school.interviews.send_line_push_message", side_effect=[False, True])
    def test_failed_line_delivery_can_be_retried(self, send):
        self.schedule()
        participant = self.latest_participant()
        self.assertFalse(self.notify(participant).json()["sent"])
        participant.refresh_from_db()
        self.assertEqual(participant.notification_status, "failed")
        self.assertTrue(self.notify(participant).json()["sent"])

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_orientation_message_and_confirmation_flow(self):
        Person.objects.filter(pk=self.people[0].pk).update(status=Person.Status.PASSED)
        Student.objects.create(person=self.people[0], is_paid=True)
        self.schedule("orientation", people=[self.people[0].pk])
        participant = self.latest_participant()
        message = build_appointment_invitation_flex_message(participant)
        self.assertIn("BRI Orientation", json.dumps(message, ensure_ascii=False))
        self.assertEqual(message["contents"]["body"]["backgroundColor"], "#F3F0E8")
        self.assertEqual(message["contents"]["footer"]["backgroundColor"], "#F3F0E8")
        parsed = urlsplit(self.confirmation_url(participant))
        token = parse_qs(parsed.query)["token"][0]
        preview = self.client.get(parsed.path, {"token": token})
        self.assertContains(preview, "ยืนยันเข้าร่วมปฐมนิเทศ")
        self.assertContains(preview, thai_date(self.at, include_weekday=True))
        self.assertContains(preview, "ห้องประชุม BRI")
        participant.refresh_from_db()
        self.assertEqual(participant.response_status, "waiting")

        confirmed = self.client.post(parsed.path, {"token": token})
        self.assertContains(confirmed, "ยืนยันเข้าร่วมปฐมนิเทศแล้ว")
        participant.refresh_from_db()
        self.assertEqual(participant.response_status, "confirmed")
        status = self.client.post(reverse("school:appointment_confirmation_status"), {
            "participants": [participant.pk]
        }).json()["participants"][str(participant.pk)]
        self.assertEqual(status["status"], "confirmed")
        self.assertEqual(status["confirmed_at"], thai_date(participant.confirmed_at, include_time=True))

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_interview_confirmation_requires_available_slot(self):
        self.schedule(slot_capacity=["1"])
        participants = list(AppointmentParticipant.objects.order_by("pk"))
        slot = AppointmentSlot.objects.get()
        first_token = parse_qs(urlsplit(self.confirmation_url(participants[0])).query)["token"][0]
        second_token = parse_qs(urlsplit(self.confirmation_url(participants[1])).query)["token"][0]

        preview = self.client.get(reverse("school:appointment_confirmation"), {"token": first_token})
        self.assertContains(preview, "เลือกเวลาสัมภาษณ์")
        self.assertContains(preview, thai_date(self.at, include_weekday=True))
        self.assertContains(preview, "เหลือ 1 จาก 1 ที่นั่ง")
        confirmed = self.client.post(reverse("school:appointment_confirmation"), {"token": first_token, "slot": slot.pk})
        self.assertContains(confirmed, "ยืนยันนัดสัมภาษณ์แล้ว")
        participants[0].refresh_from_db()
        self.assertEqual(participants[0].selected_slot, slot)

        full = self.client.get(reverse("school:appointment_confirmation"), {"token": second_token})
        self.assertContains(full, "เต็มแล้ว")
        rejected = self.client.post(reverse("school:appointment_confirmation"), {"token": second_token, "slot": slot.pk})
        self.assertEqual(rejected.status_code, 409)
        self.assertContains(rejected, "ทีมงานจะนัดวันสัมภาษณ์รอบถัดไปให้อีกครั้ง", status_code=409)
        participants[1].refresh_from_db()
        self.assertEqual(participants[1].response_status, AppointmentParticipant.ResponseStatus.WAITING)

    def test_existing_event_can_invite_new_applicants_without_creating_another_event(self):
        self.schedule(people=[self.people[0].pk])
        appointment = Appointment.objects.get()

        unsent = self.client.get(self.url, {
            "type": "interview", "event": appointment.pk, "audience": "unsent",
        })
        self.assertNotContains(unsent, "Applicant 0")
        self.assertContains(unsent, "Applicant 1")

        response = self.invite_to_event(appointment, [self.people[1]])
        self.assertRedirects(
            response,
            f"{self.url}?type=interview&event={appointment.pk}&audience=waiting",
            fetch_redirect_response=False,
        )
        self.assertEqual(Appointment.objects.count(), 1)
        self.assertEqual(appointment.participants.count(), 2)
        self.assertEqual(len(self.client.session["appointment_send_queue"]), 1)

    def test_event_audiences_separate_sent_failed_and_unsent_people(self):
        third_person = Person.objects.create(
            first_name="Applicant 2", last_name="Test", line_user_id="Utest2",
        )
        self.schedule()
        appointment = Appointment.objects.get()
        first, second = appointment.participants.order_by("pk")
        first.notification_status = AppointmentParticipant.NotificationStatus.SENT
        first.save(update_fields=["notification_status"])
        second.notification_status = AppointmentParticipant.NotificationStatus.FAILED
        second.save(update_fields=["notification_status"])

        waiting = self.client.get(self.url, {"type": "interview", "event": appointment.pk, "audience": "waiting"})
        self.assertContains(waiting, "Applicant 0")
        self.assertNotContains(waiting, "Applicant 1")
        self.assertContains(waiting, "รอยืนยัน")

        failed = self.client.get(self.url, {"type": "interview", "event": appointment.pk, "audience": "failed"})
        self.assertContains(failed, "Applicant 1")
        self.assertNotContains(failed, "Applicant 0")

        unsent = self.client.get(self.url, {"type": "interview", "event": appointment.pk, "audience": "unsent"})
        self.assertContains(unsent, third_person.full_name)
        self.assertNotContains(unsent, "Applicant 0")
        self.assertNotContains(unsent, "Applicant 1")

    def test_confirmed_interview_people_are_separated_from_ready_to_send(self):
        self.schedule(people=[self.people[0].pk])
        appointment = Appointment.objects.get()
        participant = appointment.participants.get()
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        participant.selected_slot = appointment.slots.get()
        participant.confirmed_at = timezone.now()
        participant.save(update_fields=["response_status", "selected_slot", "confirmed_at"])

        create_new = self.client.get(self.url, {"type": "interview", "event": "new"})
        self.assertNotContains(create_new, "Applicant 0")
        self.assertContains(create_new, "Applicant 1")

        next_event = Appointment.objects.create(
            appointment_type=Appointment.Type.INTERVIEW,
            title="สัมภาษณ์รอบถัดไป",
            starts_at=self.at + timedelta(days=7),
        )
        AppointmentSlot.objects.create(
            appointment=next_event,
            starts_at=self.at + timedelta(days=7),
            ends_at=self.at + timedelta(days=7, hours=1),
            capacity=10,
        )
        ready = self.client.get(self.url, {"type": "interview", "event": next_event.pk, "audience": "unsent"})
        self.assertNotContains(ready, "Applicant 0")
        self.assertContains(ready, "Applicant 1")

        confirmed_other = self.client.get(self.url, {
            "type": "interview", "event": next_event.pk, "audience": "confirmed_other",
        })
        self.assertContains(confirmed_other, "Applicant 0")
        self.assertContains(confirmed_other, "ยืนยันรอบอื่นแล้ว")

        response = self.invite_to_event(next_event, [self.people[0]])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "มีผู้เข้าร่วมที่ไม่ตรงเงื่อนไข")
        self.assertFalse(next_event.participants.exists())

    def test_full_event_cannot_invite_more_people(self):
        self.schedule(people=[self.people[0].pk], slot_capacity=["1"])
        appointment = Appointment.objects.get()
        participant = appointment.participants.get()
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        participant.selected_slot = appointment.slots.get()
        participant.confirmed_at = timezone.now()
        participant.save(update_fields=["response_status", "selected_slot", "confirmed_at"])

        response = self.invite_to_event(appointment, [self.people[1]])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Event นี้เต็มแล้ว")
        self.assertContains(response, "กรุณาสร้าง Event ใหม่")
        self.assertEqual(appointment.participants.count(), 1)
        live_status = self.client.post(reverse("school:appointment_confirmation_status"), {
            "participants": [participant.pk], "event_id": appointment.pk,
        }).json()["event"]
        self.assertEqual(live_status["confirmed_count"], 1)
        self.assertEqual(live_status["capacity"], 1)
        self.assertTrue(live_status["is_full"])

    def test_full_event_separates_waiting_people_for_next_round(self):
        third_person = Person.objects.create(
            first_name="Applicant 2", last_name="Test", line_user_id="Utest2",
        )
        failed_person = Person.objects.create(
            first_name="Applicant 3", last_name="Test", line_user_id="Utest3",
        )
        self.schedule(
            people=[self.people[0].pk, self.people[1].pk, third_person.pk, failed_person.pk],
            slot_capacity=["2"],
        )
        appointment = Appointment.objects.get()
        slot = appointment.slots.get()
        first, second, third, failed = appointment.participants.order_by("pk")
        for participant in (first, second):
            participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
            participant.selected_slot = slot
            participant.confirmed_at = timezone.now()
            participant.save(update_fields=["response_status", "selected_slot", "confirmed_at"])
        third.notification_status = AppointmentParticipant.NotificationStatus.SENT
        third.save(update_fields=["notification_status"])
        failed.notification_status = AppointmentParticipant.NotificationStatus.FAILED
        failed.save(update_fields=["notification_status"])

        waiting = self.client.get(self.url, {
            "type": "interview",
            "event": appointment.pk,
            "audience": "waiting",
        })
        self.assertContains(waiting, "Event นี้เต็มแล้ว ผู้ที่ยังไม่ยืนยันถูกแยกไปแท็บรอนัดรอบถัดไป")
        self.assertNotContains(waiting, third_person.full_name)

        next_round = self.client.get(self.url, {
            "type": "interview",
            "event": appointment.pk,
            "audience": "next_round",
        })
        self.assertContains(next_round, "รอนัดรอบถัดไป")
        self.assertContains(next_round, "รอบสัมเต็มแล้ว")
        self.assertContains(next_round, "สร้าง Event ใหม่จากกลุ่มนี้")
        self.assertContains(next_round, third_person.full_name)
        self.assertNotContains(next_round, self.people[0].full_name)
        self.assertNotContains(next_round, failed_person.full_name)

        failed_page = self.client.get(self.url, {
            "type": "interview",
            "event": appointment.pk,
            "audience": "failed",
        })
        self.assertContains(failed_page, failed_person.full_name)

        create_next = self.client.get(self.url, {
            "type": "interview",
            "event": "new",
            "source_event": appointment.pk,
            "audience": "next_round",
        })
        self.assertContains(create_next, "สร้าง Event ใหม่ให้ผู้สมัครที่รอนัดรอบถัดไป")
        self.assertContains(create_next, third_person.full_name)
        self.assertNotContains(create_next, self.people[0].full_name)
        self.assertNotContains(create_next, failed_person.full_name)

        live_status = self.client.post(reverse("school:appointment_confirmation_status"), {
            "participants": [third.pk, failed.pk], "event_id": appointment.pk,
        }).json()["event"]
        self.assertEqual(live_status["waiting_count"], 0)
        self.assertEqual(live_status["next_round_count"], 1)
        self.assertEqual(live_status["failed_count"], 1)

        response = self.schedule(
            people=[third_person.pk],
            title="สัมภาษณ์รอบถัดไป",
            date=(self.at + timedelta(days=7)).strftime("%Y-%m-%d"),
            slot_start=["09:30"],
            slot_end=["10:30"],
            slot_capacity=["1"],
        )
        self.assertRedirects(
            response,
            f"{self.url}?type=interview&event={Appointment.objects.latest('pk').pk}&audience=waiting",
            fetch_redirect_response=False,
        )
        self.assertEqual(Appointment.objects.count(), 2)
        self.assertTrue(Appointment.objects.latest("pk").participants.filter(person=third_person).exists())

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_public_urls_use_appointment_names_and_legacy_routes_redirect(self):
        self.schedule(people=[self.people[0].pk])
        participant = self.latest_participant()
        self.assertEqual(reverse("school:appointment_schedule"), "/school-admin/appointments/")
        self.assertEqual(reverse("school:appointment_confirmation"), "/appointments/confirm/")
        self.assertNotIn("/interviews/", self.confirmation_url(participant))
        response = self.client.get("/school-admin/interviews/", {"type": "orientation"})
        self.assertRedirects(
            response,
            "/school-admin/appointments/?type=orientation",
            fetch_redirect_response=False,
        )

    def test_invalid_changed_and_cancelled_confirmation_links_are_rejected(self):
        path = reverse("school:appointment_confirmation")
        self.assertEqual(self.client.get(path, {"token": "invalid"}).status_code, 400)
        self.schedule()
        participant = self.latest_participant()
        token = parse_qs(urlsplit(self.confirmation_url(participant)).query)["token"][0]
        participant.appointment.status = Appointment.Status.CANCELLED
        participant.appointment.save(update_fields=["status"])
        self.assertEqual(self.client.post(path, {"token": token}).status_code, 409)

    @patch("school.interviews.send_line_push_message")
    def test_status_change_revokes_pending_invitation(self, send):
        self.schedule(people=[self.people[0].pk])
        participant = self.latest_participant()
        Person.objects.filter(pk=self.people[0].pk).update(status=Person.Status.FAILED)
        self.assertEqual(self.notify(participant).status_code, 409)
        token = parse_qs(urlsplit(self.confirmation_url(participant)).query)["token"][0]
        self.assertEqual(self.client.get(reverse("school:appointment_confirmation"), {"token": token}).status_code, 409)
        send.assert_not_called()

    def test_old_interview_confirmation_token_remains_supported(self):
        self.schedule()
        participant = self.latest_participant()
        token = signing.dumps({
            "person_id": participant.person_id,
            "interview_at": participant.appointment.starts_at.isoformat(),
        }, salt="school.interview-confirmation", compress=True)
        response = self.client.get(reverse("school:appointment_confirmation"), {"token": token})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "เลือกเวลาสัมภาษณ์")

    def test_selection_validation_and_batch_scope(self):
        self.assertEqual(self.schedule(people=[]).status_code, 200)
        self.assertEqual(self.schedule(date="2000-01-01").status_code, 200)
        response = self.schedule(people=[self.people[0].pk])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AppointmentParticipant.objects.count(), 1)
        self.assertEqual(AppointmentParticipant.objects.get().person, self.people[0])

    def test_filters_and_history_use_generic_appointments(self):
        self.schedule(people=[self.people[0].pk])
        participant = self.latest_participant()
        participant.notification_status = "failed"
        participant.response_status = "confirmed"
        participant.confirmed_at = timezone.now()
        participant.save()
        response = self.client.get(self.url, {
            "type": "interview", "q": "Applicant 0", "appointment": "scheduled",
            "line": "connected", "notification": "failed", "confirmation": "confirmed",
        })
        self.assertContains(response, "Applicant 0")
        self.assertNotContains(response, "Applicant 1")
        self.assertContains(response, "สัมภาษณ์รุ่นใหม่")
        self.assertContains(response, "เลือก Event ที่จะส่งนัด")

    def test_requires_superuser_and_uses_admin_login(self):
        teacher = get_user_model().objects.create_user(username="teacher", password="test-password", is_staff=True)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.schedule().status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('admin:login')}?next={self.url}")

    def test_admin_index_has_appointment_entry(self):
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "นัดหมายและ LINE")
        self.assertContains(response, self.url)

    @override_settings(LINE_MESSAGING_CHANNEL_ACCESS_TOKEN="line-token")
    @patch("school.line.request.urlopen")
    def test_interview_results_page_can_search_and_pass_online_with_line_notice(self, mock_urlopen):
        person = Person.objects.create(
            first_name="Result",
            last_name="Applicant",
            phone="0890000000",
            line_user_id="Uresult",
            line_display_name="Result LINE",
            extra_data={
                "goal": "อยากรับใช้ให้ชัดขึ้น",
                "vision_calling": "สร้างผู้นำรุ่นใหม่",
            },
        )
        appointment = Appointment.objects.create(
            appointment_type=Appointment.Type.INTERVIEW,
            title="สัมภาษณ์รอบผล",
            starts_at=self.at,
        )
        AppointmentParticipant.objects.create(appointment=appointment, person=person)
        url = reverse("school:interview_results")

        response = self.client.get(url, {"q": "Result"})
        self.assertContains(response, "Result Applicant")
        self.assertNotContains(response, "school-admin-navbar")
        self.assertContains(response, "อยากรับใช้ให้ชัดขึ้น")
        self.assertContains(response, "สร้างผู้นำรุ่นใหม่")
        self.assertContains(response, "ผ่าน onsite")
        self.assertContains(response, "ผ่าน online")

        unconfirmed = self.client.post(url, {
            "person": person.pk,
            "result": "pass_online",
            "next": f"{url}?q=Result",
        })
        self.assertRedirects(unconfirmed, f"{url}?q=Result", fetch_redirect_response=False)
        person.refresh_from_db()
        self.assertEqual(person.status, Person.Status.IN_PROGRESS)
        self.assertFalse(mock_urlopen.called)

        result = self.client.post(url, {
            "person": person.pk,
            "result": "pass_online",
            "confirmed_result": "pass_online",
            "next": f"{url}?q=Result",
        })

        self.assertRedirects(result, f"{url}?q=Result", fetch_redirect_response=False)
        person.refresh_from_db()
        self.assertEqual(person.status, Person.Status.PASSED)
        self.assertEqual(person.admission_type, Person.AdmissionType.ONLINE)
        self.assertTrue(Student.objects.filter(person=person).exists())
        self.assertTrue(mock_urlopen.called)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertIn("ผ่านสัมภาษณ์ (ออนไลน์)", json.dumps(payload, ensure_ascii=False))
        self.assertIn("interview_passed", person.extra_data["line_notifications"])

        search_again = self.client.get(url, {"q": "Result"})
        self.assertContains(search_again, "Result Applicant")
        self.assertContains(search_again, "ผ่านแบบออนไลน์")

    @patch("school.line.request.urlopen")
    def test_interview_results_page_can_mark_failed_without_line_notice(self, mock_urlopen):
        person = Person.objects.create(
            first_name="Fail",
            last_name="Applicant",
            line_user_id="Ufail",
        )
        url = reverse("school:interview_results")

        response = self.client.post(url, {
            "person": person.pk,
            "result": "fail",
            "confirmed_result": "fail",
            "next": url,
        })

        self.assertRedirects(response, url, fetch_redirect_response=False)
        person.refresh_from_db()
        self.assertEqual(person.status, Person.Status.FAILED)
        self.assertEqual(person.admission_type, "")
        self.assertFalse(mock_urlopen.called)
