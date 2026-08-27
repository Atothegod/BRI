from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone

from .models import Teacher, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "App access type",
            {
                "fields": ("role",),
                "description": "Django admin access is controlled by superuser status, not by this role.",
            },
        ),
        ("Teacher approval", {"fields": ("is_teacher_approved", "teacher_approved_at")}),
        ("Google", {"fields": ("google_email", "google_connected_at")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "App access type, teacher approval, and Google",
            {"fields": ("role", "email", "is_teacher_approved", "google_email")},
        ),
    )
    list_display = (
        "username",
        "email",
        "google_email",
        "app_role",
        "is_teacher_approved",
        "teacher_approved_at",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = DjangoUserAdmin.list_filter + ("role", "is_teacher_approved")
    readonly_fields = ("google_connected_at", "teacher_approved_at")
    actions = ("approve_selected_teachers", "revoke_selected_teacher_approval")

    @admin.display(description="app role")
    def app_role(self, obj):
        if obj.is_superuser:
            return "Django superuser"
        return obj.get_role_display()

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


@admin.register(Teacher)
class TeacherAdmin(DjangoUserAdmin):
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("email", "first_name", "last_name")}),
        ("Teacher approval", {"fields": ("is_teacher_approved", "teacher_approved_at")}),
        ("Google", {"fields": ("google_email", "google_connected_at")}),
        ("Status", {"fields": ("is_active",)}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "password1",
                    "password2",
                    "is_teacher_approved",
                    "google_email",
                ),
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "google_email",
        "is_teacher_approved",
        "teacher_approved_at",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_teacher_approved", "is_active")
    search_fields = ("username", "email", "google_email", "first_name", "last_name")
    ordering = ("username",)
    readonly_fields = ("google_connected_at", "teacher_approved_at", "last_login", "date_joined")
    actions = ("approve_selected_teachers", "revoke_selected_teacher_approval")

    def save_model(self, request, obj, form, change):
        obj.role = User.Role.TEACHER
        if obj.is_teacher_approved and not obj.teacher_approved_at:
            obj.teacher_approved_at = timezone.now()
        elif not obj.is_teacher_approved:
            obj.teacher_approved_at = None
        super().save_model(request, obj, form, change)

    @admin.action(description="Approve selected teacher dashboard access")
    def approve_selected_teachers(self, request, queryset):
        queryset.update(
            is_teacher_approved=True,
            teacher_approved_at=timezone.now(),
        )

    @admin.action(description="Revoke selected teacher dashboard access")
    def revoke_selected_teacher_approval(self, request, queryset):
        queryset.update(
            is_teacher_approved=False,
            teacher_approved_at=None,
        )
