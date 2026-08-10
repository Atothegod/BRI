from django.contrib import admin

from .models import (
    AttendanceRecord,
    AttendanceSession,
    HomeworkAssignment,
    HomeworkSubmission,
    Person,
    Student,
    TeacherGroup,
)


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "phone",
        "email",
        "line_id",
        "line_display_name",
        "line_user_id",
        "student_code",
        "has_paid",
        "status",
        "user",
    )
    list_filter = ("status", "gender")
    search_fields = (
        "first_name",
        "last_name",
        "nickname",
        "gender",
        "phone",
        "email",
        "line_id",
        "line_user_id",
        "line_display_name",
    )
    actions = ("mark_as_passed",)

    @admin.action(description="Mark selected people as passed")
    def mark_as_passed(self, request, queryset):
        for person in queryset:
            person.status = Person.Status.PASSED
            person.save(update_fields=["status"])


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "person",
        "group",
        "grade",
        "admin_validation_status",
        "is_paid",
        "payment_slip",
        "is_active",
    )
    list_filter = ("admin_validation_status", "is_paid", "group", "grade", "is_active", "person__gender")
    search_fields = (
        "student_id",
        "person__first_name",
        "person__last_name",
        "person__phone",
        "person__email",
    )


@admin.register(TeacherGroup)
class TeacherGroupAdmin(admin.ModelAdmin):
    list_display = ("group_name", "teacher", "grade_level", "is_active")
    list_filter = ("teacher", "grade_level", "is_active")
    search_fields = ("group_name", "grade_level", "teacher__username", "teacher__first_name", "teacher__last_name")


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ("group", "date")
    list_filter = ("group", "date")
    search_fields = ("group__group_name",)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("attendance_session", "student", "status")
    list_filter = ("status", "attendance_session__group")
    search_fields = (
        "student__student_id",
        "student__person__first_name",
        "student__person__last_name",
    )


@admin.register(HomeworkAssignment)
class HomeworkAssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "due_date")
    list_filter = ("group", "due_date")
    search_fields = ("title", "group__group_name")


@admin.register(HomeworkSubmission)
class HomeworkSubmissionAdmin(admin.ModelAdmin):
    list_display = ("homework_assignment", "student", "status", "score", "submitted_at")
    list_filter = ("status", "homework_assignment__group")
    search_fields = (
        "homework_assignment__title",
        "student__student_id",
        "student__person__first_name",
        "student__person__last_name",
    )
