import json
from calendar import Calendar
from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    HomeworkUploadForm,
    PaymentSlipUploadForm,
    PersonForm,
    REGION_OPTIONS,
    TeacherLoginForm,
    TeacherSignupForm,
)
from .line import (
    LineProfileError,
    build_appointment_invitation_flex_message,
    normalize_line_profile,
    send_line_push_message,
    verify_line_id_token,
)
from .models import (
    Appointment,
    AppointmentParticipant,
    AttendanceRecord,
    AttendanceSession,
    HomeworkAssignment,
    HomeworkSubmission,
    Person,
    Student,
    TeacherGroup,
)


REGISTRATION_STEPS = (
    {
        "number": 1,
        "label": "ข้อมูลส่วนตัว",
        "label_en": "Personal",
        "i18n_key": "step_personal",
        "icon": "user",
    },
    {
        "number": 2,
        "label": "ที่อยู่",
        "label_en": "Address",
        "i18n_key": "step_address",
        "icon": "map-pin",
    },
    {
        "number": 3,
        "label": "คริสตจักร",
        "label_en": "Church",
        "i18n_key": "step_church",
        "icon": "landmark",
    },
    {
        "number": 4,
        "label": "เป้าหมาย",
        "label_en": "Calling",
        "i18n_key": "step_calling",
        "icon": "target",
    },
)


def is_school_admin(user):
    return user.is_authenticated and user.is_active and user.is_superuser


def is_teacher(user):
    return (
        user.is_authenticated
        and user.is_active
        and getattr(user, "role", "") == user.Role.TEACHER
    )


def can_view_teacher_dashboard(user):
    return is_school_admin(user) or (
        is_teacher(user) and user.can_access_teacher_dashboard()
    )


def get_auth_context():
    return {
        "google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED,
        "google_oauth_login_url": "google_login",
    }


class TeacherLoginView(LoginView):
    form_class = TeacherLoginForm
    template_name = "school/login.html"
    redirect_authenticated_user = False

    def get_success_url(self):
        return resolve_url("school:post_login_redirect")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if can_view_teacher_dashboard(request.user):
                return redirect("school:teacher_dashboard")
            if not is_teacher(request.user):
                return redirect("school:registration")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_auth_context())
        user = self.request.user
        status = self.request.GET.get("teacher_status")
        context["teacher_pending_notice"] = (
            status in {"pending", "registered_pending"}
            or (is_teacher(user) and not user.can_access_teacher_dashboard())
        )
        context["teacher_registered_pending_notice"] = status == "registered_pending"
        return context


def get_session_line_profile(request):
    return request.session.get("line_profile", {})


def get_line_initial(request):
    session_profile = get_session_line_profile(request)
    return {
        "line_user_id": request.GET.get("line_user_id") or session_profile.get("line_user_id", ""),
        "line_display_name": request.GET.get("line_display_name") or session_profile.get("line_display_name", ""),
        "line_picture_url": request.GET.get("line_picture_url") or session_profile.get("line_picture_url", ""),
    }


def get_liff_context(request, reload_on_sync=False):
    return {
        "line_liff_id": settings.LINE_LIFF_ID if settings.LINE_LIFF_ENABLED else "",
        "line_profile": get_session_line_profile(request),
        "liff_reload_on_sync": reload_on_sync,
    }


def redirect_to_liff_path(path):
    if not settings.LINE_LIFF_ENABLED or not settings.LINE_LIFF_ID:
        return redirect(path)
    return redirect(f"https://liff.line.me/{settings.LINE_LIFF_ID}{path}")


@require_GET
def liff_results_launch(request):
    return redirect_to_liff_path("/results/")


@require_GET
def liff_payment_launch(request):
    return redirect_to_liff_path("/students/payment/")


def store_line_profile(request, profile, verified=False):
    line_profile = {
        **profile,
        "verified": verified,
    }
    request.session["line_profile"] = line_profile
    return line_profile


def get_existing_person_for_line(request):
    line_user_id = get_session_line_profile(request).get("line_user_id", "")
    if not line_user_id:
        return None

    return (
        Person.objects.select_related("student", "student__group")
        .filter(line_user_id=line_user_id)
        .first()
    )


def get_payment_access_state(line_user_id):
    if not line_user_id:
        return "missing_line", None, None

    person = (
        Person.objects.select_related("student", "student__group")
        .filter(line_user_id=line_user_id)
        .first()
    )
    if not person:
        return "missing", None, None

    student = getattr(person, "student", None)
    if person.status != Person.Status.PASSED or not student:
        return "not_student", person, student
    if student.is_paid:
        return "paid", person, student
    return "ready", person, student


