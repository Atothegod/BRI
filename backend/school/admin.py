from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .forms import load_country_data
from .line import line_push_unavailable_reason, notify_interview_passed
from .models import (
    AttendanceRecord,
    AttendanceSession,
    HomeworkAssignment,
    HomeworkSubmission,
    Person,
    Student,
    TeacherGroup,
    line_notification_sent,
    mark_line_notification_sent,
)


class CountryCodeFilter(admin.SimpleListFilter):
    title = _("ประเทศ")
    parameter_name = "country"

    def lookups(self, request, model_admin):
        used_codes = set(
            Person.objects.exclude(extra_data__country_code__isnull=True)
            .exclude(extra_data__country_code="")
            .values_list("extra_data__country_code", flat=True)
        )
        countries = {
            country["code"]: country["name_en"]
            for country in load_country_data()
            if country.get("code") in used_codes
        }
        return [(code, countries.get(code, code)) for code in sorted(used_codes)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(extra_data__country_code=self.value())
        return queryset


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
        "admission_type_display",
        "country_display",
        "user",
    )
    list_filter = ("status", "admission_type", CountryCodeFilter, "gender")
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
    fieldsets = (
        (
            "ข้อมูลผู้สมัคร",
            {
                "fields": (
                    "user",
                    ("first_name", "last_name"),
                    "nickname",
                    "gender",
                    "date_of_birth",
                    "occupation",
                    "photo",
                    "phone",
                    "email",
                    "line_id",
                    "line_user_id",
                    "line_display_name",
                    "line_picture_url",
                    "line_connected_at",
                    "extra_data",
                )
            },
        ),
        (
            "ผลสัมภาษณ์",
            {
                "description": "เลือกผลผ่าน/ไม่ผ่านก่อน แล้วเลือกประเภทผู้เรียนเฉพาะกรณีที่ผ่าน",
                "fields": (("status", "admission_type"),),
            },
        ),
    )
    readonly_fields = ("line_connected_at",)
    actions = (
        "mark_as_passed_interview",
        "mark_as_passed_online",
        "mark_as_failed",
        "send_interview_passed_line_notification",
    )

    @admin.display(description="ประเภทผู้เรียน")
    def admission_type_display(self, obj):
        return obj.admission_type_name or "-"

    @admin.display(description="ประเทศ")
    def country_display(self, obj):
        return (obj.extra_data or {}).get("country_name_en") or "-"

    def save_model(self, request, obj, form, change):
        previous_status = None
        if change and obj.pk:
            previous_status = (
                Person.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )

        super().save_model(request, obj, form, change)

        if obj.status == Person.Status.PASSED and previous_status != Person.Status.PASSED:
            obj.refresh_from_db()
            self._message_line_notification_status(request, obj)

    @admin.action(description="Mark selected people as passed interview students")
    def mark_as_passed_interview(self, request, queryset):
        stats = {"sent": 0, "missing_line_user_id": 0, "missing_channel_access_token": 0, "failed": 0}
        for person in queryset:
            person.status = Person.Status.PASSED
            person.admission_type = Person.AdmissionType.INTERVIEW
            person.save(update_fields=["status", "admission_type"])
            person.refresh_from_db()
            stats[self._line_notification_status(person)] += 1
        self._message_line_notification_summary(request, stats)

    @admin.action(description="Mark selected people as online students")
    def mark_as_passed_online(self, request, queryset):
        stats = {"sent": 0, "missing_line_user_id": 0, "missing_channel_access_token": 0, "failed": 0}
        for person in queryset:
            person.status = Person.Status.PASSED
            person.admission_type = Person.AdmissionType.ONLINE
            person.save(update_fields=["status", "admission_type"])
            person.refresh_from_db()
            stats[self._line_notification_status(person)] += 1
        self._message_line_notification_summary(request, stats)

    @admin.action(description="Mark selected people as failed")
    def mark_as_failed(self, request, queryset):
        for person in queryset:
            person.status = Person.Status.FAILED
            person.save(update_fields=["status"])

    @admin.action(description="Send LINE interview-passed notification")
    def send_interview_passed_line_notification(self, request, queryset):
        stats = {"sent": 0, "missing_line_user_id": 0, "missing_channel_access_token": 0, "failed": 0}
        for person in queryset.filter(status=Person.Status.PASSED):
            student, _ = Student.objects.get_or_create(person=person)
            if notify_interview_passed(person, student):
                mark_line_notification_sent(person, "interview_passed")
            person.refresh_from_db()
            stats[self._line_notification_status(person)] += 1
        self._message_line_notification_summary(request, stats)

    def _line_notification_status(self, person):
        if line_notification_sent(person, "interview_passed"):
            return "sent"
        reason = line_push_unavailable_reason(person)
        return reason or "failed"

    def _message_line_notification_status(self, request, person):
        status = self._line_notification_status(person)
        if status == "sent":
            self.message_user(request, "ส่ง LINE แจ้งผลผ่านให้ผู้สมัครแล้ว", messages.SUCCESS)
        elif status == "missing_line_user_id":
            self.message_user(request, "ยังไม่ได้ส่ง LINE: ผู้สมัครยังไม่มี LINE user id", messages.WARNING)
        elif status == "missing_channel_access_token":
            self.message_user(request, "ยังไม่ได้ส่ง LINE: ยังไม่ได้ตั้ง LINE_MESSAGING_CHANNEL_ACCESS_TOKEN", messages.WARNING)
        else:
            self.message_user(request, "ส่ง LINE แจ้งผลผ่านไม่สำเร็จ กรุณาดู backend logs", messages.WARNING)

    def _message_line_notification_summary(self, request, stats):
        parts = []
        if stats["sent"]:
            parts.append(f"ส่งสำเร็จ {stats['sent']} คน")
        if stats["missing_line_user_id"]:
            parts.append(f"ไม่มี LINE user id {stats['missing_line_user_id']} คน")
        if stats["missing_channel_access_token"]:
            parts.append(f"ยังไม่ได้ตั้ง token {stats['missing_channel_access_token']} คน")
        if stats["failed"]:
            parts.append(f"ส่งไม่สำเร็จ {stats['failed']} คน")
        if parts:
            self.message_user(request, "LINE notification: " + ", ".join(parts), messages.INFO)
        else:
            self.message_user(request, "LINE notification: ไม่มีผู้สมัครที่ผ่านให้ส่งข้อความ", messages.WARNING)


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
