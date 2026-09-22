from django.contrib import admin, messages
from django.db.models import Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from .forms import load_country_data
from .line import line_push_unavailable_reason, notify_interview_passed
from .models import (
    AttendanceRecord,
    AttendanceSession,
    Appointment,
    AppointmentParticipant,
    AppointmentSlot,
    HomeworkAssignment,
    HomeworkSubmission,
    Person,
    Student,
    TeacherGroup,
    line_notification_sent,
    mark_line_notification_sent,
)


admin.site.index_template = "school/admin_index.html"
admin.site.site_header = "BRI School Admin"
admin.site.site_title = "BRI Admin"
admin.site.index_title = "ภาพรวมระบบโรงเรียน"


@admin.register(Appointment)
class AppointmentAdmin(UnfoldModelAdmin):
    list_display = ("title", "appointment_type", "starts_at", "status", "participant_total", "created_by")
    list_filter = ("appointment_type", "status", "starts_at")
    search_fields = ("title", "location", "details")
    autocomplete_fields = ("created_by",)

    @admin.display(description="ผู้เข้าร่วม")
    def participant_total(self, obj):
        return obj.participants.count()


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(UnfoldModelAdmin):
    list_display = ("appointment", "starts_at", "ends_at", "capacity")
    list_filter = ("appointment__appointment_type", "starts_at")
    search_fields = ("appointment__title", "appointment__location")
    autocomplete_fields = ("appointment",)


@admin.register(AppointmentParticipant)
class AppointmentParticipantAdmin(UnfoldModelAdmin):
    list_display = ("appointment", "person", "selected_slot", "notification_status", "response_status", "notified_at", "confirmed_at")
    list_filter = ("appointment__appointment_type", "notification_status", "response_status")
    search_fields = ("appointment__title", "person__first_name", "person__last_name", "person__phone")
    autocomplete_fields = ("appointment", "person", "selected_slot")


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


class BRIStudyHistoryFilter(admin.SimpleListFilter):
    title = _("เคยเรียน BRI")
    parameter_name = "studied_bri"

    def lookups(self, request, model_admin):
        return (
            ("yes", "เคย"),
            ("no", "ยังไม่เคย"),
            ("unknown", "ไม่ระบุ"),
        )

    def queryset(self, request, queryset):
        studied_yes = Q(extra_data__has_studied_bri=True) | Q(extra_data__has_studied_bri="true")
        studied_no = Q(extra_data__has_studied_bri=False) | Q(extra_data__has_studied_bri="false")
        if self.value() == "yes":
            return queryset.filter(studied_yes)
        if self.value() == "no":
            return queryset.filter(studied_no)
        if self.value() == "unknown":
            return queryset.exclude(studied_yes | studied_no)
        return queryset


