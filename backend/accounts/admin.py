from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils import timezone
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import Teacher, User
from school.teacher_groups import ensure_default_teacher_group


@admin.register(User)
class UserAdmin(DjangoUserAdmin, UnfoldModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "App access type",
            {
                "fields": ("role",),
                "description": "Django admin access is controlled by superuser status, not by this role.",
            },
        ),
        ("Profile", {"fields": ("nickname",)}),
        ("Teacher approval", {"fields": ("is_teacher_approved", "teacher_approved_at")}),
        ("Google", {"fields": ("google_email", "google_connected_at")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "App access type, teacher approval, and Google",
            {"fields": ("role", "email", "nickname", "is_teacher_approved", "google_email")},
        ),
    )
    list_display = (
        "display_name",
        "email",
        "nickname",
        "google_email",
        "app_role",
        "is_teacher_approved",
        "teacher_approved_at",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = DjangoUserAdmin.list_filter + ("role", "is_teacher_approved")
    search_fields = DjangoUserAdmin.search_fields + ("nickname", "google_email")
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
        if obj.role == User.Role.TEACHER:
            ensure_default_teacher_group(obj)

    @admin.action(description="Approve selected teacher dashboard access")
    def approve_selected_teachers(self, request, queryset):
        queryset.filter(role=User.Role.TEACHER).update(
            is_teacher_approved=True,
            teacher_approved_at=timezone.now(),
        )
        for teacher in queryset.filter(role=User.Role.TEACHER):
            ensure_default_teacher_group(teacher)

    @admin.action(description="Revoke selected teacher dashboard access")
    def revoke_selected_teacher_approval(self, request, queryset):
        queryset.filter(role=User.Role.TEACHER).update(
            is_teacher_approved=False,
            teacher_approved_at=None,
        )


@admin.register(Teacher)
class TeacherAdmin(DjangoUserAdmin, UnfoldModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("email", "first_name", "last_name", "nickname")}),
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
                    "nickname",
                    "password1",
                    "password2",
                    "is_teacher_approved",
                    "google_email",
                ),
            },
        ),
    )
    list_display = (
        "display_name",
        "email",
        "nickname",
        "google_email",
        "is_teacher_approved",
        "teacher_approved_at",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_teacher_approved", "is_active")
    search_fields = ("username", "email", "google_email", "first_name", "last_name", "nickname")
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
        ensure_default_teacher_group(obj)

    @admin.action(description="Approve selected teacher dashboard access")
    def approve_selected_teachers(self, request, queryset):
        queryset.update(
            is_teacher_approved=True,
            teacher_approved_at=timezone.now(),
        )
        for teacher in queryset:
            ensure_default_teacher_group(teacher)

    @admin.action(description="Revoke selected teacher dashboard access")
    def revoke_selected_teacher_approval(self, request, queryset):
        queryset.update(
            is_teacher_approved=False,
            teacher_approved_at=None,
        )