def get_student_for_line(line_user_id):
    if not line_user_id:
        return None, None
    person = (
        Person.objects.select_related("student", "student__group")
        .filter(line_user_id=line_user_id, status=Person.Status.PASSED)
        .first()
    )
    student = getattr(person, "student", None) if person else None
    if not student or not student.is_active:
        return person, None
    return person, student


def calculate_student_learning(student):
    if not student or not student.group_id:
        return {
            "attendance_total": 0,
            "attendance_attended": 0,
            "attendance_percent": None,
            "homework_total": 0,
            "homework_submitted": 0,
            "homework_percent": None,
        }

    attendance_total = AttendanceSession.objects.filter(group=student.group).count()
    attendance_attended = AttendanceRecord.objects.filter(
        student=student,
        attendance_session__group=student.group,
        status__in=(AttendanceRecord.Status.PRESENT, AttendanceRecord.Status.LATE),
    ).count()
    homework_total = HomeworkAssignment.objects.filter(group=student.group).count()
    homework_submitted = HomeworkSubmission.objects.filter(
        student=student,
        homework_assignment__group=student.group,
        status__in=(HomeworkSubmission.Status.SUBMITTED, HomeworkSubmission.Status.LATE),
    ).count()

    return {
        "attendance_total": attendance_total,
        "attendance_attended": attendance_attended,
        "attendance_percent": round(attendance_attended * 100 / attendance_total)
        if attendance_total
        else None,
        "homework_total": homework_total,
        "homework_submitted": homework_submitted,
        "homework_percent": round(homework_submitted * 100 / homework_total)
        if homework_total
        else None,
    }


@require_POST
def liff_profile_sync(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "message": "Invalid JSON payload"}, status=400)

    id_token = payload.get("id_token", "")
    verified = False

    try:
        if settings.LINE_LOGIN_CHANNEL_ID:
            profile = verify_line_id_token(id_token)
            verified = True
        elif settings.LINE_LIFF_ALLOW_UNVERIFIED_PROFILE:
            profile = normalize_line_profile(payload.get("profile", {}))
        else:
            raise LineProfileError("LINE token verification is not configured")
    except LineProfileError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=400)

    if not profile["line_user_id"]:
        return JsonResponse({"ok": False, "message": "Missing LINE user id"}, status=400)

    person = Person.objects.filter(line_user_id=profile["line_user_id"]).first()
    if person:
        changed_fields = []
        if profile["line_display_name"] and person.line_display_name != profile["line_display_name"]:
            person.line_display_name = profile["line_display_name"]
            changed_fields.append("line_display_name")
        if profile["line_picture_url"] and person.line_picture_url != profile["line_picture_url"]:
            person.line_picture_url = profile["line_picture_url"]
            changed_fields.append("line_picture_url")
        if changed_fields:
            person.line_connected_at = timezone.now()
            changed_fields.append("line_connected_at")
            person.save(update_fields=changed_fields)

    line_profile = store_line_profile(request, profile, verified=verified)
    return JsonResponse(
        {
            "ok": True,
            "profile": line_profile,
            "has_person": bool(person),
        }
    )


@never_cache
@require_GET
def agent_notifications(request, user_key):
    return JsonResponse(
        {
            "ok": True,
            "user_key": user_key,
            "ca_number": request.GET.get("ca_number", "").strip(),
            "notifications": [],
        }
    )


@never_cache
@require_GET
def latest_closed_loop_notification(request, user_key):
    return JsonResponse(
        {
            "ok": True,
            "user_key": user_key,
            "ca_number": request.GET.get("ca_number", "").strip(),
            "latest_closed_loop": None,
            "notifications": [],
        }
    )


@never_cache
@ensure_csrf_cookie
def registration(request):
    if (
        request.method == "GET"
        and request.GET.get("liff.state")
        and settings.LINE_LIFF_ENABLED
        and settings.LINE_LIFF_ID
    ):
        context = {
            "liff_state": request.GET["liff.state"],
        }
        context.update(get_liff_context(request))
        return render(request, "school/liff_boot.html", context)

    existing_person = get_existing_person_for_line(request)
    if request.method == "GET" and existing_person:
        context = {
            "person": existing_person,
            "student": getattr(existing_person, "student", None),
            "line_return_url": settings.LINE_RETURN_URL,
        }
        context.update(get_liff_context(request))
        return render(request, "school/already_registered.html", context)

    line_initial = get_line_initial(request)
    form = PersonForm(
        request.POST or None,
        request.FILES or None,
        initial=line_initial if request.method == "GET" else None,
    )

    if request.method == "POST" and form.is_valid():
        person = form.save(line_profile=get_session_line_profile(request))
        if person.line_user_id:
            store_line_profile(
                request,
                {
                    "line_user_id": person.line_user_id,
                    "line_display_name": person.line_display_name,
                    "line_picture_url": person.line_picture_url,
                },
                verified=bool(get_session_line_profile(request).get("verified")),
            )
        request.session["person_receipt"] = {
            "person_id": person.pk,
            "applicant_name": person.full_name,
            "status": person.get_status_display(),
            "line_user_id": person.line_user_id,
        }
        return redirect("school:registration_success")

    context = {
        "form": form,
        "region_options": REGION_OPTIONS,
        "registration_steps": REGISTRATION_STEPS,
    }
    context.update(get_liff_context(request, reload_on_sync=True))
    return render(request, "school/registration.html", context)


