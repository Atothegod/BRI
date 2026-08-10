from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
        ("Google", {"fields": ("google_email", "google_connected_at")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Role and Google", {"fields": ("role", "email", "google_email")}),
    )
    list_display = (
        "username",
        "email",
        "google_email",
        "role",
        "is_staff",
        "is_superuser",
        "is_active",
    )
    list_filter = DjangoUserAdmin.list_filter + ("role",)
    readonly_fields = ("google_connected_at",)
