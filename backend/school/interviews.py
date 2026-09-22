from datetime import datetime
from zoneinfo import ZoneInfo

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .date_formats import thai_date
from .line import build_appointment_invitation_flex_message, line_push_unavailable_reason, send_line_push_message
from .models import Appointment, AppointmentParticipant, AppointmentSlot, Person, line_notification_sent
from .views import is_school_admin

THAI_TIMEZONE = ZoneInfo("Asia/Bangkok")
ADMIN_APPOINTMENT_TYPES = (
    Appointment.Type.INTERVIEW,
    Appointment.Type.ORIENTATION,
)
APPOINTMENT_AUDIENCES = ("unsent", "waiting", "confirmed", "failed", "confirmed_other", "next_round")


def appointment_candidates(appointment_type):
    queryset = Person.objects.all()
    if appointment_type == Appointment.Type.CLASS:
        return queryset.filter(status=Person.Status.PASSED, student__is_active=True)
    if appointment_type == Appointment.Type.ORIENTATION:
        return queryset.filter(status=Person.Status.PASSED, student__is_paid=True)
    return queryset.filter(status=Person.Status.IN_PROGRESS)


def confirmed_interview_people():
    return AppointmentParticipant.objects.filter(
        appointment__appointment_type=Appointment.Type.INTERVIEW,
        response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
    ).values("person_id")


