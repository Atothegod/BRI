from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .models import (
    AttendanceRecord,
    AttendanceSession,
    HomeworkAssignment,
    HomeworkSubmission,
    Student,
    TeacherGroup,
    TeacherStudentAssessment,
)
from .views import is_school_admin


@login_required(login_url="admin:login")
@never_cache
def admin_learning_dashboard(request):
    if not is_school_admin(request.user):
        raise PermissionDenied

    groups = list(TeacherGroup.objects.filter(is_active=True).prefetch_related("teachers").order_by("group_name"))
    selected_group = None
    group_id = request.GET.get("group", "").strip()
    if group_id.isdigit():
        selected_group = next((group for group in groups if group.pk == int(group_id)), None)

    students = list(
        Student.objects.select_related("person", "group")
        .filter(is_active=True, group__is_active=True)
        .filter(group=selected_group) if selected_group else
        Student.objects.select_related("person", "group").filter(is_active=True, group__is_active=True)
    )
    students.sort(key=lambda student: (student.group.group_name, student.student_id))
    student_ids = [student.pk for student in students]
    group_ids = {student.group_id for student in students}

    global_session_count = AttendanceSession.objects.filter(group__isnull=True).count()
    group_session_counts = defaultdict(int)
    for session_group_id in AttendanceSession.objects.filter(group_id__in=group_ids).values_list("group_id", flat=True):
        group_session_counts[session_group_id] += 1

    attendance_by_student = defaultdict(lambda: defaultdict(int))
    latest_attendance = {}
    records = (
        AttendanceRecord.objects.filter(student_id__in=student_ids)
        .filter(Q(attendance_session__group__isnull=True) | Q(attendance_session__group_id__in=group_ids))
        .select_related("attendance_session")
        .order_by("student_id", "-attendance_session__date", "-attendance_session__starts_at", "-pk")
    )
    for record in records:
        attendance_by_student[record.student_id][record.status] += 1
        latest_attendance.setdefault(record.student_id, record)

    assignment_counts = defaultdict(int)
    for assignment_group_id in HomeworkAssignment.objects.filter(group_id__in=group_ids).values_list("group_id", flat=True):
        assignment_counts[assignment_group_id] += 1
    submitted_counts = defaultdict(int)
    submitted_statuses = (HomeworkSubmission.Status.SUBMITTED, HomeworkSubmission.Status.LATE)
    for submission_student_id in HomeworkSubmission.objects.filter(
        student_id__in=student_ids,
        status__in=submitted_statuses,
    ).values_list("student_id", flat=True):
        submitted_counts[submission_student_id] += 1

    manual_care_ids = set(
        TeacherStudentAssessment.objects.filter(student_id__in=student_ids, needs_care=True)
        .values_list("student_id", flat=True)
    )

    totals = {"present": 0, "late": 0, "absent": 0, "leave": 0, "homework_submitted": 0, "homework_total": 0}
    follow_up_count = 0
    for student in students:
        counts = attendance_by_student[student.pk]
        student.present_count = counts[AttendanceRecord.Status.PRESENT]
        student.late_count = counts[AttendanceRecord.Status.LATE]
        student.absent_count = counts[AttendanceRecord.Status.ABSENT]
        student.leave_count = counts[AttendanceRecord.Status.LEAVE]
        student.attendance_total = global_session_count + group_session_counts[student.group_id]
        student.attended_count = student.present_count + student.late_count
        student.attendance_percent = round(student.attended_count * 100 / student.attendance_total) if student.attendance_total else None
        student.latest_attendance = latest_attendance.get(student.pk)
        student.homework_total = assignment_counts[student.group_id]
        student.homework_submitted = submitted_counts[student.pk]
        student.homework_missing = max(0, student.homework_total - student.homework_submitted)
        student.homework_percent = round(student.homework_submitted * 100 / student.homework_total) if student.homework_total else None
        student.manual_care = student.pk in manual_care_ids
        student.needs_follow_up = (
            student.manual_care
            or (student.attendance_percent is not None and student.attendance_percent < 75)
            or (student.homework_percent is not None and student.homework_percent < 70)
        )
        follow_up_count += int(student.needs_follow_up)
        totals["present"] += student.present_count
        totals["late"] += student.late_count
        totals["absent"] += student.absent_count
        totals["leave"] += student.leave_count
        totals["homework_submitted"] += student.homework_submitted
        totals["homework_total"] += student.homework_total

    return render(request, "school/admin_learning_dashboard.html", {
        "groups": groups,
        "selected_group": selected_group,
        "students": students,
        "student_count": len(students),
        "follow_up_count": follow_up_count,
        "totals": totals,
    })
