from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .line import line_push_unavailable_reason, send_line_push_message
from .models import Appointment, AppointmentParticipant, AppointmentSlot, Person
from .views import is_school_admin


LINE_MESSAGE_AUDIENCES = {"all", "confirmed", "waiting", "failed", "unsent"}


def _optional_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _filtered_people(request):
    query = request.GET.get("q", "").strip()
    line_status = request.GET.get("line", "connected")
    if line_status not in {"all", "connected", "missing"}:
        line_status = "connected"
    audience = request.GET.get("audience", "all")
    if audience not in LINE_MESSAGE_AUDIENCES:
        audience = "all"
    event_id = _optional_int(request.GET.get("event"))
    slot_id = _optional_int(request.GET.get("slot"))
    appointment = (
        Appointment.objects.filter(pk=event_id).prefetch_related("slots").first()
        if event_id
        else None
    )
    if appointment is None:
        event_id = None
        slot_id = None
        audience = "all"

    people = Person.objects.all().order_by("-created_at", "-pk")
    if query:
        people = people.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(nickname__icontains=query)
            | Q(phone__icontains=query)
            | Q(email__icontains=query)
            | Q(line_display_name__icontains=query)
            | Q(line_user_id__icontains=query)
        )
    if line_status == "connected":
        people = people.exclude(line_user_id="")
    elif line_status == "missing":
        people = people.filter(line_user_id="")

    if appointment:
        participations = AppointmentParticipant.objects.filter(appointment=appointment)
        if audience == "unsent":
            people = people.exclude(pk__in=participations.values("person_id"))
            slot_id = None
        else:
            if audience == "confirmed":
                participations = participations.filter(
                    response_status=AppointmentParticipant.ResponseStatus.CONFIRMED,
                )
            elif audience == "waiting":
                participations = participations.filter(
                    response_status=AppointmentParticipant.ResponseStatus.WAITING,
                )
            elif audience == "failed":
                participations = participations.filter(
                    notification_status=AppointmentParticipant.NotificationStatus.FAILED,
                )
            people = people.filter(pk__in=participations.values("person_id"))
        if slot_id and audience != "unsent":
            slot = AppointmentSlot.objects.filter(pk=slot_id, appointment=appointment).first()
            if slot:
                people = people.filter(
                    appointment_participations__appointment=appointment,
                    appointment_participations__selected_slot=slot,
                )
            else:
                slot_id = None

    return people.distinct(), {
        "query": query,
        "line_status": line_status,
        "audience": audience,
        "appointment": appointment,
        "event_id": event_id,
        "slot_id": slot_id,
    }


@login_required(login_url="admin:login")
@require_GET
def line_message_center(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    people, filters = _filtered_people(request)
    total_count = people.count()
    connected_people = people.exclude(line_user_id="")
    connected_count = connected_people.count()
    all_recipient_ids = list(connected_people.values_list("pk", flat=True))
    page_obj = Paginator(people, 100).get_page(request.GET.get("page"))
    page_person_ids = [person.pk for person in page_obj.object_list]

    participation_by_person = {}
    if page_person_ids:
        participations = AppointmentParticipant.objects.filter(
            person_id__in=page_person_ids,
        ).select_related("appointment", "selected_slot").order_by("person_id", "-pk")
        if filters["appointment"]:
            participations = participations.filter(appointment=filters["appointment"])
        for participation in participations:
            participation_by_person.setdefault(participation.person_id, participation)
    for person in page_obj.object_list:
        person.message_participation = participation_by_person.get(person.pk)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    page_query_prefix = f"?{query_params.urlencode()}&" if query_params else "?"
    appointments = list(
        Appointment.objects.prefetch_related("slots").order_by("-starts_at", "-pk")[:50]
    )
    slot_options_by_event = {
        str(item.pk): [
            {
                "id": slot.pk,
                "label": (
                    f"{timezone.localtime(slot.starts_at):%H:%M}–"
                    f"{timezone.localtime(slot.ends_at):%H:%M}"
                ),
            }
            for slot in item.slots.all()
        ]
        for item in appointments
    }
    slot_options = filters["appointment"].slots.all() if filters["appointment"] else []
    return render(request, "school/line_message_center.html", {
        **filters,
        "appointments": appointments,
        "slot_options": slot_options,
        "slot_options_by_event": slot_options_by_event,
        "page_obj": page_obj,
        "page_query_prefix": page_query_prefix,
        "total_count": total_count,
        "connected_count": connected_count,
        "missing_count": total_count - connected_count,
        "all_recipient_ids": all_recipient_ids,
    })


@login_required(login_url="admin:login")
@require_POST
def person_direct_message(request, pk):
    if not is_school_admin(request.user):
        raise PermissionDenied
    person = Person.objects.filter(pk=pk).first()
    if person is None:
        return JsonResponse({"error": "ไม่พบผู้รับ"}, status=404)
    message = request.POST.get("message", "").strip()
    if not message:
        return JsonResponse({"error": "กรุณากรอกข้อความ"}, status=400)
    if len(message) > 5000:
        return JsonResponse({"error": "ข้อความต้องยาวไม่เกิน 5,000 ตัวอักษร"}, status=400)
    issue = line_push_unavailable_reason(person)
    if issue == "missing_line_user_id":
        return JsonResponse({"error": "ผู้รับยังไม่เชื่อม LINE"}, status=409)
    if issue == "missing_channel_access_token":
        return JsonResponse({"error": "ยังไม่ได้ตั้งค่า LINE token"}, status=503)
    sent = send_line_push_message(
        person.line_user_id,
        [{"type": "text", "text": message}],
    )
    if not sent:
        return JsonResponse({"error": "LINE ไม่รับข้อความ"}, status=502)
    return JsonResponse({"sent": True, "label": "LINE รับข้อความแล้ว"})
