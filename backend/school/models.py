from django.conf import settings
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Person(TimeStampedModel):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "ดำเนินการ"
        PASSED = "passed", "ผ่าน"
        FAILED = "failed", "ไม่ผ่าน"

    class AdmissionType(models.TextChoices):
        INTERVIEW = "interview", "ผ่านสัมภาษณ์"
        ONLINE = "online", "ผ่านแบบออนไลน์"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="person",
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    nickname = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=150, blank=True)
    photo = models.ImageField(upload_to="person_photos/", null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    line_id = models.CharField(max_length=120, blank=True)
    line_user_id = models.CharField(max_length=80, blank=True)
    line_display_name = models.CharField(max_length=255, blank=True)
    line_picture_url = models.URLField(max_length=500, blank=True)
    line_connected_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    admission_type = models.CharField(
        max_length=20,
        choices=AdmissionType.choices,
        blank=True,
    )
    extra_data = models.JSONField(default=dict, blank=True)
    interview_at = models.DateTimeField(null=True, blank=True)
    interview_details = models.CharField(max_length=1000, blank=True)
    interview_notified_at = models.DateTimeField(null=True, blank=True)
    interview_confirmed_at = models.DateTimeField(null=True, blank=True)
    interview_notification_state = models.CharField(
        max_length=10, blank=True,
        choices=[("pending", "รอส่ง"), ("sent", "LINE รับข้อความแล้ว"), ("failed", "ส่งไม่สำเร็จ")],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["line_id"],
                condition=~models.Q(line_id=""),
                name="uniq_person_line_id_when_present",
            ),
            models.UniqueConstraint(
                fields=["line_user_id"],
                condition=~models.Q(line_user_id=""),
                name="uniq_person_line_user_id_when_present",
            )
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def age(self):
        if not self.date_of_birth:
            return None

        today = timezone.localdate()
        birthday_passed = (today.month, today.day) >= (
            self.date_of_birth.month,
            self.date_of_birth.day,
        )
        return today.year - self.date_of_birth.year - (not birthday_passed)

    @property
    def line_name(self):
        return self.line_display_name or self.full_name

    @property
    def student_code(self):
        if not hasattr(self, "student") or not self.student.is_paid:
            return ""
        return self.student.student_id

    @property
    def has_paid(self):
        if not hasattr(self, "student"):
            return False
        return self.student.is_paid

    @property
    def admission_type_name(self):
        if self.status != self.Status.PASSED:
            return ""
        return self.get_admission_type_display() or self.AdmissionType.INTERVIEW.label

    def connect_line_account(self, user_id, display_name="", picture_url=""):
        self.line_user_id = user_id
        self.line_display_name = display_name
        self.line_picture_url = picture_url
        self.line_connected_at = timezone.now()

    def normalize_admission_type(self):
        if self.status != self.Status.PASSED:
            self.admission_type = ""
        elif not self.admission_type:
            self.admission_type = self.AdmissionType.INTERVIEW

    def save(self, *args, **kwargs):
        original_admission_type = self.admission_type
        self.normalize_admission_type()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and self.admission_type != original_admission_type:
            kwargs["update_fields"] = set(update_fields) | {"admission_type"}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


class Appointment(TimeStampedModel):
    class Type(models.TextChoices):
        INTERVIEW = "interview", "สัมภาษณ์"
        ORIENTATION = "orientation", "ปฐมนิเทศ"
        CLASS = "class", "นัดเรียน"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "กำหนดนัดแล้ว"
        CANCELLED = "cancelled", "ยกเลิก"
        COMPLETED = "completed", "เสร็จสิ้น"

    appointment_type = models.CharField(max_length=20, choices=Type.choices)
    title = models.CharField(max_length=255)
    starts_at = models.DateTimeField()
    location = models.CharField(max_length=500, blank=True)
    meeting_url = models.URLField(max_length=1000, blank=True)
    details = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_appointments",
    )

    class Meta:
        ordering = ("-starts_at", "-pk")

    def __str__(self):
        return f"{self.title} - {timezone.localtime(self.starts_at):%d/%m/%Y %H:%M}"


class AppointmentSlot(TimeStampedModel):
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="slots",
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    capacity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("starts_at", "pk")

    def __str__(self):
        local_start = timezone.localtime(self.starts_at)
        local_end = timezone.localtime(self.ends_at)
        return f"{local_start:%d/%m/%Y %H:%M}-{local_end:%H:%M} ({self.capacity})"


class AppointmentParticipant(TimeStampedModel):
    class ResponseStatus(models.TextChoices):
        WAITING = "waiting", "รอตอบรับ"
        CONFIRMED = "confirmed", "ยืนยันแล้ว"
        DECLINED = "declined", "ไม่สะดวกเข้าร่วม"

    class NotificationStatus(models.TextChoices):
        PENDING = "pending", "รอส่ง"
        SENT = "sent", "LINE รับข้อความแล้ว"
        FAILED = "failed", "ส่งไม่สำเร็จ"

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="appointment_participations",
    )
    selected_slot = models.ForeignKey(
        AppointmentSlot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participants",
    )
    response_status = models.CharField(
        max_length=20,
        choices=ResponseStatus.choices,
        default=ResponseStatus.WAITING,
    )
    notification_status = models.CharField(
        max_length=20,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    notification_error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("appointment", "person"),
                name="uniq_appointment_participant",
            ),
        ]

    def __str__(self):
        return f"{self.appointment.title} - {self.person.full_name}"