@never_cache
@ensure_csrf_cookie
def registration_success(request):
    receipt = request.session.get("person_receipt")
    if not receipt:
        return redirect("school:registration")

    person = (
        Person.objects.select_related("student", "student__group")
        .filter(pk=receipt["person_id"])
        .first()
    )
    student = getattr(person, "student", None) if person else None
    context = {
        "receipt": receipt,
        "person": person,
        "student": student,
        "line_return_url": settings.LINE_RETURN_URL,
        "next_steps": (
            "รอตรวจสอบข้อมูลของคุณ",
            "รอนัดหมายสัมภาษณ์ สถานที่ คริสตจักรไบร์ทโรแมนซ์",
            "ประกาศผลผู้ที่ผ่านสัมภาษณ์",
            "ยืนยันการเข้าเรียน ด้วยการชำระค่าเทอม",
            "รับรหัสนักเรียนรอปฐมนิเทศน์",
        ),
    }
    context.update(get_liff_context(request))
    return render(request, "school/registration_success.html", context)


@never_cache
@ensure_csrf_cookie
def announcement_result(request):
    line_user_id = (
        request.GET.get("line_user_id", "")
        or get_session_line_profile(request).get("line_user_id", "")
        or request.session.get("person_receipt", {}).get("line_user_id", "")
    ).strip()
    person = None
    student = None
    result_state = "missing"

    if line_user_id:
        person = (
            Person.objects.select_related("student", "student__group")
            .filter(line_user_id=line_user_id)
            .first()
        )

    if person:
        student = getattr(person, "student", None)
        if person.status == Person.Status.PASSED or student:
            result_state = "paid" if student and student.is_paid else "passed"
        elif person.status == Person.Status.FAILED:
            result_state = "failed"
        else:
            result_state = "pending"

    context = {
        "line_user_id": line_user_id,
        "line_return_url": settings.LINE_RETURN_URL,
        "person": person,
        "student": student,
        "result_state": result_state,
    }
    context.update(get_liff_context(request, reload_on_sync=not bool(line_user_id)))
    return render(request, "school/announcement_result.html", context)


def teacher_register(request):
    form = TeacherSignupForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(f"{resolve_url('school:login')}?teacher_status=registered_pending")

    return render(
        request,
        "school/teacher_register.html",
        {"form": form, **get_auth_context()},
    )


@login_required
def post_login_redirect(request):
    if can_view_teacher_dashboard(request.user):
        return redirect("school:teacher_dashboard")
    if is_teacher(request.user):
        return redirect(f"{resolve_url('school:login')}?teacher_status=pending")
    return redirect("school:registration")


@login_required
def teacher_pending_approval(request):
    if not is_teacher(request.user):
        if is_school_admin(request.user):
            return redirect("school:admin_overview_dashboard")
        raise PermissionDenied

    if request.user.can_access_teacher_dashboard():
        return redirect("school:teacher_dashboard")

    return redirect(f"{resolve_url('school:login')}?teacher_status=pending")


