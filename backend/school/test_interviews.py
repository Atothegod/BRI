import json
import threading
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
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

        inactive = Person.objects.create(first_name="Inactive", last_name="Student", line_user_id="Uinactive")
        inactive.status = Person.Status.PASSED
        inactive.save(update_fields=["status"])
        Student.objects.filter(person=inactive).update(is_paid=True, is_active=False)
        self.assertEqual(self.schedule("orientation", people=[inactive.pk]).status_code, 200)
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
        participants[0].person.refresh_from_db()
        self.assertEqual(participants[0].selected_slot, slot)
        self.assertEqual(participants[0].response_status, AppointmentParticipant.ResponseStatus.CONFIRMED)
        self.assertIsNotNone(participants[0].confirmed_at)
        self.assertEqual(participants[0].person.interview_confirmed_at, participants[0].confirmed_at)

        repeated = self.client.post(
            reverse("school:appointment_confirmation"),
            {"token": first_token, "slot": slot.pk},
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertContains(repeated, "ยืนยันนัดสัมภาษณ์แล้ว")
        self.assertEqual(slot.participants.filter(response_status="confirmed").count(), 1)

        full = self.client.get(reverse("school:appointment_confirmation"), {"token": second_token})
        self.assertContains(full, "เต็มแล้ว")
        rejected = self.client.post(reverse("school:appointment_confirmation"), {"token": second_token, "slot": slot.pk})
        self.assertEqual(rejected.status_code, 409)
        self.assertContains(rejected, "ทีมงานจะนัดวันสัมภาษณ์รอบถัดไปให้อีกครั้ง", status_code=409)
        participants[1].refresh_from_db()
        self.assertEqual(participants[1].response_status, AppointmentParticipant.ResponseStatus.WAITING)
        self.assertIsNone(participants[1].selected_slot)
        self.assertIsNone(participants[1].confirmed_at)

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    def test_person_can_choose_another_slot_when_only_selected_slot_is_full(self):
        self.schedule(
            slot_start=["09:30", "10:30"],
            slot_end=["10:30", "11:30"],
            slot_capacity=["1", "1"],
        )
        participants = list(AppointmentParticipant.objects.order_by("pk"))
        first_slot, second_slot = AppointmentSlot.objects.order_by("starts_at")
        tokens = [
            parse_qs(urlsplit(self.confirmation_url(participant)).query)["token"][0]
            for participant in participants
        ]
        self.client.post(
            reverse("school:appointment_confirmation"),
            {"token": tokens[0], "slot": first_slot.pk},
        )

        admin_view = self.client.get(self.url, {
            "type": "interview",
            "event": Appointment.objects.get().pk,
            "audience": "waiting",
        })
        self.assertContains(admin_view, "09:30-10:30")
        self.assertContains(admin_view, "10:30-11:30")
        self.assertContains(admin_view, "เต็มแล้ว")
        self.assertContains(admin_view, "เหลือ 1 ที่นั่ง")
        slot_status = self.client.post(reverse("school:appointment_confirmation_status"), {
            "event_id": Appointment.objects.get().pk,
        }).json()["event"]["slots"]
        self.assertEqual(slot_status[0]["remaining"], 0)
        self.assertEqual(slot_status[1]["remaining"], 1)

        full_slot = self.client.post(
            reverse("school:appointment_confirmation"),
            {"token": tokens[1], "slot": first_slot.pk},
        )
        self.assertEqual(full_slot.status_code, 409)
        self.assertContains(
            full_slot,
            "ช่วงเวลานี้เต็มแล้ว กรุณาเลือกช่วงเวลาอื่น",
            status_code=409,
        )
        self.assertContains(full_slot, "10:30-11:30", status_code=409)

        available_slot = self.client.post(
            reverse("school:appointment_confirmation"),
            {"token": tokens[1], "slot": second_slot.pk},
        )
        self.assertEqual(available_slot.status_code, 200)
        participants[1].refresh_from_db()
        self.assertEqual(participants[1].selected_slot, second_slot)
        self.assertEqual(
            participants[1].response_status,
            AppointmentParticipant.ResponseStatus.CONFIRMED,
        )

    def test_changing_participant_slot_syncs_person_interview_time(self):
        self.schedule(
            people=[self.people[0].pk],
            slot_start=["09:30", "10:30"],
            slot_end=["10:30", "11:30"],
            slot_capacity=["1", "1"],
        )
        first_slot, second_slot = AppointmentSlot.objects.order_by("starts_at")
        participant = AppointmentParticipant.objects.get()
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        participant.confirmed_at = timezone.now()
        participant.selected_slot = first_slot
        participant.save(update_fields=["response_status", "confirmed_at", "selected_slot"])
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_at, first_slot.starts_at)

        participant.selected_slot = second_slot
        participant.save(update_fields=["selected_slot"])
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_at, second_slot.starts_at)

        second_slot.starts_at = second_slot.starts_at + timedelta(minutes=15)
        second_slot.ends_at = second_slot.ends_at + timedelta(minutes=15)
        second_slot.save(update_fields=["starts_at", "ends_at"])
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_at, second_slot.starts_at)

    def test_slot_capacity_cannot_be_reduced_below_confirmed_count(self):
        self.schedule(slot_capacity=["2"])
        slot = AppointmentSlot.objects.get()
        participant = AppointmentParticipant.objects.order_by("pk").first()
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        participant.selected_slot = slot
        participant.confirmed_at = timezone.now()
        participant.save(update_fields=["response_status", "selected_slot", "confirmed_at"])

        slot.capacity = 0
        with self.assertRaises(ValidationError):
            slot.full_clean()

        slot.capacity = 1
        slot.full_clean()

    @override_settings(
        LINE_MESSAGING_CHANNEL_ACCESS_TOKEN="line-token",
        PUBLIC_BASE_URL="https://bri.example",
    )
    @patch("school.admin.send_line_push_message", return_value=True)
    def test_changing_notified_participant_slot_marks_and_sends_reschedule_notice(self, send):
        self.schedule(
            people=[self.people[0].pk],
            slot_start=["09:30", "10:30"],
            slot_end=["10:30", "11:30"],
            slot_capacity=["1", "1"],
        )
        first_slot, second_slot = AppointmentSlot.objects.order_by("starts_at")
        participant = AppointmentParticipant.objects.get()
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        participant.confirmed_at = timezone.now()
        participant.selected_slot = first_slot
        participant.save(update_fields=["response_status", "confirmed_at", "selected_slot"])
        participant.notification_status = AppointmentParticipant.NotificationStatus.SENT
        participant.notification_count = 1
        participant.notified_at = timezone.now()
        participant.save(update_fields=["notification_status", "notification_count", "notified_at"])
        participant.refresh_from_db()
        self.assertFalse(participant.needs_reschedule_notice)

        participant.selected_slot = second_slot
        participant.save(update_fields=["selected_slot"])
        participant.refresh_from_db()
        self.assertTrue(participant.needs_reschedule_notice)
        admin_url = reverse("admin:school_appointmentparticipant_changelist")
        filtered = self.client.get(admin_url, {"reschedule_notice": "required"})
        self.assertContains(filtered, self.people[0].full_name)

        response = self.client.post(
            admin_url,
            {
                "action": "send_interview_reschedule_line_notification",
                "_selected_action": [participant.pk],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        send.assert_called_once()
        payload = json.dumps(send.call_args.args[1], ensure_ascii=False)
        self.assertIn("แจ้งเปลี่ยนเวลาสัมภาษณ์", payload)
        self.assertIn("10:30-11:30", payload)
        participant.refresh_from_db()
        self.assertFalse(participant.needs_reschedule_notice)
        self.assertEqual(participant.notification_count, 2)

    def test_changing_notified_slot_time_marks_reschedule_notice(self):
        self.schedule(people=[self.people[0].pk], slot_capacity=["1"])
        slot = AppointmentSlot.objects.get()
        participant = AppointmentParticipant.objects.get()
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        participant.confirmed_at = timezone.now()
        participant.selected_slot = slot
        participant.notification_status = AppointmentParticipant.NotificationStatus.SENT
        participant.notification_count = 1
        participant.notified_at = timezone.now()
        participant.save(update_fields=[
            "response_status",
            "confirmed_at",
            "selected_slot",
            "notification_status",
            "notification_count",
            "notified_at",
        ])
        participant.refresh_from_db()
        self.assertFalse(participant.needs_reschedule_notice)

        slot.starts_at = slot.starts_at + timedelta(minutes=15)
        slot.ends_at = slot.ends_at + timedelta(minutes=15)
        slot.save(update_fields=["starts_at", "ends_at"])

        participant.refresh_from_db()
        self.assertTrue(participant.needs_reschedule_notice)

    def test_saving_old_participant_does_not_overwrite_newer_interview_snapshot(self):
        self.schedule(people=[self.people[0].pk], slot_capacity=["1"])
        old_participant = AppointmentParticipant.objects.get()
        next_event = Appointment.objects.create(
            appointment_type=Appointment.Type.INTERVIEW,
            title="สัมภาษณ์รอบใหม่",
            starts_at=self.at + timedelta(days=7),
        )
        next_slot = AppointmentSlot.objects.create(
            appointment=next_event,
            starts_at=self.at + timedelta(days=7, hours=1),
            ends_at=self.at + timedelta(days=7, hours=2),
            capacity=1,
        )
        AppointmentParticipant.objects.create(
            appointment=next_event,
            person=self.people[0],
            selected_slot=next_slot,
            notification_status=AppointmentParticipant.NotificationStatus.SENT,
        )
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_at, next_slot.starts_at)

        old_participant.notification_status = AppointmentParticipant.NotificationStatus.FAILED
        old_participant.save(update_fields=["notification_status"])
        self.people[0].refresh_from_db()
        self.assertEqual(self.people[0].interview_at, next_slot.starts_at)

    def test_participant_slot_must_belong_to_same_event(self):
        self.schedule(people=[self.people[0].pk])
        participant = AppointmentParticipant.objects.get()
        other_event = Appointment.objects.create(
            appointment_type=Appointment.Type.INTERVIEW,
            title="สัมภาษณ์คนละ Event",
            starts_at=self.at + timedelta(days=3),
        )
        other_slot = AppointmentSlot.objects.create(
            appointment=other_event,
            starts_at=self.at + timedelta(days=3),
            ends_at=self.at + timedelta(days=3, hours=1),
            capacity=1,
        )

        participant.selected_slot = other_slot
        participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED

        with self.assertRaises(ValidationError):
            participant.full_clean()

    def test_participant_cannot_move_to_full_slot_even_before_confirming(self):
        self.schedule(slot_capacity=["1"])
        slot = AppointmentSlot.objects.get()
        first, second = AppointmentParticipant.objects.order_by("pk")
        first.selected_slot = slot
        first.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
        first.confirmed_at = timezone.now()
        first.save(update_fields=["selected_slot", "response_status", "confirmed_at"])

        second.selected_slot = slot
        second.response_status = AppointmentParticipant.ResponseStatus.WAITING

        with self.assertRaises(ValidationError):
            second.full_clean()

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

    def test_people_can_be_filtered_into_metro_and_provincial_groups(self):
        self.people[0].extra_data = {"province": "กรุงเทพมหานคร"}
        self.people[0].save(update_fields=["extra_data"])
        self.people[1].extra_data = {"address_th": {"province": "เชียงใหม่"}}
        self.people[1].save(update_fields=["extra_data"])
        unknown = Person.objects.create(
            first_name="Unknown", last_name="Province", line_user_id="Uunknown"
        )

        metro = self.client.get(self.url, {
            "type": "interview", "event": "new", "province": "metro",
        })
        self.assertContains(metro, self.people[0].full_name)
        self.assertNotContains(metro, self.people[1].full_name)
        self.assertNotContains(metro, unknown.full_name)

        provincial = self.client.get(self.url, {
            "type": "interview", "event": "new", "province": "provincial",
        })
        self.assertContains(provincial, self.people[1].full_name)
        self.assertNotContains(provincial, self.people[0].full_name)
        self.assertNotContains(provincial, unknown.full_name)

    @override_settings(PUBLIC_BASE_URL="https://bri.example")
    @patch("school.interviews.send_line_push_message", return_value=True)
    def test_one_event_supports_per_batch_messages_and_explicit_resend(self, send):
        self.people[0].extra_data = {"province": "กรุงเทพมหานคร"}
        self.people[0].save(update_fields=["extra_data"])
        self.people[1].extra_data = {"province": "เชียงใหม่"}
        self.people[1].save(update_fields=["extra_data"])
        self.schedule(
            people=[self.people[0].pk],
            location="BRI Bangkok",
            meeting_url="",
            details="มาสัมภาษณ์ที่สถาบัน",
        )
        appointment = Appointment.objects.get()
        metro_participant = appointment.participants.get(person=self.people[0])

        self.assertTrue(self.notify(metro_participant).json()["sent"])
        metro_participant.refresh_from_db()
        self.assertEqual(metro_participant.notification_count, 1)

        added = self.client.post(self.url, {
            "appointment_type": "interview",
            "event_id": appointment.pk,
            "people": [self.people[1].pk],
            "location": "ออนไลน์",
            "meeting_url": "",
            "details": "สัมภาษณ์ออนไลน์",
        })
        self.assertEqual(added.status_code, 302)
        self.assertEqual(Appointment.objects.count(), 1)
        provincial_participant = appointment.participants.get(person=self.people[1])

        metro_message = json.dumps(
            build_appointment_invitation_flex_message(metro_participant),
            ensure_ascii=False,
        )
        provincial_message = json.dumps(
            build_appointment_invitation_flex_message(provincial_participant),
            ensure_ascii=False,
        )
        self.assertIn("BRI Bangkok", metro_message)
        self.assertNotIn("BRI Bangkok", provincial_message)
        self.assertIn("ออนไลน์", provincial_message)
        self.assertIn("สัมภาษณ์ออนไลน์", provincial_message)

        confirmation = self.client.get(self.confirmation_url(provincial_participant))
        self.assertContains(confirmation, "ออนไลน์")
        self.assertContains(confirmation, "สัมภาษณ์ออนไลน์")
        self.assertNotContains(confirmation, "BRI Bangkok")

        waiting = self.client.get(self.url, {
            "type": "interview", "event": appointment.pk, "audience": "waiting",
        })
        place_options = {
            option["label"]: option["key"]
            for option in waiting.context["place_options"]
        }
        self.assertIn("BRI Bangkok", place_options)
        self.assertIn("ออนไลน์", place_options)

        onsite_page = self.client.get(self.url, {
            "type": "interview",
            "event": appointment.pk,
            "audience": "waiting",
            "place": place_options["BRI Bangkok"],
        })
        self.assertContains(onsite_page, self.people[0].full_name)
        self.assertNotContains(onsite_page, self.people[1].full_name)

        online_page = self.client.get(self.url, {
            "type": "interview",
            "event": appointment.pk,
            "audience": "waiting",
            "place": place_options["ออนไลน์"],
        })
        self.assertContains(online_page, self.people[1].full_name)
        self.assertNotContains(online_page, self.people[0].full_name)

        resend = self.client.post(self.url, {
            "action": "resend",
            "appointment_type": "interview",
            "event_id": appointment.pk,
            "audience": "waiting",
            "province": "metro",
            "place": place_options["BRI Bangkok"],
            "participants": [metro_participant.pk],
            "location": "BRI Bangkok อาคารใหม่",
            "meeting_url": "",
            "details": "กรุณามาก่อนเวลา 20 นาที",
        })
        self.assertEqual(resend.status_code, 302)
        queue = self.client.session["appointment_send_queue"]
        self.assertEqual(queue[0]["id"], metro_participant.pk)
        self.assertTrue(queue[0]["force"])
        metro_participant.refresh_from_db()
        self.assertEqual(metro_participant.invitation_location, "BRI Bangkok อาคารใหม่")

        resent = self.client.post(
            reverse("school:appointment_notify", args=[metro_participant.pk]),
            {"at": appointment.starts_at.isoformat(), "force": "1"},
        )
        self.assertTrue(resent.json()["sent"])
        metro_participant.refresh_from_db()
        self.assertEqual(metro_participant.notification_count, 2)
        sent_content = json.dumps(send.call_args.args[1], ensure_ascii=False)
        self.assertIn("BRI Bangkok อาคารใหม่", sent_content)
        self.assertIn("กรุณามาก่อนเวลา 20 นาที", sent_content)

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
        self.assertEqual(reverse("school:interview_roster"), "/school-admin/interview-roster/")
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

    def test_operation_urls_use_operations_prefix(self):
        self.assertEqual(reverse("school:interview_results"), "/operations/interview-results/")
        self.assertEqual(reverse("school:admin_payment_slip_review"), "/operations/payment-slips/")
        self.assertEqual(reverse("school:admin_student_photo_import"), "/operations/student-photos/")

    def test_operation_user_can_view_results_but_not_announcements(self):
        User = get_user_model()
        operation = User.objects.create_user(
            username="operation",
            password="test-password",
            role=User.Role.OPERATION,
        )
        self.client.force_login(operation)

        results = self.client.get(reverse("school:interview_results"))
        announcements = self.client.get(reverse("school:interview_announcements"))

        self.assertEqual(results.status_code, 200)
        self.assertNotContains(results, "ไปหน้ายิงประกาศผล")
        self.assertNotContains(results, reverse("school:interview_announcements"))
        self.assertEqual(announcements.status_code, 403)

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
        self.assertContains(response, "รอตัดสินอีกครั้ง")

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
        self.assertFalse(mock_urlopen.called)
        self.assertNotIn("line_notifications", person.extra_data)

        announcement_url = reverse("school:interview_announcements")
        announcement_page = self.client.get(announcement_url, {"q": "Result"})
        self.assertContains(announcement_page, "Result Applicant")
        self.assertContains(announcement_page, "พร้อมยิง")

        announcement = self.client.post(announcement_url, {
            "people": [person.pk],
            "confirmed_send": "yes",
            "next": f"{announcement_url}?q=Result",
        })

        self.assertRedirects(announcement, f"{announcement_url}?q=Result", fetch_redirect_response=False)
        self.assertTrue(mock_urlopen.called)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertIn("ผ่านสัมภาษณ์ (ออนไลน์)", json.dumps(payload, ensure_ascii=False))
        person.refresh_from_db()
        self.assertIn("interview_passed", person.extra_data["line_notifications"])

        search_again = self.client.get(url, {"q": "Result"})
        self.assertContains(search_again, "Result Applicant")
        self.assertContains(search_again, "ผ่านแบบออนไลน์")

    def test_interview_roster_page_shows_location_instead_of_line_user_ids(self):
        self.people[0].extra_data = {
            "province": "กรุงเทพมหานคร",
            "country_name_th": "ไทย",
        }
        self.people[0].line_display_name = "Applicant 0 LINE"
        self.people[0].save(update_fields=["extra_data", "line_display_name"])
        self.people[1].extra_data = {
            "address_en": {"state_province": "Chiang Mai"},
            "country_name_en": "Thailand",
        }
        self.people[1].line_display_name = "Applicant 1 LINE"
        self.people[1].save(update_fields=["extra_data", "line_display_name"])
        appointment = Appointment.objects.create(
            appointment_type=Appointment.Type.INTERVIEW,
            title="สัมภาษณ์ Online Onsite",
            starts_at=self.at,
            location="BRI Bangkok",
        )
        onsite_slot = AppointmentSlot.objects.create(
            appointment=appointment,
            starts_at=self.at,
            ends_at=self.at + timedelta(hours=1),
            capacity=2,
        )
        online_slot = AppointmentSlot.objects.create(
            appointment=appointment,
            starts_at=self.at + timedelta(hours=1),
            ends_at=self.at + timedelta(hours=2),
            capacity=2,
        )
        AppointmentParticipant.objects.create(
            appointment=appointment,
            person=self.people[0],
            selected_slot=onsite_slot,
            response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
            confirmed_at=timezone.now(),
            invitation_message={"location": "BRI Bangkok"},
        )
        AppointmentParticipant.objects.create(
            appointment=appointment,
            person=self.people[1],
            selected_slot=online_slot,
            response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
            confirmed_at=timezone.now(),
            invitation_message={
                "location": "ออนไลน์",
                "meeting_url": "https://meet.example/interview",
            },
        )
        url = reverse("school:interview_roster")

        response = self.client.get(url, {"event": appointment.pk})

        self.assertContains(response, "สัมภาษณ์ Online Onsite")
        self.assertContains(response, self.people[0].full_name)
        self.assertContains(response, self.people[1].full_name)
        self.assertContains(response, "กรุงเทพมหานคร")
        self.assertContains(response, "Chiang Mai")
        self.assertContains(response, "ไทย")
        self.assertContains(response, "Thailand")
        self.assertContains(response, "Applicant 0 LINE")
        self.assertNotContains(response, "Utest0")
        self.assertNotContains(response, "Utest1")
        self.assertContains(response, "09:30-10:30")
        self.assertContains(response, "10:30-11:30")
        self.assertContains(response, "Onsite")
        self.assertContains(response, "Online")

        online = self.client.get(url, {"event": appointment.pk, "mode": "online"})
        self.assertContains(online, self.people[1].full_name)
        self.assertNotContains(online, self.people[0].full_name)

    @override_settings(LINE_MESSAGING_CHANNEL_ACCESS_TOKEN="line-token")
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

        announcement_url = reverse("school:interview_announcements")
        announcement = self.client.post(announcement_url, {
            "people": [person.pk],
            "confirmed_send": "yes",
            "next": announcement_url,
        })

        self.assertRedirects(announcement, announcement_url, fetch_redirect_response=False)
        self.assertTrue(mock_urlopen.called)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertIn("ประกาศผลสัมภาษณ์แล้ว", json.dumps(payload, ensure_ascii=False))
        person.refresh_from_db()
        self.assertIn("interview_failed", person.extra_data["line_notifications"])

        reset = self.client.post(url, {
            "person": person.pk,
            "result": "pending",
            "confirmed_result": "pending",
            "next": url,
        })

        self.assertRedirects(reset, url, fetch_redirect_response=False)
        person.refresh_from_db()
        self.assertEqual(person.status, Person.Status.IN_PROGRESS)
        self.assertEqual(person.admission_type, "")


class AppointmentSlotConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_only_one_person_can_take_the_last_slot(self):
        starts_at = timezone.now() + timedelta(days=2)
        appointment = Appointment.objects.create(
            appointment_type=Appointment.Type.INTERVIEW,
            title="สัมภาษณ์ slot สุดท้าย",
            starts_at=starts_at,
        )
        slot = AppointmentSlot.objects.create(
            appointment=appointment,
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            capacity=1,
        )
        participants = []
        for index in range(2):
            person = Person.objects.create(
                first_name=f"Concurrent {index}",
                last_name="Applicant",
                line_user_id=f"Uconcurrent{index}",
            )
            participants.append(
                AppointmentParticipant.objects.create(
                    appointment=appointment,
                    person=person,
                )
            )
        tokens = [
            signing.dumps(
                {
                    "participant_id": participant.pk,
                    "starts_at": appointment.starts_at.isoformat(),
                },
                salt="school.appointment-confirmation",
                compress=True,
            )
            for participant in participants
        ]
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def confirm(token):
            connections.close_all()
            try:
                barrier.wait(timeout=5)
                response = Client().post(
                    reverse("school:appointment_confirmation"),
                    {"token": token, "slot": slot.pk},
                )
                results.append(response.status_code)
            except Exception as error:
                errors.append(error)
            finally:
                connections.close_all()

        threads = [threading.Thread(target=confirm, args=(token,)) for token in tokens]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        self.assertFalse(errors)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(results, [200, 409])
        self.assertEqual(
            AppointmentParticipant.objects.filter(
                selected_slot=slot,
                response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
            ).count(),
            1,
        )