class AppointmentScheduleForm(forms.Form):
    appointment_type = forms.ChoiceField(choices=Appointment.Type.choices, widget=forms.HiddenInput)
    event_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    people = forms.ModelMultipleChoiceField(
        queryset=Person.objects.none(), label="ผู้เข้าร่วม",
        error_messages={"required": "กรุณาเลือกผู้เข้าร่วมอย่างน้อย 1 คน", "invalid_choice": "มีผู้เข้าร่วมที่ไม่ตรงเงื่อนไข กรุณาเลือกใหม่"},
    )
    title = forms.CharField(label="ชื่อกิจกรรม", max_length=255)
    date = forms.DateField(label="วันที่", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(label="เวลา (ประเทศไทย)", widget=forms.TimeInput(attrs={"type": "time"}))
    location = forms.CharField(label="สถานที่", required=False, max_length=500)
    meeting_url = forms.URLField(label="ลิงก์เข้าร่วม (ถ้ามี)", required=False, max_length=1000)
    details = forms.CharField(label="รายละเอียดเพิ่มเติม", required=False, max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, appointment_type=Appointment.Type.INTERVIEW, selected_appointment=None, **kwargs):
        super().__init__(*args, **kwargs)
        if appointment_type not in ADMIN_APPOINTMENT_TYPES:
            appointment_type = Appointment.Type.INTERVIEW
        self.fields["appointment_type"].choices = [
            choice
            for choice in Appointment.Type.choices
            if choice[0] in ADMIN_APPOINTMENT_TYPES
        ]
        self.fields["appointment_type"].initial = appointment_type
        people = appointment_candidates(appointment_type)
        if appointment_type == Appointment.Type.INTERVIEW:
            people = people.exclude(pk__in=confirmed_interview_people())
        if selected_appointment is not None:
            people = people.exclude(appointment_participations__appointment=selected_appointment)
        self.fields["people"].queryset = people
        self.fields["title"].initial = dict(Appointment.Type.choices)[appointment_type]
        self.appointment_type = appointment_type
        self.selected_appointment = selected_appointment
        if selected_appointment is not None:
            self.fields["event_id"].initial = selected_appointment.pk
            for field_name in ("title", "date", "time", "location", "meeting_url", "details"):
                self.fields[field_name].required = False
        if appointment_type == Appointment.Type.INTERVIEW:
            self.fields["time"].required = False
            self.fields["time"].widget = forms.HiddenInput()

    def slot_rows(self):
        if self.is_bound:
            starts = self.data.getlist("slot_start")
            ends = self.data.getlist("slot_end")
            capacities = self.data.getlist("slot_capacity")
            row_count = max(len(starts), len(ends), len(capacities), 1)
            return [
                {
                    "start": starts[index] if index < len(starts) else "",
                    "end": ends[index] if index < len(ends) else "",
                    "capacity": capacities[index] if index < len(capacities) else "",
                }
                for index in range(row_count)
            ]
        return [
            {"start": "13:00", "end": "15:00", "capacity": "35"},
            {"start": "15:00", "end": "17:00", "capacity": "35"},
            {"start": "17:00", "end": "19:00", "capacity": "35"},
            {"start": "19:00", "end": "20:00", "capacity": "35"},
        ]

    def clean(self):
        data = super().clean()
        people = data.get("people")
        if people is not None and len(people) > 500:
            self.add_error("people", "เลือกได้ครั้งละไม่เกิน 500 คน")
        if self.selected_appointment is not None:
            if data.get("event_id") != self.selected_appointment.pk:
                self.add_error("event_id", "Event ที่เลือกมีการเปลี่ยนแปลง กรุณาเลือกใหม่")
            data["appointment"] = self.selected_appointment
            return data
        if data.get("appointment_type") == Appointment.Type.INTERVIEW:
            self.clean_interview_slots(data)
        elif data.get("date") and data.get("time"):
            data["starts_at"] = timezone.make_aware(datetime.combine(data["date"], data["time"]), THAI_TIMEZONE)
            if data["starts_at"] <= timezone.now():
                self.add_error("date", "กรุณาเลือกวันเวลาในอนาคต")
        return data

    def clean_interview_slots(self, data):
        if not data.get("date"):
            return
        slot_defs = []
        time_field = forms.TimeField()
        starts = self.data.getlist("slot_start")
        ends = self.data.getlist("slot_end")
        capacities = self.data.getlist("slot_capacity")
        row_count = max(len(starts), len(ends), len(capacities))
        for index in range(row_count):
            raw_start = starts[index].strip() if index < len(starts) else ""
            raw_end = ends[index].strip() if index < len(ends) else ""
            raw_capacity = capacities[index].strip() if index < len(capacities) else ""
            if not any([raw_start, raw_end, raw_capacity]):
                continue
            if not all([raw_start, raw_end, raw_capacity]):
                self.add_error("date", f"กรุณากรอกข้อมูล slot แถวที่ {index + 1} ให้ครบ")
                continue
            try:
                start_time = time_field.clean(raw_start)
                end_time = time_field.clean(raw_end)
                capacity = int(raw_capacity)
            except (forms.ValidationError, TypeError, ValueError):
                self.add_error("date", f"ข้อมูล slot แถวที่ {index + 1} ไม่ถูกต้อง")
                continue
            if capacity <= 0:
                self.add_error("date", f"quota slot แถวที่ {index + 1} ต้องมากกว่า 0")
                continue
            if end_time <= start_time:
                self.add_error("date", f"เวลาสิ้นสุด slot แถวที่ {index + 1} ต้องมากกว่าเวลาเริ่ม")
                continue
            slot_defs.append({
                "starts_at": timezone.make_aware(datetime.combine(data["date"], start_time), THAI_TIMEZONE),
                "ends_at": timezone.make_aware(datetime.combine(data["date"], end_time), THAI_TIMEZONE),
                "capacity": capacity,
            })
        if not slot_defs:
            self.add_error("date", "กรุณาเพิ่ม slot เวลาอย่างน้อย 1 slot")
            return
        if min(slot["starts_at"] for slot in slot_defs) <= timezone.now():
            self.add_error("date", "กรุณาเลือก slot เวลาในอนาคต")
        data["total_capacity"] = sum(slot["capacity"] for slot in slot_defs)
        data["slot_defs"] = slot_defs
        data["starts_at"] = min(slot["starts_at"] for slot in slot_defs)


def selected_appointment_type(request):
    value = request.POST.get("appointment_type") or request.GET.get("type")
    return value if value in ADMIN_APPOINTMENT_TYPES else Appointment.Type.INTERVIEW


def appointment_capacity(appointment):
    return sum(slot.capacity for slot in appointment.slots.all())


def appointment_is_full(appointment, confirmed_count=None):
    capacity = appointment_capacity(appointment)
    if not capacity:
        return False
    if confirmed_count is None:
        confirmed_count = appointment.participants.filter(
            response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
        ).count()
    return confirmed_count >= capacity


def waiting_participations_for_next_round(appointment):
    return AppointmentParticipant.objects.filter(
        appointment=appointment,
        response_status=AppointmentParticipant.ResponseStatus.WAITING,
    ).exclude(notification_status=AppointmentParticipant.NotificationStatus.FAILED)


def latest_interview_participations(person_ids):
    latest_by_person = {}
    if not person_ids:
        return latest_by_person
    participants = (
        AppointmentParticipant.objects.filter(
            person_id__in=person_ids,
            appointment__appointment_type=Appointment.Type.INTERVIEW,
        )
        .select_related("appointment", "selected_slot")
        .order_by("person_id", "-pk")
    )
    for participant in participants:
        latest_by_person.setdefault(participant.person_id, participant)
    return latest_by_person


def update_interview_result(person, result):
    if result == "pass_online":
        person.status = Person.Status.PASSED
        person.admission_type = Person.AdmissionType.ONLINE
        person.save(update_fields=["status", "admission_type"])
        return "ผ่านแบบ online"
    if result == "pass_onsite":
        person.status = Person.Status.PASSED
        person.admission_type = Person.AdmissionType.INTERVIEW
        person.save(update_fields=["status", "admission_type"])
        return "ผ่านแบบ onsite"
    if result == "fail":
        person.status = Person.Status.FAILED
        person.admission_type = ""
        person.save(update_fields=["status", "admission_type"])
        return "ไม่ผ่าน"
    return ""


@login_required(login_url="admin:login")
@never_cache
@require_http_methods(["GET", "POST"])
def interview_results(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    if request.method == "POST":
        person = Person.objects.filter(pk=request.POST.get("person")).first()
        result_label = update_interview_result(person, request.POST.get("result")) if person else ""
        if not person or not result_label:
            messages.error(request, "ไม่พบผู้สมัครหรือสถานะผลสัมภาษณ์ไม่ถูกต้อง")
        elif person.status == Person.Status.PASSED:
            person.refresh_from_db()
            if line_notification_sent(person, "interview_passed"):
                messages.success(request, f"บันทึกผล {person.full_name}: {result_label} และส่ง LINE ประกาศผลแล้ว")
            else:
                reason = line_push_unavailable_reason(person)
                if reason == "missing_line_user_id":
                    messages.warning(request, f"บันทึกผล {person.full_name}: {result_label} แล้ว แต่ยังไม่ได้ส่ง LINE เพราะผู้สมัครยังไม่เชื่อม LINE")
                elif reason == "missing_channel_access_token":
                    messages.warning(request, f"บันทึกผล {person.full_name}: {result_label} แล้ว แต่ยังไม่ได้ส่ง LINE เพราะยังไม่ได้ตั้ง LINE token")
                else:
                    messages.warning(request, f"บันทึกผล {person.full_name}: {result_label} แล้ว แต่ LINE ยังส่งไม่สำเร็จ")
        else:
            messages.success(request, f"บันทึกผล {person.full_name}: {result_label} แล้ว")
        redirect_to = request.POST.get("next") or reverse("school:interview_results")
        return redirect(redirect_to)

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status") or ("all" if query else "pending")
    people = Person.objects.all().order_by("first_name", "last_name", "pk")
    if status == "passed":
        people = people.filter(status=Person.Status.PASSED)
    elif status == "failed":
        people = people.filter(status=Person.Status.FAILED)
    elif status == "all":
        pass
    else:
        status = "pending"
        people = people.filter(status=Person.Status.IN_PROGRESS)
    if query:
        people = people.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(nickname__icontains=query)
            | Q(phone__icontains=query)
            | Q(line_display_name__icontains=query)
        )
    counts = {
        "pending": Person.objects.filter(status=Person.Status.IN_PROGRESS).count(),
        "passed": Person.objects.filter(status=Person.Status.PASSED).count(),
        "failed": Person.objects.filter(status=Person.Status.FAILED).count(),
        "all": Person.objects.count(),
    }
    page = Paginator(people, 60).get_page(request.GET.get("page"))
    latest_by_person = latest_interview_participations([person.pk for person in page.object_list])
    for person in page.object_list:
        person.latest_interview_participant = latest_by_person.get(person.pk)
        person.has_result_line_notification = line_notification_sent(person, "interview_passed")
        person.student_record = getattr(person, "student", None)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    return render(request, "school/interview_results.html", {
        "page_obj": page,
        "query": query,
        "status": status,
        "counts": counts,
        "page_query_prefix": f"?{query_params.urlencode()}&" if query_params else "?",
        "next_url": request.get_full_path(),
    })


@login_required(login_url="admin:login")
@never_cache
def interview_schedule(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    appointment_type = selected_appointment_type(request)
    appointments = list(Appointment.objects.filter(appointment_type=appointment_type).prefetch_related("slots").annotate(
        participant_count=Count("participants", distinct=True),
        confirmed_count=Count("participants", filter=Q(participants__response_status="confirmed"), distinct=True),
        sent_count=Count("participants", filter=Q(participants__notification_status="sent"), distinct=True),
        failed_count=Count("participants", filter=Q(participants__notification_status="failed"), distinct=True),
    )[:12])
    for appointment in appointments:
        appointment.slot_capacity = appointment_capacity(appointment)
        appointment.is_full = appointment_is_full(appointment, appointment.confirmed_count)

    requested_event = request.POST.get("event_id") if request.method == "POST" else request.GET.get("event")
    selected_appointment = None
    if requested_event and requested_event != "new":
        try:
            requested_event_id = int(requested_event)
        except (TypeError, ValueError):
            requested_event_id = None
        selected_appointment = next(
            (appointment for appointment in appointments if appointment.pk == requested_event_id),
            None,
        )
        if selected_appointment is None and requested_event_id:
            selected_appointment = Appointment.objects.filter(
                pk=requested_event_id,
                appointment_type=appointment_type,
            ).prefetch_related("slots").annotate(
                participant_count=Count("participants", distinct=True),
                confirmed_count=Count("participants", filter=Q(participants__response_status="confirmed"), distinct=True),
                sent_count=Count("participants", filter=Q(participants__notification_status="sent"), distinct=True),
                failed_count=Count("participants", filter=Q(participants__notification_status="failed"), distinct=True),
            ).first()
            if selected_appointment:
                selected_appointment.slot_capacity = appointment_capacity(selected_appointment)
                selected_appointment.is_full = appointment_is_full(selected_appointment, selected_appointment.confirmed_count)
    elif request.method != "POST" and requested_event != "new" and appointments:
        selected_appointment = appointments[0]
    source_appointment = None
    if appointment_type == Appointment.Type.INTERVIEW and selected_appointment is None:
        try:
            source_event_id = int(request.GET.get("source_event", ""))
        except (TypeError, ValueError):
            source_event_id = None
        if source_event_id:
            source_appointment = Appointment.objects.filter(
                pk=source_event_id,
                appointment_type=Appointment.Type.INTERVIEW,
            ).prefetch_related("slots").annotate(
                confirmed_count=Count("participants", filter=Q(participants__response_status="confirmed"), distinct=True),
            ).first()
            if source_appointment:
                source_appointment.slot_capacity = appointment_capacity(source_appointment)
                source_appointment.is_full = appointment_is_full(source_appointment, source_appointment.confirmed_count)

    form = AppointmentScheduleForm(
        request.POST or None,
        appointment_type=appointment_type,
        selected_appointment=selected_appointment,
    )
    invalid_requested_event = bool(requested_event and requested_event != "new" and selected_appointment is None)
    if request.method == "POST" and invalid_requested_event:
        form.is_valid()
        form.add_error("event_id", "ไม่พบ Event ที่เลือก กรุณาเลือก Event ใหม่")
    if request.method == "POST" and not invalid_requested_event and form.is_valid():
        ids = list(form.cleaned_data["people"].values_list("pk", flat=True))
        appointment_type = form.cleaned_data["appointment_type"]
        with transaction.atomic():
            people = list(appointment_candidates(appointment_type).select_for_update().filter(pk__in=ids).order_by("pk"))
            if len(people) != len(ids):
                form.add_error("people", "สถานะผู้เข้าร่วมเปลี่ยนแล้ว กรุณาเลือกใหม่")
            elif selected_appointment is not None and selected_appointment.participants.filter(person_id__in=ids).exists():
                form.add_error("people", "มีผู้สมัครบางคนอยู่ใน Event นี้แล้ว กรุณาโหลดรายชื่อใหม่")
            elif selected_appointment is not None and (
                selected_appointment.status != Appointment.Status.SCHEDULED
                or not appointment_is_confirmable(selected_appointment)
                or appointment_is_full(selected_appointment)
            ):
                form.add_error("people", "Event นี้เต็มหรือปิดรับแล้ว กรุณาสร้าง Event ใหม่")
            else:
                appointment = selected_appointment
                if appointment is None:
                    appointment = Appointment.objects.create(
                        appointment_type=appointment_type, title=form.cleaned_data["title"],
                        starts_at=form.cleaned_data["starts_at"], location=form.cleaned_data["location"],
                        meeting_url=form.cleaned_data["meeting_url"], details=form.cleaned_data["details"],
                        created_by=request.user,
                    )
                    AppointmentSlot.objects.bulk_create([
                        AppointmentSlot(appointment=appointment, **slot)
                        for slot in form.cleaned_data.get("slot_defs", [])
                    ])
                participants = AppointmentParticipant.objects.bulk_create([
                    AppointmentParticipant(appointment=appointment, person=person) for person in people
                ])
                if appointment_type == Appointment.Type.INTERVIEW:
                    legacy_details = "\n".join(filter(None, [appointment.location, appointment.meeting_url, appointment.details]))
                    Person.objects.filter(pk__in=ids).update(
                        interview_at=appointment.starts_at, interview_details=legacy_details,
                        interview_notification_state="pending", interview_notified_at=None,
                        interview_confirmed_at=None, updated_at=timezone.now(),
                    )
        if not form.errors:
            request.session["appointment_send_queue"] = [
                {"id": participant.pk, "at": appointment.starts_at.isoformat()} for participant in participants
            ]
            action = "เพิ่มเข้า Event และเตรียมส่ง" if selected_appointment else "สร้าง Event และเตรียมส่ง"
            messages.success(request, f"{action} LINE ให้ {len(ids)} คนแล้ว")
            return redirect(f"{reverse('school:appointment_schedule')}?type={appointment_type}&event={appointment.pk}&audience=waiting")

    query = request.GET.get("q", "").strip()
    filters = {key: request.GET.get(key, "") for key in ("appointment", "line", "notification", "confirmation")}
    audience = request.GET.get("audience", "")
    if audience == "sent":
        audience = "waiting"
    if audience not in APPOINTMENT_AUDIENCES:
        if filters["notification"] == AppointmentParticipant.NotificationStatus.FAILED:
            audience = "failed"
        elif filters["confirmation"] == AppointmentParticipant.ResponseStatus.CONFIRMED:
            audience = "confirmed"
        elif filters["appointment"] == "scheduled" or filters["notification"] in (
            AppointmentParticipant.NotificationStatus.PENDING,
            AppointmentParticipant.NotificationStatus.SENT,
        ):
            audience = "waiting"
        else:
            audience = "unsent"
    if audience == "next_round" and appointment_type != Appointment.Type.INTERVIEW:
        audience = "unsent"
    if audience == "next_round" and selected_appointment is None and source_appointment is None:
        audience = "unsent"
    people = appointment_candidates(appointment_type).order_by("-created_at", "-pk")
    participations = AppointmentParticipant.objects.none()
    confirmed_people = confirmed_interview_people() if appointment_type == Appointment.Type.INTERVIEW else Person.objects.none().values("pk")
    if selected_appointment is None:
        if audience == "next_round" and source_appointment is not None:
            people = people.filter(
                pk__in=waiting_participations_for_next_round(source_appointment).values("person_id"),
            ).exclude(pk__in=confirmed_people)
        elif audience == "confirmed_other" and appointment_type == Appointment.Type.INTERVIEW:
            people = people.filter(pk__in=confirmed_people)
        elif audience == "unsent":
            people = people.exclude(pk__in=confirmed_people)
    audience_counts = {
        "unsent": people.count(),
        "waiting": 0,
        "confirmed": 0,
        "failed": 0,
        "next_round": people.count() if audience == "next_round" and source_appointment is not None else 0,
        "confirmed_other": appointment_candidates(appointment_type).filter(pk__in=confirmed_people).count()
        if appointment_type == Appointment.Type.INTERVIEW else 0,
    }
    if selected_appointment is not None:
        participations = AppointmentParticipant.objects.filter(appointment=selected_appointment)
        participant_people = participations.values("person_id")
        waiting_participations = waiting_participations_for_next_round(selected_appointment)
        confirmed_participations = participations.filter(
            response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
        )
        next_round_participations = waiting_participations if (
            appointment_type == Appointment.Type.INTERVIEW and selected_appointment.is_full
        ) else AppointmentParticipant.objects.none()
        audience_counts = {
            "unsent": people.exclude(pk__in=participant_people).exclude(pk__in=confirmed_people).count(),
            "waiting": waiting_participations.count(),
            "confirmed": confirmed_participations.count(),
            "failed": participations.filter(notification_status=AppointmentParticipant.NotificationStatus.FAILED).count(),
            "next_round": next_round_participations.count(),
            "confirmed_other": people.filter(pk__in=confirmed_people).exclude(
                pk__in=confirmed_participations.values("person_id"),
            ).count() if appointment_type == Appointment.Type.INTERVIEW else 0,
        }
        if audience == "unsent":
            people = people.exclude(pk__in=participant_people).exclude(pk__in=confirmed_people)
        elif audience == "confirmed_other":
            people = people.filter(pk__in=confirmed_people).exclude(
                pk__in=confirmed_participations.values("person_id"),
            )
        elif audience == "confirmed":
            people = people.filter(pk__in=confirmed_participations.values("person_id"))
        elif audience == "failed":
            people = people.filter(pk__in=participations.filter(
                notification_status=AppointmentParticipant.NotificationStatus.FAILED,
            ).values("person_id"))
        elif audience == "next_round":
            people = people.filter(pk__in=next_round_participations.values("person_id"))
        else:
            people = people.filter(pk__in=waiting_participations.values("person_id"))
    if query:
        people = people.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(phone__icontains=query) | Q(line_display_name__icontains=query))
    if filters["line"] == "connected":
        people = people.exclude(line_user_id="")
    elif filters["line"] == "missing":
        people = people.filter(line_user_id="")
    if selected_appointment is not None and filters["notification"] in AppointmentParticipant.NotificationStatus.values:
        people = people.filter(appointment_participations__in=participations.filter(notification_status=filters["notification"]))
    if selected_appointment is not None and filters["confirmation"] == "confirmed":
        people = people.filter(appointment_participations__in=participations.filter(response_status="confirmed"))
    elif selected_appointment is not None and filters["confirmation"] == "waiting":
        people = people.filter(appointment_participations__in=participations.filter(response_status="waiting"))
    people = people.distinct()
    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params["type"] = appointment_type
    query_params["event"] = selected_appointment.pk if selected_appointment else "new"
    query_params["audience"] = audience
    if source_appointment is not None:
        query_params["source_event"] = source_appointment.pk
    filter_query = query_params.urlencode()
    page = Paginator(people, 200).get_page(request.GET.get("page"))
    page_person_ids = [person.pk for person in page.object_list]
    event_by_person = {}
    latest_by_person = {}
    confirmed_by_person = {}
    if page_person_ids:
        if selected_appointment is not None:
            for participant in participations.filter(person_id__in=page_person_ids).select_related("appointment", "selected_slot").order_by("person_id", "-pk"):
                event_by_person.setdefault(participant.person_id, participant)
        global_participations = (
            AppointmentParticipant.objects.filter(
                person_id__in=page_person_ids,
                appointment__appointment_type=appointment_type,
            )
            .select_related("appointment", "selected_slot")
            .order_by("person_id", "-pk")
        )
        for participant in global_participations:
            if participant.response_status == AppointmentParticipant.ResponseStatus.CONFIRMED:
                confirmed_by_person.setdefault(participant.person_id, participant)
            latest_by_person.setdefault(participant.person_id, participant)
    for person in page.object_list:
        person.latest_appointment_participant = event_by_person.get(person.pk)
        person.overall_appointment_participant = confirmed_by_person.get(person.pk) or latest_by_person.get(person.pk)
        person.confirmed_appointment_participant = confirmed_by_person.get(person.pk)
    selected_event_open = bool(
        selected_appointment
        and selected_appointment.status == Appointment.Status.SCHEDULED
        and appointment_is_confirmable(selected_appointment)
        and not selected_appointment.is_full
    )
    return render(request, "school/interview_schedule.html", {
        "form": form, "page_obj": page, "query": query, "filters": filters,
        "has_filters": bool(query or any(filters.values())),
        "page_query_prefix": f"?{filter_query}&" if filter_query else "?",
        "selected_ids": request.POST.getlist("people"),
        "send_queue": request.session.pop("appointment_send_queue", []),
        "appointment_type": appointment_type,
        "appointment_types": [
            choice
            for choice in Appointment.Type.choices
            if choice[0] in ADMIN_APPOINTMENT_TYPES
        ],
        "candidate_description": "นักศึกษาที่ผ่านการคัดเลือกและชำระเงินแล้ว" if appointment_type == Appointment.Type.ORIENTATION else "ผู้สมัครที่อยู่ระหว่างดำเนินการ",
        "appointments": appointments,
        "selected_appointment": selected_appointment,
        "source_appointment": source_appointment,
        "selected_event_open": selected_event_open,
        "audience": audience,
        "audience_counts": audience_counts,
        "slot_rows": form.slot_rows(),
    })


@login_required(login_url="admin:login")
@require_POST
def interview_notify(request, pk):
    if not is_school_admin(request.user):
        raise PermissionDenied
    with transaction.atomic():
        participant = AppointmentParticipant.objects.select_for_update().select_related("appointment", "person").filter(pk=pk).first()
        if participant is None:
            return JsonResponse({"error": "ไม่พบผู้เข้าร่วม"}, status=404)
        appointment = participant.appointment
        try:
            expected = parse_datetime(request.POST.get("at", ""))
        except ValueError:
            expected = None
        if appointment.status != Appointment.Status.SCHEDULED or not appointment_is_confirmable(appointment) or expected != appointment.starts_at:
            return JsonResponse({"error": "นัดนี้มีการเปลี่ยนแปลงหรือไม่สามารถส่งได้แล้ว"}, status=409)
        if not appointment_candidates(appointment.appointment_type).filter(pk=participant.person_id).exists():
            return JsonResponse({"error": "สถานะผู้เข้าร่วมไม่ตรงเงื่อนไขแล้ว"}, status=409)
        if participant.notification_status == AppointmentParticipant.NotificationStatus.SENT:
            return JsonResponse({"sent": True, "label": "LINE รับข้อความแล้ว"})
        if appointment.appointment_type == Appointment.Type.INTERVIEW and appointment_is_full(appointment):
            return JsonResponse({"error": "รอบสัมภาษณ์เต็มแล้ว กรุณาสร้าง Event ใหม่"}, status=409)
        sent = send_line_push_message(participant.person.line_user_id, [build_appointment_invitation_flex_message(participant)])
        participant.notification_status = AppointmentParticipant.NotificationStatus.SENT if sent else AppointmentParticipant.NotificationStatus.FAILED
        participant.notified_at = timezone.now() if sent else None
        participant.notification_error = "" if sent else "LINE ไม่รับข้อความ โปรดตรวจ token และการเชื่อมต่อ"
        participant.save(update_fields=["notification_status", "notified_at", "notification_error", "updated_at"])
        if appointment.appointment_type == Appointment.Type.INTERVIEW:
            Person.objects.filter(pk=participant.person_id).update(
                interview_notification_state=participant.notification_status,
                interview_notified_at=participant.notified_at,
            )
        return JsonResponse({"sent": sent, "label": "LINE รับข้อความแล้ว" if sent else "ส่งไม่สำเร็จ ตรวจสอบ LINE / token แล้วลองใหม่"})


@login_required(login_url="admin:login")
@require_POST
def interview_confirmation_status(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    try:
        ids = list(dict.fromkeys(int(value) for value in request.POST.getlist("participants")))[:50]
    except (TypeError, ValueError):
        return JsonResponse({"error": "ข้อมูลผู้เข้าร่วมไม่ถูกต้อง"}, status=400)
    items = AppointmentParticipant.objects.filter(pk__in=ids).values("pk", "response_status", "confirmed_at")
    event = None
    try:
        event_id = int(request.POST.get("event_id", ""))
    except (TypeError, ValueError):
        event_id = None
    if event_id:
        appointment = Appointment.objects.filter(pk=event_id).prefetch_related("slots").annotate(
            confirmed_count=Count(
                "participants",
                filter=Q(participants__response_status=AppointmentParticipant.ResponseStatus.CONFIRMED),
                distinct=True,
            ),
            sent_count=Count(
                "participants",
                filter=Q(participants__notification_status=AppointmentParticipant.NotificationStatus.SENT),
                distinct=True,
            ),
            failed_count=Count(
                "participants",
                filter=Q(participants__notification_status=AppointmentParticipant.NotificationStatus.FAILED),
                distinct=True,
            ),
            waiting_count=Count(
                "participants",
                filter=(
                    Q(participants__response_status=AppointmentParticipant.ResponseStatus.WAITING)
                    & ~Q(participants__notification_status=AppointmentParticipant.NotificationStatus.FAILED)
                ),
                distinct=True,
            ),
            invited_count=Count(
                "participants",
                filter=~Q(participants__notification_status=AppointmentParticipant.NotificationStatus.FAILED),
                distinct=True,
            ),
        ).first()
        if appointment:
            capacity = appointment_capacity(appointment)
            event = {
                "confirmed_count": appointment.confirmed_count,
                "capacity": capacity,
                "is_full": bool(capacity and appointment.confirmed_count >= capacity),
                "sent_count": appointment.sent_count,
                "failed_count": appointment.failed_count,
                "waiting_count": appointment.waiting_count,
                "invited_count": appointment.invited_count,
            }
    return JsonResponse({"participants": {str(item["pk"]): {
        "status": item["response_status"],
        "confirmed_at": thai_date(item["confirmed_at"], include_time=True) if item["confirmed_at"] else None,
    } for item in items}, "event": event})


def appointment_is_confirmable(appointment):
    if appointment.slots.exists():
        return appointment.slots.filter(ends_at__gt=timezone.now()).exists()
    return appointment.starts_at > timezone.now()


def interview_slot_options(appointment, selected_slot_id=None):
    slots = appointment.slots.annotate(
        confirmed_count=Count(
            "participants",
            filter=Q(participants__response_status=AppointmentParticipant.ResponseStatus.CONFIRMED),
        )
    ).order_by("starts_at", "pk")
    options = []
    has_default = False
    for slot in slots:
        remaining = max(slot.capacity - slot.confirmed_count, 0)
        local_start = timezone.localtime(slot.starts_at, THAI_TIMEZONE)
        local_end = timezone.localtime(slot.ends_at, THAI_TIMEZONE)
        is_selected = selected_slot_id == slot.pk
        is_default = not selected_slot_id and not has_default and remaining > 0
        has_default = has_default or is_default
        options.append({
            "id": slot.pk,
            "label": f"{local_start:%H:%M}-{local_end:%H:%M}",
            "capacity": slot.capacity,
            "confirmed_count": slot.confirmed_count,
            "remaining": remaining,
            "is_full": remaining <= 0,
            "is_selected": is_selected,
            "is_default": is_default,
        })
    return options


def resolve_confirmation_token(token):
    try:
        payload = signing.loads(token, salt="school.appointment-confirmation")
        return int(payload["participant_id"]), parse_datetime(payload["starts_at"])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        pass
    try:
        payload = signing.loads(token, salt="school.interview-confirmation")
        person_id = int(payload["person_id"])
        expected_at = parse_datetime(payload["interview_at"])
        participant_id = AppointmentParticipant.objects.filter(
            person_id=person_id, appointment__appointment_type=Appointment.Type.INTERVIEW,
            appointment__starts_at=expected_at,
        ).order_by("-pk").values_list("pk", flat=True).first()
        return participant_id, expected_at
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return None, None


@never_cache
@require_http_methods(["GET", "POST"])
def interview_confirmation(request):
    token = request.GET.get("token", "") or request.POST.get("token", "")
    participant_id, expected_at = resolve_confirmation_token(token)
    if not participant_id:
        return render(
            request,
            "school/interview_confirmation.html",
            {"confirmation_state": "invalid"},
            status=400,
        )
    with transaction.atomic():
        participant = AppointmentParticipant.objects.select_for_update().select_related("appointment", "person").filter(pk=participant_id).first()
        valid = (
            participant is not None and expected_at is not None
            and participant.appointment.starts_at == expected_at
            and participant.appointment.status == Appointment.Status.SCHEDULED
            and appointment_is_confirmable(participant.appointment)
            and appointment_candidates(participant.appointment.appointment_type).filter(pk=participant.person_id).exists()
        )
        if not valid:
            return render(
                request,
                "school/interview_confirmation.html",
                {"confirmation_state": "stale"},
                status=409,
            )
        slot_error = ""
        has_slots = participant.appointment.slots.exists()
        if request.method == "POST" and participant.response_status != AppointmentParticipant.ResponseStatus.CONFIRMED:
            selected_slot = None
            if has_slots:
                try:
                    slot_id = int(request.POST.get("slot", ""))
                except (TypeError, ValueError):
                    slot_id = None
                selected_slot = AppointmentSlot.objects.select_for_update().filter(
                    pk=slot_id,
                    appointment=participant.appointment,
                    ends_at__gt=timezone.now(),
                ).first()
                if selected_slot is None:
                    slot_error = "กรุณาเลือกช่วงเวลาที่ยังเปิดให้ยืนยัน"
                elif AppointmentParticipant.objects.filter(
                    selected_slot=selected_slot,
                    response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
                ).count() >= selected_slot.capacity:
                    slot_error = "ช่วงเวลานี้เต็มแล้ว กรุณาเลือกช่วงเวลาอื่น"
            if not slot_error:
                participant.response_status = AppointmentParticipant.ResponseStatus.CONFIRMED
                participant.confirmed_at = timezone.now()
                if selected_slot:
                    participant.selected_slot = selected_slot
                participant.save(update_fields=["response_status", "confirmed_at", "selected_slot", "updated_at"])
                if participant.appointment.appointment_type == Appointment.Type.INTERVIEW:
                    Person.objects.filter(pk=participant.person_id).update(interview_confirmed_at=participant.confirmed_at)
    is_orientation = participant.appointment.appointment_type == Appointment.Type.ORIENTATION
    is_class = participant.appointment.appointment_type == Appointment.Type.CLASS
    slot_options = interview_slot_options(participant.appointment, participant.selected_slot_id)
    slots_are_full = bool(slot_options) and all(slot["is_full"] for slot in slot_options)
    confirmation_state = "confirmed" if participant.response_status == AppointmentParticipant.ResponseStatus.CONFIRMED else "ready"
    if confirmation_state == "ready" and slots_are_full:
        confirmation_state = "full"
    return render(request, "school/interview_confirmation.html", {
        "confirmation_state": confirmation_state,
        "person": participant.person, "appointment": participant.appointment, "token": token,
        "slot_options": slot_options, "slots_are_full": slots_are_full,
        "selected_slot": participant.selected_slot, "slot_error": slot_error,
        "event_eyebrow": "BRI Orientation" if is_orientation else "BRI Class" if is_class else "BRI Interview",
        "event_heading": "ยืนยันเข้าร่วมปฐมนิเทศ" if is_orientation else "ยืนยันนัดเรียน" if is_class else "เลือกเวลาสัมภาษณ์",
        "event_confirmed_heading": "ยืนยันเข้าร่วมปฐมนิเทศแล้ว" if is_orientation else "ยืนยันนัดเรียนแล้ว" if is_class else "ยืนยันนัดสัมภาษณ์แล้ว",
        "line_return_url": settings.LINE_RETURN_URL,
    }, status=409 if slot_error else 200)
