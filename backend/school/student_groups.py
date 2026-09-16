from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import Person, Student, TeacherGroup
from .views import is_school_admin


def assignable_students():
    return Student.objects.filter(
        person__status=Person.Status.PASSED,
        is_paid=True,
        is_active=True,
    ).exclude(student_id="")


def assignable_groups():
    return TeacherGroup.objects.filter(
        is_active=True,
        teacher__is_active=True,
        teacher__role="TEACHER",
        teacher__is_teacher_approved=True,
    )


class StudentGroupAssignmentForm(forms.Form):
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        label="นักศึกษา",
        error_messages={
            "required": "กรุณาเลือกนักศึกษาอย่างน้อย 1 คน",
            "invalid_choice": "มีนักศึกษาที่ไม่ตรงเงื่อนไข กรุณาเลือกใหม่",
        },
    )
    group = forms.ModelChoiceField(
        queryset=TeacherGroup.objects.none(),
        label="กลุ่มเรียนและผู้สอน",
        empty_label="เลือกกลุ่มเรียน",
        error_messages={
            "required": "กรุณาเลือกกลุ่มเรียน",
            "invalid_choice": "กลุ่มเรียนนี้ไม่พร้อมใช้งาน กรุณาเลือกใหม่",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = assignable_students()
        self.fields["group"].queryset = assignable_groups().select_related("teacher").order_by(
            "teacher__first_name", "teacher__last_name", "teacher__username", "group_name"
        )

    def clean_students(self):
        students = self.cleaned_data["students"]
        if len(students) > 100:
            raise forms.ValidationError("เลือกได้ครั้งละไม่เกิน 100 คน")
        return students


def move_student_between_groups(request):
    student_id = request.POST.get("student", "").strip()
    group_id = request.POST.get("group", "").strip()
    if not student_id.isdigit() or (group_id and not group_id.isdigit()):
        return JsonResponse({"ok": False, "message": "ข้อมูลการย้ายกลุ่มไม่ถูกต้อง"}, status=400)

    with transaction.atomic():
        student = (
            assignable_students()
            .select_for_update()
            .select_related("person")
            .filter(pk=int(student_id))
            .first()
        )
        if student is None:
            return JsonResponse(
                {"ok": False, "message": "นักศึกษาคนนี้ไม่อยู่ในเงื่อนไขการจัดกลุ่มแล้ว"},
                status=400,
            )

        group = None
        if group_id:
            group = (
                assignable_groups()
                .select_for_update()
                .select_related("teacher")
                .filter(pk=int(group_id))
                .first()
            )
            if group is None:
                return JsonResponse(
                    {"ok": False, "message": "กลุ่มปลายทางไม่พร้อมใช้งานแล้ว"},
                    status=400,
                )

        previous_group_id = student.group_id
        if previous_group_id != (group.pk if group else None):
            Student.objects.filter(pk=student.pk).update(
                group=group,
                updated_at=timezone.now(),
            )

    if group:
        teacher_name = group.teacher.get_full_name() or group.teacher.username
        destination = f"{group.group_name} โดย {teacher_name}"
    else:
        destination = "ยังไม่มีกลุ่ม"

    return JsonResponse({
        "ok": True,
        "student_id": student.pk,
        "previous_group_id": previous_group_id,
        "group_id": group.pk if group else None,
        "group_name": group.group_name if group else "ยังไม่มีกลุ่ม",
        "message": f"ย้าย {student.person.full_name} ไปยัง {destination} เรียบร้อยแล้ว",
    })


@login_required(login_url="admin:login")
@never_cache
def student_group_assignment(request):
    if not is_school_admin(request.user):
        raise PermissionDenied

    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        return move_student_between_groups(request)

    form = StudentGroupAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student_ids = list(form.cleaned_data["students"].values_list("pk", flat=True))
        group_id = form.cleaned_data["group"].pk
        with transaction.atomic():
            group = assignable_groups().select_for_update().select_related("teacher").filter(pk=group_id).first()
            students = list(
                assignable_students().select_for_update().filter(pk__in=student_ids).order_by("pk")
            )
            if group is None:
                form.add_error("group", "สถานะกลุ่มหรือผู้สอนเปลี่ยนแล้ว กรุณาเลือกใหม่")
            elif len(students) != len(student_ids):
                form.add_error("students", "สถานะนักศึกษาเปลี่ยนแล้ว กรุณาเลือกใหม่")
            else:
                changed_ids = [student.pk for student in students if student.group_id != group.pk]
                if changed_ids:
                    Student.objects.filter(pk__in=changed_ids).update(
                        group=group,
                        updated_at=timezone.now(),
                    )
        if not form.errors:
            teacher_name = group.teacher.get_full_name() or group.teacher.username
            messages.success(
                request,
                f"จัดนักศึกษา {len(student_ids)} คนเข้ากลุ่ม {group.group_name} โดย {teacher_name} เรียบร้อยแล้ว",
            )
            return redirect("school:student_group_assignment")

    students = list(
        assignable_students()
        .select_related("person", "group", "group__teacher")
        .order_by("student_id", "pk")
    )

    groups = list(
        assignable_groups().select_related("teacher").annotate(
            student_count=Count(
                "students",
                filter=Q(students__is_active=True, students__is_paid=True),
            )
        ).order_by("teacher__first_name", "teacher__last_name", "teacher__username", "group_name")
    )
    students_by_group = {group.pk: [] for group in groups}
    unassigned_students = []
    other_group_students = []
    for student in students:
        if student.group_id is None:
            unassigned_students.append(student)
        elif student.group_id in students_by_group:
            students_by_group[student.group_id].append(student)
        else:
            other_group_students.append(student)

    for group in groups:
        group.board_students = students_by_group[group.pk]

    assigned_count = sum(student.group_id is not None for student in students)
    return render(request, "school/student_group_assignment.html", {
        "form": form,
        "students": students,
        "unassigned_students": unassigned_students,
        "other_group_students": other_group_students,
        "groups": groups,
        "stats": {
            "total": len(students),
            "unassigned": len(unassigned_students),
            "assigned": assigned_count,
            "groups": len(groups),
        },
    })