class TeacherGroup(TimeStampedModel):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teacher_groups",
    )
    group_name = models.CharField(max_length=255)
    grade_level = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        if self.grade_level:
            return f"{self.group_name} ({self.grade_level})"
        return self.group_name


class Student(TimeStampedModel):
    class AdminValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        NEEDS_FIX = "needs_fix", "Needs fix"

    student_id = models.CharField(max_length=20, unique=True, blank=True)
    person = models.OneToOneField(
        Person,
        on_delete=models.PROTECT,
        related_name="student",
    )
    group = models.ForeignKey(
        TeacherGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    grade = models.CharField(max_length=100, blank=True)
    admin_validation_status = models.CharField(
        max_length=20,
        choices=AdminValidationStatus.choices,
        default=AdminValidationStatus.PENDING,
    )
    is_paid = models.BooleanField(default=False)
    payment_slip = models.ImageField(upload_to="payment_slips/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def next_student_id(cls):
        max_number = 0
        for value in cls.objects.filter(student_id__startswith="bri-").values_list(
            "student_id",
            flat=True,
        ):
            suffix = value.removeprefix("bri-")
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"bri-{max_number + 1:04d}"

    def save(self, *args, **kwargs):
        if not self.student_id:
            self.student_id = self.next_student_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_id} - {self.person.full_name}"


def line_notification_sent(person, key):
    return bool((person.extra_data or {}).get("line_notifications", {}).get(key))


def mark_line_notification_sent(person, key):
    extra_data = dict(person.extra_data or {})
    notifications = dict(extra_data.get("line_notifications", {}))
    notifications[key] = timezone.now().isoformat()
    extra_data["line_notifications"] = notifications
    Person.objects.filter(pk=person.pk).update(extra_data=extra_data)
    person.extra_data = extra_data


@receiver(pre_save, sender=Person)
def remember_previous_person_status(sender, instance, **kwargs):
    instance._previous_status = None
    if instance.pk:
        instance._previous_status = (
            Person.objects.filter(pk=instance.pk)
            .values_list("status", flat=True)
            .first()
        )


@receiver(post_save, sender=Person)
def handle_passed_person(sender, instance, **kwargs):
    if instance.status != Person.Status.PASSED:
        return

    student, _ = Student.objects.get_or_create(person=instance)
    previous_status = getattr(instance, "_previous_status", None)
    if previous_status == Person.Status.PASSED or line_notification_sent(
        instance,
        "interview_passed",
    ):
        return

    from .line import notify_interview_passed

    if notify_interview_passed(instance, student):
        mark_line_notification_sent(instance, "interview_passed")


@receiver(pre_save, sender=Student)
def remember_previous_student_payment_status(sender, instance, **kwargs):
    instance._previous_is_paid = None
    if instance.pk:
        instance._previous_is_paid = (
            Student.objects.filter(pk=instance.pk)
            .values_list("is_paid", flat=True)
            .first()
        )


@receiver(post_save, sender=Student)
def notify_student_payment_approved(sender, instance, **kwargs):
    previous_is_paid = getattr(instance, "_previous_is_paid", None)
    if not instance.is_paid or previous_is_paid is True:
        return

    person = instance.person
    if line_notification_sent(person, "payment_approved"):
        return

    from .line import notify_payment_approved

    if notify_payment_approved(person, instance):
        mark_line_notification_sent(person, "payment_approved")


class AttendanceSession(TimeStampedModel):
    group = models.ForeignKey(
        TeacherGroup,
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
    )
    date = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["group", "date"],
                name="uniq_attendance_session_group_date",
            )
        ]

    def __str__(self):
        return f"{self.group} - {self.date}"


class AttendanceRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        ABSENT = "absent", "Absent"
        LATE = "late", "Late"

    attendance_session = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    status = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attendance_session", "student"],
                name="uniq_attendance_record_session_student",
            )
        ]

    def __str__(self):
        return f"{self.student} - {self.attendance_session}"


class HomeworkAssignment(TimeStampedModel):
    group = models.ForeignKey(
        TeacherGroup,
        on_delete=models.CASCADE,
        related_name="homework_assignments",
    )
    title = models.CharField(max_length=255)
    due_date = models.DateField()

    def __str__(self):
        return self.title


class HomeworkSubmission(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUBMITTED = "submitted", "Submitted"
        LATE = "late", "Late"

    homework_assignment = models.ForeignKey(
        HomeworkAssignment,
        on_delete=models.CASCADE,
        related_name="homework_submissions",
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="homework_submissions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    submission_file = models.FileField(
        upload_to="homework_submissions/",
        null=True,
        blank=True,
    )
    student_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["homework_assignment", "student"],
                name="uniq_homework_submission_assignment_student",
            )
        ]

    def __str__(self):
        return f"{self.homework_assignment} - {self.student}"