@login_required
def teacher_dashboard(request):
    if not can_view_teacher_dashboard(request.user):
        if not is_teacher(request.user):
            raise PermissionDenied
        return redirect(f"{resolve_url('school:login')}?teacher_status=pending")

    groups = list(
        TeacherGroup.objects.filter(teacher=request.user, is_active=True)
        .annotate(
            active_student_count=Count(
                "students",
                filter=Q(students__is_active=True),
                distinct=True,
            ),
            paid_student_count=Count(
                "students",
                filter=Q(students__is_active=True, students__is_paid=True),
                distinct=True,
            ),
            attendance_session_count=Count("attendance_sessions", distinct=True),
            homework_assignment_count=Count("homework_assignments", distinct=True),
        )
        .order_by("group_name")
    )

    selected_group = None
    selected_group_id = request.GET.get("group", "").strip()
    if selected_group_id.isdigit():
        selected_group = next(
            (group for group in groups if group.pk == int(selected_group_id)),
            None,
        )

    scope_groups = [selected_group] if selected_group else groups
    students = list(
        Student.objects.select_related("person", "group")
        .filter(group__in=scope_groups, is_active=True)
        .annotate(
            attendance_total=Count("group__attendance_sessions", distinct=True),
            attendance_attended=Count(
                "attendance_records",
                filter=Q(
                    attendance_records__attendance_session__group__in=scope_groups,
                    attendance_records__status__in=(
                        AttendanceRecord.Status.PRESENT,
                        AttendanceRecord.Status.LATE,
                    ),
                ),
                distinct=True,
            ),
            homework_total=Count("group__homework_assignments", distinct=True),
            homework_submitted=Count(
                "homework_submissions",
                filter=Q(
                    homework_submissions__homework_assignment__group__in=scope_groups,
                    homework_submissions__status__in=(
                        HomeworkSubmission.Status.SUBMITTED,
                        HomeworkSubmission.Status.LATE,
                    ),
                ),
                distinct=True,
            ),
        )
        .order_by("group__group_name", "student_id")
    )

    attendance_percentages = []
    homework_percentages = []
    needs_attention_count = 0
    for student in students:
        student.attendance_percent = None
        student.homework_percent = None
        student.needs_attention = False
        student.attention_reasons = []

        if student.attendance_total:
            student.attendance_percent = round(
                student.attendance_attended * 100 / student.attendance_total
            )
            attendance_percentages.append(student.attendance_percent)
            if student.attendance_percent < 75:
                student.needs_attention = True
                student.attention_reasons.append("การเข้าเรียน")

        if student.homework_total:
            student.homework_percent = round(
                student.homework_submitted * 100 / student.homework_total
            )
            homework_percentages.append(student.homework_percent)
            if student.homework_percent < 70:
                student.needs_attention = True
                student.attention_reasons.append("การส่งงาน")

        if student.needs_attention:
            needs_attention_count += 1

    student_count = len(students)
    paid_count = sum(student.is_paid for student in students)
    validation_pending_count = sum(
        student.admin_validation_status == Student.AdminValidationStatus.PENDING
        for student in students
    )
    average_attendance = (
        round(sum(attendance_percentages) / len(attendance_percentages))
        if attendance_percentages
        else None
    )
    average_homework = (
        round(sum(homework_percentages) / len(homework_percentages))
        if homework_percentages
        else None
    )

    dashboard_groups = []
    for group in scope_groups:
        group_students = [student for student in students if student.group_id == group.pk]
        group_attendance = [
            student.attendance_percent
            for student in group_students
            if student.attendance_percent is not None
        ]
        group_homework = [
            student.homework_percent
            for student in group_students
            if student.homework_percent is not None
        ]
        group.dashboard_attendance = (
            round(sum(group_attendance) / len(group_attendance))
            if group_attendance
            else None
        )
        group.dashboard_homework = (
            round(sum(group_homework) / len(group_homework))
            if group_homework
            else None
        )
        group.dashboard_attention_count = sum(
            student.needs_attention for student in group_students
        )
        dashboard_groups.append(group)

    attention_students = [student for student in students if student.needs_attention][:5]

    upcoming_assignments = (
        HomeworkAssignment.objects.select_related("group")
        .filter(group__in=scope_groups, due_date__gte=timezone.localdate())
        .annotate(
            submitted_count=Count(
                "homework_submissions",
                filter=Q(
                    homework_submissions__status__in=(
                        HomeworkSubmission.Status.SUBMITTED,
                        HomeworkSubmission.Status.LATE,
                    )
                ),
                distinct=True,
            ),
            target_student_count=Count(
                "group__students",
                filter=Q(group__students__is_active=True),
                distinct=True,
            ),
        )
        .order_by("due_date", "title")[:5]
    )
    recent_attendance_sessions = (
        AttendanceSession.objects.select_related("group")
        .filter(group__in=scope_groups)
        .annotate(
            present_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.Status.PRESENT),
            ),
            late_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.Status.LATE),
            ),
            absent_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.Status.ABSENT),
            ),
        )
        .order_by("-date", "group__group_name")[:5]
    )
    context = {
        "groups": groups,
        "students": students,
        "selected_group": selected_group,
        "student_count": student_count,
        "paid_count": paid_count,
        "unpaid_count": student_count - paid_count,
        "validation_pending_count": validation_pending_count,
        "average_attendance": average_attendance,
        "average_homework": average_homework,
        "has_learning_data": bool(attendance_percentages or homework_percentages),
        "needs_attention_count": needs_attention_count,
        "attention_students": attention_students,
        "dashboard_groups": dashboard_groups,
        "upcoming_assignments": upcoming_assignments,
        "recent_attendance_sessions": recent_attendance_sessions,
    }
    return render(request, "school/teacher_dashboard.html", context)


