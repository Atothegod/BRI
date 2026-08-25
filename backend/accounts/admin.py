from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
        ("Teacher approval", {"fields": ("is_teacher_approved", "teacher_approved_at")}),
        ("Google", {"fields": ("google_email", "google_connected_at")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Role, teacher approval, and Google",
            {"fields": ("role", "email", "is_teacher_approved", "google_email")},
        ),
    )
    list_display = (
        "username",
        "email",
        "google_email",
        "role",
        "is_teacher_approved",
        "teacher_approved_at",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = DjangoUserAdmin.list_filter + ("role", "is_teacher_approved")
    readonly_fields = ("google_connected_at", "teacher_approved_at")
    actions = ("approve_selected_teachers", "revoke_selected_teacher_approval")

    def save_model(self, request, obj, form, change):
        if obj.role != User.Role.TEACHER:
            obj.is_teacher_approved = False
            obj.teacher_approved_at = None
        elif obj.is_teacher_approved and not obj.teacher_approved_at:
            obj.teacher_approved_at = timezone.now()
        elif not obj.is_teacher_approved:
            obj.teacher_approved_at = None
        super().save_model(request, obj, form, change)

    @admin.action(description="Approve selected teacher dashboard access")
    def approve_selected_teachers(self, request, queryset):
        queryset.filter(role=User.Role.TEACHER).update(
            is_teacher_approved=True,
            teacher_approved_at=timezone.now(),
        )

    @admin.action(description="Revoke selected teacher dashboard access")
    def revoke_selected_teacher_approval(self, request, queryset):
        queryset.filter(role=User.Role.TEACHER).update(
            is_teacher_approved=False,
            teacher_approved_at=None,
        )
