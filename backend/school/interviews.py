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

from .line import build_appointment_invitation_flex_message, send_line_push_message
from .models import Appointment, AppointmentParticipant, AppointmentSlot, Person
from .views import is_school_admin

THAI_TIMEZONE = ZoneInfo("Asia/Bangkok")
ADMIN_APPOINTMENT_TYPES = (
    Appointment.Type.INTERVIEW,
    Appointment.Type.ORIENTATION,
)


def appointment_candidates(appointment_type):
    queryset = Person.objects.all()
    if appointment_type == Appointment.Type.CLASS:
        return queryset.filter(status=Person.Status.PASSED, student__is_active=True)
    if appointment_type == Appointment.Type.ORIENTATION:
        return queryset.filter(status=Person.Status.PASSED, student__is_paid=True)
    return queryset.filter(status=Person.Status.IN_PROGRESS)


class AppointmentScheduleForm(forms.Form):
    appointment_type = forms.ChoiceField(choices=Appointment.Type.choices, widget=forms.HiddenInput)
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

    def __init__(self, *args, appointment_type=Appointment.Type.INTERVIEW, **kwargs):
        super().__init__(*args, **kwargs)
        if appointment_type not in ADMIN_APPOINTMENT_TYPES:
            appointment_type = Appointment.Type.INTERVIEW
        self.fields["appointment_type"].choices = [
            choice
            for choice in Appointment.Type.choices
            if choice[0] in ADMIN_APPOINTMENT_TYPES
        ]
        self.fields["appointment_type"].initial = appointment_type
        self.fields["people"].queryset = appointment_candidates(appointment_type)
        self.fields["title"].initial = dict(Appointment.Type.choices)[appointment_type]
        self.appointment_type = appointment_type
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


@login_required(login_url="admin:login")
@never_cache
def interview_schedule(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    appointment_type = selected_appointment_type(request)
    form = AppointmentScheduleForm(request.POST or None, appointment_type=appointment_type)
    if request.method == "POST" and form.is_valid():
        ids = list(form.cleaned_data["people"].values_list("pk", flat=True))
        appointment_type = form.cleaned_data["appointment_type"]
        with transaction.atomic():
            people = list(appointment_candidates(appointment_type).select_for_update().filter(pk__in=ids).order_by("pk"))
            if len(people) != len(ids):
                form.add_error("people", "สถานะผู้เข้าร่วมเปลี่ยนแล้ว กรุณาเลือกใหม่")
            else:
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
                    legacy_details = "\n".join(filter(None, [form.cleaned_data["location"], form.cleaned_data["meeting_url"], form.cleaned_data["details"]]))
                    Person.objects.filter(pk__in=ids).update(
                        interview_at=appointment.starts_at, interview_details=legacy_details,
                        interview_notification_state="pending", interview_notified_at=None,
                        interview_confirmed_at=None, updated_at=timezone.now(),
                    )
        if not form.errors:
            request.session["appointment_send_queue"] = [
                {"id": participant.pk, "at": appointment.starts_at.isoformat()} for participant in participants
            ]
            messages.success(request, f"สร้างนัดและเตรียมส่ง LINE ให้ {len(ids)} คนแล้ว")
            return redirect(f"{reverse('school:appointment_schedule')}?type={appointment_type}")

    query = request.GET.get("q", "").strip()
    filters = {key: request.GET.get(key, "") for key in ("appointment", "line", "notification", "confirmation")}
    people = appointment_candidates(appointment_type).order_by("first_name", "pk")
    participations = AppointmentParticipant.objects.filter(appointment__appointment_type=appointment_type)
    if query:
        people = people.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(phone__icontains=query) | Q(line_display_name__icontains=query))
    if filters["appointment"] == "scheduled":
        people = people.filter(appointment_participations__in=participations)
    elif filters["appointment"] == "unscheduled":
        people = people.exclude(appointment_participations__in=participations)
    if filters["line"] == "connected":
        people = people.exclude(line_user_id="")
    elif filters["line"] == "missing":
        people = people.filter(line_user_id="")
    if filters["notification"] in AppointmentParticipant.NotificationStatus.values:
        people = people.filter(appointment_participations__in=participations.filter(notification_status=filters["notification"]))
    if filters["confirmation"] == "confirmed":
        people = people.filter(appointment_participations__in=participations.filter(response_status="confirmed"))
    elif filters["confirmation"] == "waiting":
        people = people.filter(appointment_participations__in=participations.filter(response_status="waiting"))
    people = people.distinct()
    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params["type"] = appointment_type
    filter_query = query_params.urlencode()
    page = Paginator(people, 50).get_page(request.GET.get("page"))
    latest_by_person = {}
    for participant in participations.filter(person_id__in=[person.pk for person in page.object_list]).select_related("appointment", "selected_slot").order_by("person_id", "-appointment__starts_at", "-pk"):
        latest_by_person.setdefault(participant.person_id, participant)
    for person in page.object_list:
        person.latest_appointment_participant = latest_by_person.get(person.pk)
    appointments = list(Appointment.objects.filter(appointment_type=appointment_type).prefetch_related("slots").annotate(
        participant_count=Count("participants", distinct=True),
        confirmed_count=Count("participants", filter=Q(participants__response_status="confirmed"), distinct=True),
    )[:12])
    for appointment in appointments:
        appointment.slot_capacity = sum(slot.capacity for slot in appointment.slots.all())
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
    return JsonResponse({"participants": {str(item["pk"]): {
        "status": item["response_status"],
        "confirmed_at": timezone.localtime(item["confirmed_at"], THAI_TIMEZONE).strftime("%d/%m/%Y %H:%M") if item["confirmed_at"] else None,
    } for item in items}})


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
    return render(request, "school/interview_confirmation.html", {
        "confirmation_state": "confirmed" if participant.response_status == AppointmentParticipant.ResponseStatus.CONFIRMED else "ready",
        "person": participant.person, "appointment": participant.appointment, "token": token,
        "slot_options": slot_options, "slots_are_full": slots_are_full,
        "selected_slot": participant.selected_slot, "slot_error": slot_error,
        "event_eyebrow": "BRI Orientation" if is_orientation else "BRI Class" if is_class else "BRI Interview",
        "event_heading": "ยืนยันเข้าร่วมปฐมนิเทศ" if is_orientation else "ยืนยันนัดเรียน" if is_class else "เลือกเวลาสัมภาษณ์",
        "event_confirmed_heading": "ยืนยันเข้าร่วมปฐมนิเทศแล้ว" if is_orientation else "ยืนยันนัดเรียนแล้ว" if is_class else "ยืนยันนัดสัมภาษณ์แล้ว",
        "line_return_url": settings.LINE_RETURN_URL,
    }, status=409 if slot_error else 200)