def teacher_accessible_groups(user):
    group_queryset = TeacherGroup.objects.filter(is_active=True)
    if is_school_admin(user):
        return group_queryset.select_related("teacher").order_by("group_name")
    return group_queryset.filter(teacher=user).order_by("group_name")


def parse_teacher_calendar_month(value):
    parsed = parse_date(f"{value}-01") if value else None
    if parsed:
        return parsed.replace(day=1)
    today = timezone.localdate()
    return today.replace(day=1)


@login_required
@never_cache
def teacher_calendar(request):
    if not can_view_teacher_dashboard(request.user):
        if not is_teacher(request.user):
            raise PermissionDenied
        return redirect(f"{resolve_url('school:login')}?teacher_status=pending")

    groups = list(
        teacher_accessible_groups(request.user).annotate(
            active_student_count=Count(
                "students",
                filter=Q(students__is_active=True),
                distinct=True,
            )
        )
    )
    selected_group = None
    selected_group_id = (
        request.POST.get("group")
        if request.method == "POST"
        else request.GET.get("group", "")
    )
    if str(selected_group_id).isdigit():
        selected_group = next(
            (group for group in groups if group.pk == int(selected_group_id)),
            None,
        )
    scope_groups = [selected_group] if selected_group else groups
    student_queryset = (
        Student.objects.select_related("person", "group")
        .filter(group__in=scope_groups, is_active=True)
        .order_by("group__group_name", "student_id")
    )

    if request.method == "POST":
        title = request.POST.get("title", "").strip() or "นัดเรียน"
        location = request.POST.get("location", "").strip()
        meeting_url = request.POST.get("meeting_url", "").strip()
        details = request.POST.get("details", "").strip()
        date_value = request.POST.get("date", "").strip()
        time_value = request.POST.get("time", "").strip()
        selected_student_ids = request.POST.getlist("students")
        form_has_error = False

        selected_students = student_queryset.filter(pk__in=selected_student_ids)
        if not selected_student_ids:
            messages.error(request, "กรุณาเลือกนักเรียนอย่างน้อย 1 คน")
            form_has_error = True
        elif selected_students.count() != len(set(selected_student_ids)):
            messages.error(request, "มีนักเรียนบางคนอยู่นอกกลุ่มที่คุณดูแล กรุณาเลือกใหม่")
            form_has_error = True
        elif selected_students.count() > 50:
            messages.error(request, "เลือกนักเรียนได้ครั้งละไม่เกิน 50 คน")
            form_has_error = True

        try:
            starts_at = timezone.make_aware(
                datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M"),
                timezone.get_current_timezone(),
            )
        except ValueError:
            messages.error(request, "กรุณาระบุวันและเวลาให้ถูกต้อง")
            starts_at = None
            form_has_error = True

        if starts_at and starts_at <= timezone.now():
            messages.error(request, "กรุณาเลือกวันเวลาในอนาคต")
            form_has_error = True

        if not form_has_error:
            with transaction.atomic():
                locked_students = list(
                    student_queryset.select_for_update()
                    .filter(pk__in=selected_student_ids)
                    .order_by("pk")
                )
                appointment = Appointment.objects.create(
                    appointment_type=Appointment.Type.CLASS,
                    title=title,
                    starts_at=starts_at,
                    location=location,
                    meeting_url=meeting_url,
                    details=details,
                    created_by=request.user,
                )
                participants = AppointmentParticipant.objects.bulk_create(
                    [
                        AppointmentParticipant(
                            appointment=appointment,
                            person=student.person,
                        )
                        for student in locked_students
                    ]
                )
            request.session["teacher_appointment_send_queue"] = [
                {"id": participant.pk, "at": appointment.starts_at.isoformat()}
                for participant in participants
            ]
            messages.success(
                request,
                f"สร้างนัดเรียนและเตรียมส่ง LINE ให้ {len(participants)} คนแล้ว",
            )
            query = f"?group={selected_group.pk}" if selected_group else ""
            return redirect(f"{reverse('school:teacher_calendar')}{query}")

    month_start = parse_teacher_calendar_month(request.GET.get("month", ""))
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    previous_month = (month_start - timedelta(days=1)).replace(day=1)
    calendar_weeks = Calendar(firstweekday=6).monthdatescalendar(
        month_start.year,
        month_start.month,
    )
    range_start = calendar_weeks[0][0]
    range_end = calendar_weeks[-1][-1]
    appointment_queryset = (
        Appointment.objects.filter(
            appointment_type=Appointment.Type.CLASS,
            participants__person__student__group__in=scope_groups,
            starts_at__date__gte=range_start,
            starts_at__date__lte=range_end,
        )
        .annotate(
            participant_count=Count("participants", distinct=True),
            confirmed_count=Count(
                "participants",
                filter=Q(participants__response_status=AppointmentParticipant.ResponseStatus.CONFIRMED),
                distinct=True,
            ),
        )
        .order_by("starts_at", "title")
        .distinct()
    )
    events_by_date = {}
    for appointment in appointment_queryset:
        local_start = timezone.localtime(appointment.starts_at)
        events_by_date.setdefault(local_start.date(), []).append(appointment)

    today = timezone.localdate()
    calendar_rows = [
        [
            {
                "date": day,
                "is_today": day == today,
                "is_current_month": day.month == month_start.month,
                "events": events_by_date.get(day, []),
            }
            for day in week
        ]
        for week in calendar_weeks
    ]
    upcoming_appointments = (
        Appointment.objects.filter(
            appointment_type=Appointment.Type.CLASS,
            participants__person__student__group__in=scope_groups,
            starts_at__gte=timezone.now(),
        )
        .annotate(
            participant_count=Count("participants", distinct=True),
            confirmed_count=Count(
                "participants",
                filter=Q(participants__response_status=AppointmentParticipant.ResponseStatus.CONFIRMED),
                distinct=True,
            ),
        )
        .order_by("starts_at", "title")
        .distinct()[:8]
    )

    return render(
        request,
        "school/teacher_calendar.html",
        {
            "active_teacher_page": "calendar",
            "groups": groups,
            "selected_group": selected_group,
            "scope_groups": scope_groups,
            "students": student_queryset,
            "student_count": student_queryset.count(),
            "calendar_rows": calendar_rows,
            "month_start": month_start,
            "previous_month": previous_month,
            "next_month": next_month,
            "upcoming_appointments": upcoming_appointments,
            "send_queue": request.session.pop("teacher_appointment_send_queue", []),
        },
    )


