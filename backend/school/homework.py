from pathlib import PurePath

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .forms import HomeworkUploadForm
from .models import HomeworkAssignment, HomeworkSubmission, TeacherGroup
from .views import get_liff_context, get_session_line_profile, get_student_for_line, is_school_admin


class HomeworkAssignmentForm(forms.ModelForm):
    class Meta:
        model = HomeworkAssignment
        fields = ("group", "title", "description", "due_date")
        labels = {
            "group": "มอบหมายให้กลุ่ม",
            "title": "หัวข้อการบ้าน",
            "description": "รายละเอียดและคำสั่งงาน",
            "due_date": "วันกำหนดส่ง",
        }
        widgets = {
            "group": forms.Select(attrs={"class": "homework-control"}),
            "title": forms.TextInput(attrs={
                "class": "homework-control",
                "placeholder": "เช่น การบ้านครั้งที่ 1 — ตัวตนที่แท้จริง",
                "maxlength": 255,
            }),
            "description": forms.Textarea(attrs={
                "class": "homework-control homework-control--textarea",
                "rows": 7,
                "placeholder": "อธิบายโจทย์ สิ่งที่ต้องส่ง รูปแบบไฟล์ และเกณฑ์ที่ต้องการให้นักศึกษาทำตาม",
            }),
            "due_date": forms.DateInput(attrs={"class": "homework-control", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["group"].queryset = TeacherGroup.objects.filter(is_active=True).order_by("group_name")
        self.fields["group"].empty_label = "เลือกกลุ่มนักศึกษา"

    def clean_title(self):
        return " ".join(self.cleaned_data["title"].split())


def student_context(request):
    line_profile = get_session_line_profile(request)
    line_user_id = line_profile.get("line_user_id", "").strip()
    person, student = get_student_for_line(line_user_id)
    state = (
        "missing_line" if not line_user_id else
        "ready" if student else
        "not_ready" if person else
        "missing"
    )
    return state, person, student, {
        "line_return_url": settings.LINE_RETURN_URL,
        **get_liff_context(request, reload_on_sync=not bool(line_user_id)),
    }


@login_required(login_url="admin:login")
@never_cache
@require_http_methods(["GET", "POST"])
def admin_homework(request):
    if not is_school_admin(request.user):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    form = HomeworkAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.created_by = request.user
        assignment.save()
        messages.success(request, f"เผยแพร่ {assignment.title} ให้กลุ่ม {assignment.group.group_name} แล้ว")
        return redirect("school:admin_homework")

    assignments = list(
        HomeworkAssignment.objects.select_related("group", "created_by")
        .annotate(
            target_count=Count(
                "group__students",
                filter=Q(group__students__is_active=True),
                distinct=True,
            ),
            submitted_count=Count(
                "homework_submissions",
                filter=Q(homework_submissions__status__in=(
                    HomeworkSubmission.Status.SUBMITTED,
                    HomeworkSubmission.Status.LATE,
                )),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )
    today = timezone.localdate()
    for assignment in assignments:
        assignment.missing_count = max(assignment.target_count - assignment.submitted_count, 0)
        assignment.is_overdue = assignment.due_date < today
        assignment.progress_percent = (
            round(assignment.submitted_count * 100 / assignment.target_count)
            if assignment.target_count else 0
        )

    return render(request, "school/admin_homework.html", {
        "form": form,
        "assignments": assignments,
        "assignment_count": len(assignments),
        "group_count": TeacherGroup.objects.filter(is_active=True).count(),
    })


@never_cache
@ensure_csrf_cookie
def student_homework_list(request):
    student_state, person, student, context = student_context(request)
    assignment_rows = []
    if student and student.group_id:
        submissions = {
            item.homework_assignment_id: item
            for item in HomeworkSubmission.objects.filter(
                student=student,
                homework_assignment__group=student.group,
            )
        }
        today = timezone.localdate()
        assignments = HomeworkAssignment.objects.filter(group=student.group).order_by("due_date", "created_at")
        for assignment in assignments:
            submission = submissions.get(assignment.pk)
            assignment_rows.append({
                "assignment": assignment,
                "submission": submission,
                "is_overdue": assignment.due_date < today and not submission,
                "is_submitted": bool(submission and submission.status in (
                    HomeworkSubmission.Status.SUBMITTED,
                    HomeworkSubmission.Status.LATE,
                )),
            })

    context.update({
        "student_state": student_state,
        "person": person,
        "student": student,
        "assignment_rows": assignment_rows,
    })
    return render(request, "school/student_homework_list.html", context)


@never_cache
@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def student_homework_detail(request, pk):
    student_state, person, student, context = student_context(request)
    if not student or not student.group_id:
        messages.error(request, "ยังไม่พบกลุ่มนักศึกษาสำหรับเปิดการบ้านนี้")
        return redirect("school:student_homework_upload")

    assignment = get_object_or_404(HomeworkAssignment, pk=pk, group=student.group)
    submission = HomeworkSubmission.objects.filter(
        homework_assignment=assignment,
        student=student,
    ).first()
    form = HomeworkUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        submission = form.save(student, assignment)
        messages.success(request, f"Turned in — ส่ง {assignment.title} เรียบร้อยแล้ว")
        return redirect("school:student_homework_detail", pk=assignment.pk)

    context.update({
        "student_state": student_state,
        "person": person,
        "student": student,
        "assignment": assignment,
        "submission": submission,
        "submission_filename": PurePath(submission.submission_file.name).name if submission and submission.submission_file else "",
        "form": form,
        "is_overdue": assignment.due_date < timezone.localdate(),
    })
    return render(request, "school/student_homework_detail.html", context)
