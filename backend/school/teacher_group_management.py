from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from .models import TeacherGroup
from .views import is_school_admin


def active_teachers():
    User = get_user_model()
    return User.objects.filter(role=User.Role.TEACHER, is_active=True, is_teacher_approved=True)


class TeacherGroupCreateForm(forms.ModelForm):
    class Meta:
        model = TeacherGroup
        fields = ("group_name",)
        labels = {"group_name": "ชื่อกลุ่ม"}
        widgets = {"group_name": forms.TextInput(attrs={
            "placeholder": "เช่น กลุ่ม Moses", "autocomplete": "off", "maxlength": 255,
        })}

    def clean_group_name(self):
        name = " ".join(self.cleaned_data["group_name"].split())
        if TeacherGroup.objects.filter(group_name__iexact=name, is_active=True).exists():
            raise forms.ValidationError("มีชื่อกลุ่มนี้อยู่แล้ว")
        return name


def move_teacher(request):
    teacher_id = request.POST.get("teacher", "").strip()
    group_id = request.POST.get("group", "").strip()
    if not teacher_id.isdigit() or (group_id and not group_id.isdigit()):
        return JsonResponse({"ok": False, "message": "ข้อมูลการย้ายอาจารย์ไม่ถูกต้อง"}, status=400)

    with transaction.atomic():
        teacher = active_teachers().select_for_update().filter(pk=int(teacher_id)).first()
        if teacher is None:
            return JsonResponse({"ok": False, "message": "บัญชีผู้สอนนี้ไม่พร้อมใช้งาน"}, status=400)
        destination = None
        if group_id:
            destination = TeacherGroup.objects.select_for_update().filter(pk=int(group_id), is_active=True).first()
            if destination is None:
                return JsonResponse({"ok": False, "message": "ไม่พบกลุ่มปลายทาง"}, status=400)

        current_group_ids = list(
            TeacherGroup.objects.filter(
                Q(teachers=teacher) | Q(teacher=teacher),
                is_active=True,
            ).values_list("pk", flat=True).distinct()
        )
        current_groups = list(
            TeacherGroup.objects.select_for_update().filter(pk__in=current_group_ids)
        )
        previous_group_ids = [group.pk for group in current_groups]
        for group in current_groups:
            group.teachers.remove(teacher)
            if group.teacher_id == teacher.pk:
                group.teacher = group.teachers.order_by("pk").first()
                group.save(update_fields=["teacher", "updated_at"])

        if destination is not None:
            destination.teachers.add(teacher)
            if destination.teacher_id is None:
                destination.teacher = teacher
                destination.save(update_fields=["teacher", "updated_at"])

    destination_name = destination.group_name if destination else "ยังไม่มีกลุ่ม"
    return JsonResponse({
        "ok": True,
        "teacher_id": teacher.pk,
        "previous_group_ids": previous_group_ids,
        "group_id": destination.pk if destination else None,
        "group_name": destination_name,
        "message": f"ย้าย {teacher.teacher_display_name} ไปยัง {destination_name} เรียบร้อยแล้ว",
    })


@login_required(login_url="admin:login")
@never_cache
def teacher_group_management(request):
    if not is_school_admin(request.user):
        raise PermissionDenied
    if request.method == "POST" and request.headers.get("x-requested-with") == "XMLHttpRequest":
        return move_teacher(request)

    form = TeacherGroupCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        messages.success(request, f"สร้างกลุ่ม {group.group_name} เรียบร้อยแล้ว")
        return redirect("school:teacher_group_management")

    teachers = list(active_teachers().order_by("nickname", "first_name", "username"))
    groups = list(
        TeacherGroup.objects.filter(is_active=True)
        .select_related("teacher").prefetch_related("teachers")
        .annotate(active_student_count=Count("students", filter=Q(students__is_active=True)))
        .order_by("group_name", "pk")
    )
    teacher_group = {}
    for group in groups:
        for teacher in group.teacher_list:
            if teacher and teacher.is_active and teacher.is_teacher_approved:
                teacher_group.setdefault(teacher.pk, group.pk)

    teachers_by_group = {group.pk: [] for group in groups}
    unassigned_teachers = []
    for teacher in teachers:
        group_id = teacher_group.get(teacher.pk)
        teacher.managed_group_id = group_id
        if group_id in teachers_by_group:
            teachers_by_group[group_id].append(teacher)
        else:
            unassigned_teachers.append(teacher)
    for group in groups:
        group.managed_teachers = teachers_by_group[group.pk]

    return render(request, "school/teacher_group_management.html", {
        "form": form, "groups": groups, "unassigned_teachers": unassigned_teachers,
        "stats": {"teachers": len(teachers), "assigned": len(teachers) - len(unassigned_teachers), "unassigned": len(unassigned_teachers), "groups": len(groups)},
    })