def participant_in_teacher_scope(user, participant):
    if is_school_admin(user):
        return True
    student = getattr(participant.person, "student", None)
    return bool(student and student.group and student.group.teacher_id == user.pk)


@login_required
@require_POST
def teacher_calendar_notify(request, pk):
    if not can_view_teacher_dashboard(request.user):
        raise PermissionDenied
    with transaction.atomic():
        participant = (
            AppointmentParticipant.objects.select_for_update()
            .select_related("appointment", "person", "person__student", "person__student__group")
            .filter(pk=pk, appointment__appointment_type=Appointment.Type.CLASS)
            .first()
        )
        if participant is None or not participant_in_teacher_scope(request.user, participant):
            return JsonResponse({"error": "ไม่พบนัดเรียนนี้"}, status=404)
        try:
            expected = datetime.fromisoformat(request.POST.get("at", ""))
        except ValueError:
            expected = None
        appointment = participant.appointment
        if (
            appointment.status != Appointment.Status.SCHEDULED
            or appointment.starts_at <= timezone.now()
            or expected != appointment.starts_at
        ):
            return JsonResponse(
                {"error": "นัดนี้มีการเปลี่ยนแปลงหรือไม่สามารถส่งได้แล้ว"},
                status=409,
            )
        if participant.notification_status == AppointmentParticipant.NotificationStatus.SENT:
            return JsonResponse({"sent": True, "label": "LINE รับข้อความแล้ว"})
        sent = send_line_push_message(
            participant.person.line_user_id,
            [build_appointment_invitation_flex_message(participant)],
        )
        participant.notification_status = (
            AppointmentParticipant.NotificationStatus.SENT
            if sent
            else AppointmentParticipant.NotificationStatus.FAILED
        )
        participant.notified_at = timezone.now() if sent else None
        participant.notification_error = (
            ""
            if sent
            else "LINE ไม่รับข้อความ โปรดตรวจ token / friend status แล้วลองใหม่"
        )
        participant.save(
            update_fields=[
                "notification_status",
                "notified_at",
                "notification_error",
                "updated_at",
            ]
        )
        return JsonResponse(
            {
                "sent": sent,
                "label": "LINE รับข้อความแล้ว" if sent else "ส่งไม่สำเร็จ ตรวจสอบ LINE แล้วลองใหม่",
            }
        )