@admin.register(Person)
class PersonAdmin(UnfoldModelAdmin):
    list_display = (
        "applicant_display",
        "contact_display",
        "line_account_display",
        "status",
        "admission_type_display",
        "student_code_display",
        "paid_display",
        "country_display",
        "studied_bri_display",
        "goal_display",
        "vision_calling_display",
        "interview_at",
        "interview_notification_state",
        "interview_confirmed_at",
        "created_at",
    )
    list_filter = ("status", "admission_type", BRIStudyHistoryFilter, CountryCodeFilter, "gender")
    ordering = ("-created_at", "-id")
    search_fields = (
        "first_name",
        "last_name",
        "nickname",
        "gender",
        "phone",
        "email",
        "line_user_id",
        "line_display_name",
    )
    fieldsets = (
        ("นัดสัมภาษณ์", {"fields": ("interview_at", "interview_details", "interview_notification_state", "interview_notified_at", "interview_confirmed_at")}),
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
                    "line_user_id",
                    "line_display_name",
                    "line_picture_url",
                    "line_connected_at",
                    "goal_display",
                    "vision_calling_display",
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
    readonly_fields = (
        "line_connected_at",
        "goal_display",
        "vision_calling_display",
        "interview_at",
        "interview_details",
        "interview_notification_state",
        "interview_notified_at",
        "interview_confirmed_at",
    )
    actions = (
        "mark_as_passed_interview",
        "mark_as_passed_online",
        "mark_as_failed",
        "send_interview_passed_line_notification",
    )

    @admin.display(ordering="nickname", description="ผู้สมัคร")
    def applicant_display(self, obj):
        nickname = obj.nickname or "-"
        full_name = obj.full_name or "-"
        return format_html(
            '<strong>{}</strong><br><span style="color:#667085;">{}</span>',
            nickname,
            full_name,
        )

    @admin.display(ordering="phone", description="ติดต่อ")
    def contact_display(self, obj):
        phone = obj.phone or "-"
        email = obj.email or "-"
        return format_html(
            '{}<br><span style="color:#667085;">{}</span>',
            phone,
            email,
        )

    @admin.display(ordering="line_display_name", description="LINE")
    def line_account_display(self, obj):
        display_name = obj.line_display_name or "-"
        if not obj.line_user_id:
            return display_name
        return format_html(
            '{}<br><span style="color:#667085;">เชื่อมต่อแล้ว</span>',
            display_name,
        )

    @admin.display(description="ประเภทผู้เรียน")
    def admission_type_display(self, obj):
        return obj.admission_type_name or "-"

    @admin.display(ordering="student__student_id", description="รหัสนักเรียน")
    def student_code_display(self, obj):
        return obj.student_code or "-"

    @admin.display(boolean=True, ordering="student__is_paid", description="ชำระเงิน")
    def paid_display(self, obj):
        return obj.has_paid

    @admin.display(description="ประเทศ")
    def country_display(self, obj):
        return (obj.extra_data or {}).get("country_name_en") or "-"

    @admin.display(description="เคยเรียน BRI")
    def studied_bri_display(self, obj):
        value = (obj.extra_data or {}).get("has_studied_bri")
        if value is True or value == "true":
            return "เคย"
        if value is False or value == "false":
            return "ยังไม่เคย"
        return "-"

    @admin.display(description="Goal")
    def goal_display(self, obj):
        return (obj.extra_data or {}).get("goal") or "-"

    @admin.display(description="Vision calling")
    def vision_calling_display(self, obj):
        return (obj.extra_data or {}).get("vision_calling") or "-"

    @admin.action(description="Mark selected people as passed interview students")
    def mark_as_passed_interview(self, request, queryset):
        updated = 0
        for person in queryset:
            person.status = Person.Status.PASSED
            person.admission_type = Person.AdmissionType.INTERVIEW
            person.save(update_fields=["status", "admission_type"])
            updated += 1
        self.message_user(request, f"บันทึกผ่าน onsite {updated} คนแล้ว ยังไม่ได้ส่ง LINE", messages.SUCCESS)

    @admin.action(description="Mark selected people as online students")
    def mark_as_passed_online(self, request, queryset):
        updated = 0
        for person in queryset:
            person.status = Person.Status.PASSED
            person.admission_type = Person.AdmissionType.ONLINE
            person.save(update_fields=["status", "admission_type"])
            updated += 1
        self.message_user(request, f"บันทึกผ่าน online {updated} คนแล้ว ยังไม่ได้ส่ง LINE", messages.SUCCESS)

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
class StudentAdmin(UnfoldModelAdmin):
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
class TeacherGroupAdmin(UnfoldModelAdmin):
    list_display = ("group_name", "teacher", "grade_level", "is_active")
    list_filter = ("teacher", "grade_level", "is_active")
    search_fields = ("group_name", "grade_level", "teacher__username", "teacher__first_name", "teacher__last_name")


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(UnfoldModelAdmin):
    list_display = ("group", "date")
    list_filter = ("group", "date")
    search_fields = ("group__group_name",)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(UnfoldModelAdmin):
    list_display = ("attendance_session", "student", "status")
    list_filter = ("status", "attendance_session__group")
    search_fields = (
        "student__student_id",
        "student__person__first_name",
        "student__person__last_name",
    )


@admin.register(HomeworkAssignment)
class HomeworkAssignmentAdmin(UnfoldModelAdmin):
    list_display = ("title", "group", "due_date")
    list_filter = ("group", "due_date")
    search_fields = ("title", "group__group_name")


@admin.register(HomeworkSubmission)
class HomeworkSubmissionAdmin(UnfoldModelAdmin):
    list_display = ("homework_assignment", "student", "status", "score", "submitted_at", "submission_file")
    list_filter = ("status", "homework_assignment__group")
    search_fields = (
        "homework_assignment__title",
        "student__student_id",
        "student__person__first_name",
        "student__person__last_name",
    )
