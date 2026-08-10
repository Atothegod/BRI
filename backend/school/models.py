from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
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
    extra_data = models.JSONField(default=dict, blank=True)

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
        if not hasattr(self, "student"):
            return ""
        return self.student.student_id

    @property
    def has_paid(self):
        if not hasattr(self, "student"):
            return False
        return self.student.is_paid

    def connect_line_account(self, user_id, display_name="", picture_url=""):
        self.line_user_id = user_id
        self.line_display_name = display_name
        self.line_picture_url = picture_url
        self.line_connected_at = timezone.now()

    def __str__(self):
        return self.full_name


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


@receiver(post_save, sender=Person)
def create_student_for_passed_person(sender, instance, **kwargs):
    if instance.status != Person.Status.PASSED:
        return

    Student.objects.get_or_create(person=instance)


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