@login_required(login_url="admin:login")
def admin_overview_dashboard(request):
    if not is_school_admin(request.user):
        raise PermissionDenied

    User = get_user_model()
    teacher_queryset = User.objects.filter(role=User.Role.TEACHER)
    recent_students = (
        Student.objects.select_related("person", "group")
        .order_by("-created_at", "-id")[:8]
    )
    teacher_summaries = teacher_queryset.prefetch_related("teacher_groups").order_by(
        "first_name", "last_name", "username"
    )[:8]
    group_summaries = (
        TeacherGroup.objects.select_related("teacher")
        .annotate(
            student_count=Count("students"),
            paid_student_count=Count(
                "students",
                filter=Q(students__is_paid=True),
            ),
        )
        .order_by("group_name")[:8]
    )

    region_counts = Counter()
    province_counts = Counter()
    country_counts = Counter()
    thai_count = 0
    international_count = 0
    unspecified_count = 0

    for extra_data in Person.objects.values_list("extra_data", flat=True):
        extra_data = extra_data or {}
        thai_address = extra_data.get("address_th") or {}
        region = extra_data.get("region") or thai_address.get("region") or ""
        province = extra_data.get("province") or thai_address.get("province") or ""
        country_code = str(extra_data.get("country_code") or "").strip().upper()

        if not country_code and (region or province):
            country_code = "TH"

        if country_code == "TH":
            thai_count += 1
            country_counts["ประเทศไทย"] += 1
            region_counts[region or "unspecified"] += 1
            if province:
                province_counts[province] += 1
        elif country_code:
            international_count += 1
            country_name = (
                extra_data.get("country_name_th")
                or extra_data.get("country_name_en")
                or country_code
            )
            country_counts[str(country_name).strip()] += 1
        else:
            unspecified_count += 1
            country_counts["ไม่ระบุประเทศ"] += 1

    region_summaries = [
        {
            "label": item["label"],
            "value": item["value"],
            "count": region_counts[item["value"]],
        }
        for item in REGION_OPTIONS
    ]
    if region_counts["unspecified"]:
        region_summaries.append(
            {
                "label": "ไม่ระบุภูมิภาค",
                "value": "unspecified",
                "count": region_counts["unspecified"],
            }
        )

    context = {
        "stats": {
            "applicants_total": Person.objects.count(),
            "applicants_pending": Person.objects.filter(status=Person.Status.IN_PROGRESS).count(),
            "applicants_passed": Person.objects.filter(status=Person.Status.PASSED).count(),
            "students_total": Student.objects.count(),
            "students_paid": Student.objects.filter(is_paid=True).count(),
            "students_unpaid": Student.objects.filter(is_paid=False).count(),
            "teachers_total": teacher_queryset.count(),
            "groups_total": TeacherGroup.objects.count(),
        },
        "recent_students": recent_students,
        "teacher_summaries": teacher_summaries,
        "group_summaries": group_summaries,
        "geo_stats": {
            "thai": thai_count,
            "international": international_count,
            "unspecified": unspecified_count,
        },
        "region_summaries": region_summaries,
        "province_summaries": [
            {"label": label, "count": count}
            for label, count in province_counts.most_common(10)
        ],
        "country_summaries": [
            {"label": label, "count": count}
            for label, count in country_counts.most_common(10)
        ],
    }
    return render(request, "school/admin_overview_dashboard.html", context)


@require_GET
def liff_student_dashboard_launch(request):
    return redirect_to_liff_path("/students/dashboard/")


