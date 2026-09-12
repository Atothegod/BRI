from datetime import datetime
from zoneinfo import ZoneInfo

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .line import build_interview_invitation_flex_message, send_line_push_message
from .models import Person
from .views import is_school_admin


class InterviewScheduleForm(forms.Form):
    people = forms.ModelMultipleChoiceField(queryset=Person.objects.none(), label="ผู้สมัคร", error_messages={
        "required": "กรุณาเลือกผู้สมัครอย่างน้อย 1 คน",
        "invalid_choice": "ผู้สมัครบางคนไม่อยู่ระหว่างดำเนินการแล้ว กรุณาเลือกใหม่",
    })
    date = forms.DateField(label="วันสัมภาษณ์ (ค.ศ.)", widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(label="เวลา (ประเทศไทย)", widget=forms.TimeInput(attrs={"type": "time"}))
    details = forms.CharField(label="สถานที่ / ลิงก์ / รายละเอียด", required=False, max_length=1000,
                              widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["people"].queryset = Person.objects.filter(status=Person.Status.IN_PROGRESS)

    def clean(self):
        data = super().clean()
        if data.get("people") is not None and len(data["people"]) > 50:
            self.add_error("people", "เลือกได้ครั้งละไม่เกิน 50 คน")
        if data.get("date") and data.get("time"):
            data["interview_at"] = timezone.make_aware(datetime.combine(data["date"], data["time"]), ZoneInfo("Asia/Bangkok"))
            if data["interview_at"] <= timezone.now():
                self.add_error("date", "กรุณาเลือกวันเวลาในอนาคต")
        return data


@login_required(login_url="admin:login")
@never_cache
def interview_schedule(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    form = InterviewScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ids = list(form.cleaned_data["people"].values_list("pk", flat=True))
        with transaction.atomic():
            # Recheck eligibility under lock before replacing any appointments.
            people = list(Person.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            if any(person.status != Person.Status.IN_PROGRESS for person in people) or len(people) != len(ids):
                form.add_error("people", "สถานะผู้สมัครเปลี่ยนแล้ว กรุณาเลือกใหม่")
            else:
                Person.objects.filter(pk__in=ids).update(
                    interview_at=form.cleaned_data["interview_at"], interview_details=form.cleaned_data["details"],
                    interview_notification_state="pending", interview_notified_at=None,
                    interview_confirmed_at=None, updated_at=timezone.now(),
                )
        if not form.errors:
            request.session["interview_send_queue"] = [
                {"id": pk, "at": form.cleaned_data["interview_at"].isoformat()} for pk in ids
            ]
            messages.success(request, f"บันทึกนัดสัมภาษณ์ {len(ids)} คนแล้ว")
            return redirect("school:interview_schedule")

    query = request.GET.get("q", "").strip()
    people = Person.objects.filter(status=Person.Status.IN_PROGRESS).order_by("first_name", "pk")
    if query:
        people = people.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(phone__icontains=query) | Q(line_display_name__icontains=query))
    page = Paginator(people, 50).get_page(request.GET.get("page"))
    return render(request, "school/interview_schedule.html", {
        "form": form, "page_obj": page, "query": query,
        "selected_ids": request.POST.getlist("people"),
        "send_queue": request.session.pop("interview_send_queue", []),
    })


@login_required(login_url="admin:login")
@require_POST
def interview_notify(request, pk):
    if not is_school_admin(request.user):
        raise PermissionDenied
    with transaction.atomic():
        person = Person.objects.select_for_update().filter(pk=pk).first()
        if person is None:
            return JsonResponse({"error": "ไม่พบผู้สมัคร"}, status=404)
        if not person.interview_at or person.status != Person.Status.IN_PROGRESS or person.interview_at <= timezone.now():
            return JsonResponse({"error": "นัดนี้ไม่สามารถส่งได้แล้ว"}, status=409)
        try:
            expected = parse_datetime(request.POST.get("at", ""))
        except ValueError:
            expected = None
        if expected != person.interview_at:
            return JsonResponse({"error": "นัดมีการเปลี่ยนแปลง กรุณารีเฟรชหน้า"}, status=409)
        if person.interview_notification_state == "sent":
            return JsonResponse({"sent": True, "label": "LINE รับข้อความแล้ว"})
        sent = send_line_push_message(person.line_user_id, [build_interview_invitation_flex_message(person)])
        Person.objects.filter(pk=person.pk).update(
            interview_notification_state="sent" if sent else "failed",
            interview_notified_at=timezone.now() if sent else None,
        )
        return JsonResponse({"sent": sent, "label": "LINE รับข้อความแล้ว" if sent else "ส่งไม่สำเร็จ ตรวจสอบ LINE / token แล้วลองใหม่"})


@login_required(login_url="admin:login")
@require_POST
def interview_confirmation_status(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    raw_ids = request.POST.getlist("people")
    try:
        ids = list(dict.fromkeys(int(value) for value in raw_ids))[:50]
    except (TypeError, ValueError):
        return JsonResponse({"error": "ข้อมูลผู้สมัครไม่ถูกต้อง"}, status=400)
    people = Person.objects.filter(pk__in=ids).values("pk", "interview_confirmed_at")
    return JsonResponse({
        "people": {
            str(person["pk"]): (
                timezone.localtime(person["interview_confirmed_at"], ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y %H:%M")
                if person["interview_confirmed_at"] else None
            )
            for person in people
        }
    })


@never_cache
@require_http_methods(["GET", "POST"])
def interview_confirmation(request):
    token = request.GET.get("token", "") or request.POST.get("token", "")
    try:
        payload = signing.loads(token, salt="school.interview-confirmation")
        person_id = int(payload["person_id"])
        expected_at = parse_datetime(payload["interview_at"])
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        return render(request, "school/interview_confirmation.html", {"confirmation_state": "invalid"}, status=400)

    with transaction.atomic():
        person = Person.objects.select_for_update().filter(pk=person_id).first()
        valid_appointment = (
            person is not None
            and expected_at is not None
            and person.interview_at == expected_at
            and person.status == Person.Status.IN_PROGRESS
            and person.interview_at > timezone.now()
        )
        if not valid_appointment:
            return render(
                request,
                "school/interview_confirmation.html",
                {"confirmation_state": "stale"},
                status=409,
            )
        if request.method == "POST" and person.interview_confirmed_at is None:
            Person.objects.filter(pk=person.pk).update(interview_confirmed_at=timezone.now())
            person.refresh_from_db(fields=["interview_confirmed_at"])

    return render(request, "school/interview_confirmation.html", {
        "confirmation_state": "confirmed" if person.interview_confirmed_at else "ready",
        "person": person,
        "token": token,
    })
