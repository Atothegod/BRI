from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
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


@login_required(login_url="admin:login")
@never_cache
def student_group_assignment(request):
    if not is_school_admin(request.user):
        raise PermissionDenied

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

    query = request.GET.get("q", "").strip()
    assignment = request.GET.get("assignment", "unassigned")
    teacher_id = request.GET.get("teacher", "").strip()
    group_id = request.GET.get("group", "").strip()
    if teacher_id.isdigit() or group_id.isdigit():
        assignment = "assigned"
    students = assignable_students().select_related("person", "group", "group__teacher")
    if query:
        students = students.filter(
            Q(student_id__icontains=query)
            | Q(person__first_name__icontains=query)
            | Q(person__last_name__icontains=query)
            | Q(person__nickname__icontains=query)
            | Q(person__phone__icontains=query)
        )
    if assignment == "unassigned":
        students = students.filter(group__isnull=True)
    elif assignment == "assigned":
        students = students.filter(group__isnull=False)
    if teacher_id.isdigit():
        students = students.filter(group__teacher_id=int(teacher_id))
    if group_id.isdigit():
        students = students.filter(group_id=int(group_id))
    students = students.order_by("student_id", "pk")

    groups = list(
        assignable_groups().select_related("teacher").annotate(
            student_count=Count(
                "students",
                filter=Q(students__is_active=True, students__is_paid=True),
            )
        ).order_by("teacher__first_name", "teacher__last_name", "teacher__username", "group_name")
    )
    teachers = []
    teacher_ids = set()
    for group in groups:
        if group.teacher_id not in teacher_ids:
            teachers.append(group.teacher)
            teacher_ids.add(group.teacher_id)

    page = Paginator(students, 50).get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)
    page_query = query_params.urlencode()
    base_students = assignable_students()
    return render(request, "school/student_group_assignment.html", {
        "form": form,
        "page_obj": page,
        "groups": groups,
        "teachers": teachers,
        "query": query,
        "filters": {
            "assignment": assignment,
            "teacher": teacher_id,
            "group": group_id,
        },
        "has_filters": bool(query or assignment != "unassigned" or teacher_id or group_id),
        "page_query_prefix": f"?{page_query}&" if page_query else "?",
        "selected_ids": request.POST.getlist("students"),
        "stats": {
            "total": base_students.count(),
            "unassigned": base_students.filter(group__isnull=True).count(),
            "assigned": base_students.filter(group__isnull=False).count(),
            "groups": len(groups),
        },
    })