@never_cache
@ensure_csrf_cookie
def student_dashboard(request):
    line_profile = get_session_line_profile(request)
    line_user_id = line_profile.get("line_user_id", "").strip()
    person, student = get_student_for_line(line_user_id)
    student_state = (
        "missing_line"
        if not line_user_id
        else "ready"
        if student
        else "not_ready"
        if person
        else "missing"
    )
    learning = calculate_student_learning(student)
    assignment_rows = []
    recent_attendance = []
    appointment_rows = []

    if student and student.group_id:
        submissions = {
            submission.homework_assignment_id: submission
            for submission in HomeworkSubmission.objects.filter(
                student=student,
                homework_assignment__group=student.group,
            ).select_related("homework_assignment")
        }
        assignments = (
            HomeworkAssignment.objects.filter(group=student.group)
            .order_by("due_date", "title")[:8]
        )
        for assignment in assignments:
            submission = submissions.get(assignment.pk)
            assignment_rows.append(
                {
                    "assignment": assignment,
                    "submission": submission,
                    "is_done": bool(
                        submission
                        and submission.status
                        in (HomeworkSubmission.Status.SUBMITTED, HomeworkSubmission.Status.LATE)
                    ),
                    "is_late": assignment.due_date < timezone.localdate()
                    and not submission,
                }
            )

        attendance_records = (
            AttendanceRecord.objects.select_related("attendance_session")
            .filter(student=student, attendance_session__group=student.group)
            .order_by("-attendance_session__date")[:6]
        )
        recent_attendance = attendance_records
        appointment_rows = (
            AppointmentParticipant.objects.select_related("appointment")
            .filter(
                person=student.person,
                appointment__appointment_type=Appointment.Type.CLASS,
                appointment__status=Appointment.Status.SCHEDULED,
                appointment__starts_at__gte=timezone.now(),
            )
            .order_by("appointment__starts_at")[:5]
        )

    return render(
        request,
        "school/student_dashboard.html",
        {
            "student_state": student_state,
            "person": person,
            "student": student,
            "learning": learning,
            "assignment_rows": assignment_rows,
            "recent_attendance": recent_attendance,
            "appointment_rows": appointment_rows,
            "line_return_url": settings.LINE_RETURN_URL,
            **get_liff_context(request, reload_on_sync=not bool(line_user_id)),
        },
    )


@never_cache
@ensure_csrf_cookie
def student_homework_upload(request):
    line_profile = get_session_line_profile(request)
    line_user_id = line_profile.get("line_user_id", "").strip()
    person, student = get_student_for_line(line_user_id)
    student_state = (
        "missing_line"
        if not line_user_id
        else "ready"
        if student
        else "not_ready"
        if person
        else "missing"
    )
    active_assignment = None
    form = HomeworkUploadForm()

    if student and request.method == "POST":
        assignment_id = request.POST.get("assignment_id", "")
        if assignment_id.isdigit():
            active_assignment = get_object_or_404(
                HomeworkAssignment,
                pk=assignment_id,
                group=student.group,
            )
            form = HomeworkUploadForm(request.POST, request.FILES)
            if form.is_valid():
                form.save(student, active_assignment)
                messages.success(request, f"ส่งการบ้าน {active_assignment.title} เรียบร้อยแล้ว")
                return redirect("school:student_homework_upload")
        else:
            messages.error(request, "ไม่พบการบ้านที่ต้องการส่ง กรุณาลองใหม่")

    assignment_rows = []
    if student and student.group_id:
        submissions = {
            submission.homework_assignment_id: submission
            for submission in HomeworkSubmission.objects.filter(
                student=student,
                homework_assignment__group=student.group,
            )
        }
        for assignment in HomeworkAssignment.objects.filter(group=student.group).order_by(
            "due_date",
            "title",
        ):
            assignment_rows.append(
                {
                    "assignment": assignment,
                    "submission": submissions.get(assignment.pk),
                    "form": form if active_assignment and active_assignment.pk == assignment.pk else HomeworkUploadForm(),
                    "is_late": assignment.due_date < timezone.localdate()
                    and assignment.pk not in submissions,
                }
            )

    return render(
        request,
        "school/student_homework_upload.html",
        {
            "student_state": student_state,
            "person": person,
            "student": student,
            "assignment_rows": assignment_rows,
            "active_assignment": active_assignment,
            "line_return_url": settings.LINE_RETURN_URL,
            **get_liff_context(request, reload_on_sync=not bool(line_user_id)),
        },
    )


@never_cache
def student_payment_upload(request):
    line_profile = get_session_line_profile(request)
    line_user_id = line_profile.get("line_user_id", "").strip()
    payment_state, person, student = get_payment_access_state(line_user_id)
    should_bind_form = request.method == "POST" and payment_state == "ready"
    form = PaymentSlipUploadForm(
        request.POST if should_bind_form else None,
        request.FILES if should_bind_form else None,
        initial={"line_user_id": line_user_id} if request.method == "GET" else None,
        line_profile=line_profile,
    )
    uploaded_student = None

    if should_bind_form and form.is_valid():
        uploaded_student = form.save()
        messages.success(
            request,
            "อัปโหลดสลิปเรียบร้อยแล้ว ทีมงานจะตรวจสอบการชำระเงิน",
        )
        return redirect("school:student_payment_upload")

    return render(
        request,
        "school/student_payment_upload.html",
        {
            "form": form,
            "uploaded_student": uploaded_student,
            "payment_state": payment_state,
            "person": person,
            "student": student,
            "line_return_url": settings.LINE_RETURN_URL,
            **get_liff_context(request, reload_on_sync=not bool(line_user_id)),
        },
    )
