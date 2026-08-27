import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.views.decorators.cache import never_cache
from django.http import JsonResponse
from django.shortcuts import redirect, render, resolve_url
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    PaymentSlipUploadForm,
    PersonForm,
    REGION_OPTIONS,
    TeacherLoginForm,
    TeacherSignupForm,
)
from .line import LineProfileError, normalize_line_profile, verify_line_id_token
from .models import Person, Student, TeacherGroup


REGISTRATION_STEPS = (
    {"number": 1, "label": "ข้อมูลส่วนตัว", "icon": "user"},
    {"number": 2, "label": "ที่อยู่", "icon": "map-pin"},
    {"number": 3, "label": "คริสตจักร", "icon": "landmark"},
    {"number": 4, "label": "เป้าหมาย", "icon": "target"},
)


def is_school_admin(user):
    return (
        user.is_authenticated
        and user.is_active
        and (
            user.is_staff
            or user.is_superuser
            or getattr(user, "role", "") == user.Role.ADMIN
        )
    )


def is_teacher(user):
    return (
        user.is_authenticated
        and user.is_active
        and getattr(user, "role", "") == user.Role.TEACHER
    )


def get_auth_context():
    return {
        "google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED,
        "google_oauth_login_url": "google_login",
    }


class TeacherLoginView(LoginView):
    form_class = TeacherLoginForm
    template_name = "school/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return resolve_url("school:post_login_redirect")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_auth_context())
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
        "line_liff_id": settings.LINE_LIFF_ID,
        "line_profile": get_session_line_profile(request),
        "liff_reload_on_sync": reload_on_sync,
    }


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
    if request.method == "GET" and request.GET.get("liff.state") and settings.LINE_LIFF_ID:
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

    context = {
        "receipt": receipt,
        "line_return_url": settings.LINE_RETURN_URL,
        "next_steps": (
            "ทีมรับสมัครจะตรวจสอบข้อมูลของคุณ",
            "สถานะเริ่มต้นคือดำเนินการ",
            "เมื่อผ่านแล้วทีมงานจะสร้างรหัสนักศึกษาให้ในตารางนักเรียน",
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
            result_state = "passed"
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
        return redirect("school:teacher_pending_approval")

    return render(
        request,
        "school/teacher_register.html",
        {"form": form, **get_auth_context()},
    )


@login_required
def post_login_redirect(request):
    if is_school_admin(request.user):
        return redirect("school:admin_overview_dashboard")
    if is_teacher(request.user):
        if request.user.can_access_teacher_dashboard():
            return redirect("school:teacher_dashboard")
        return redirect("school:teacher_pending_approval")
    return redirect("school:registration")


@login_required
def teacher_pending_approval(request):
    if not is_teacher(request.user):
        if is_school_admin(request.user):
            return redirect("school:admin_overview_dashboard")
        raise PermissionDenied

    if request.user.can_access_teacher_dashboard():
        return redirect("school:teacher_dashboard")

    return render(request, "school/teacher_pending_approval.html")


@login_required
def teacher_dashboard(request):
    if not is_teacher(request.user):
        if is_school_admin(request.user):
            return redirect("school:admin_overview_dashboard")
        raise PermissionDenied

    if not request.user.can_access_teacher_dashboard():
        return redirect("school:teacher_pending_approval")

    groups = (
        TeacherGroup.objects.filter(teacher=request.user, is_active=True)
        .annotate(
            active_student_count=Count("students", filter=Q(students__is_active=True)),
            paid_student_count=Count(
                "students",
                filter=Q(students__is_active=True, students__is_paid=True),
            ),
        )
        .order_by("group_name")
    )
    students = (
        Student.objects.select_related("person", "group")
        .filter(group__in=groups, is_active=True)
        .order_by("group__group_name", "student_id")
    )
    student_count = students.count()
    paid_count = students.filter(is_paid=True).count()
    validation_pending_count = students.filter(
        admin_validation_status=Student.AdminValidationStatus.PENDING
    ).count()
    context = {
        "groups": groups,
        "students": students,
        "student_count": student_count,
        "paid_count": paid_count,
        "unpaid_count": student_count - paid_count,
        "validation_pending_count": validation_pending_count,
    }
    return render(request, "school/teacher_dashboard.html", context)


@login_required
def admin_overview_dashboard(request):
    if not is_school_admin(request.user):
        raise PermissionDenied

    User = get_user_model()
    teacher_queryset = User.objects.filter(role=User.Role.TEACHER)
    recent_students = (
        Student.objects.select_related("person", "group")
        .order_by("-created_at", "-id")[:8]
    )
    pending_teachers = teacher_queryset.filter(is_teacher_approved=False).order_by(
        "date_joined"
    )[:8]
    group_summaries = (
        TeacherGroup.objects.select_related("teacher")
        .annotate(
            active_student_count=Count("students", filter=Q(students__is_active=True)),
            paid_student_count=Count(
                "students",
                filter=Q(students__is_active=True, students__is_paid=True),
            ),
        )
        .order_by("group_name")[:8]
    )
    context = {
        "stats": {
            "applicants_total": Person.objects.count(),
            "applicants_pending": Person.objects.filter(status=Person.Status.IN_PROGRESS).count(),
            "applicants_passed": Person.objects.filter(status=Person.Status.PASSED).count(),
            "students_total": Student.objects.count(),
            "students_active": Student.objects.filter(is_active=True).count(),
            "students_paid": Student.objects.filter(is_paid=True).count(),
            "students_payment_pending": Student.objects.filter(is_paid=False).count(),
            "students_validation_pending": Student.objects.filter(
                admin_validation_status=Student.AdminValidationStatus.PENDING
            ).count(),
            "teachers_total": teacher_queryset.count(),
            "teachers_approved": teacher_queryset.filter(is_teacher_approved=True).count(),
            "teachers_pending": teacher_queryset.filter(is_teacher_approved=False).count(),
            "groups_active": TeacherGroup.objects.filter(is_active=True).count(),
        },
        "recent_students": recent_students,
        "pending_teachers": pending_teachers,
        "group_summaries": group_summaries,
    }
    return render(request, "school/admin_overview_dashboard.html", context)


@never_cache
def student_payment_upload(request):
    line_initial = get_line_initial(request)
    line_profile = get_session_line_profile(request)
    form = PaymentSlipUploadForm(
        request.POST or None,
        request.FILES or None,
        initial={"line_user_id": line_initial["line_user_id"]} if request.method == "GET" else None,
        line_profile=line_profile,
    )
    uploaded_student = None

    if request.method == "POST" and form.is_valid():
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
            **get_liff_context(request, reload_on_sync=not bool(line_initial["line_user_id"])),
        },
    )
