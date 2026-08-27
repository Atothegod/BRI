from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="App role for teacher/student flows. Django admin access is controlled by superuser status.",
    )
    google_email = models.EmailField(blank=True)
    google_connected_at = models.DateTimeField(null=True, blank=True)
    is_teacher_approved = models.BooleanField(
        default=False,
        help_text="Allows teacher users to access the school teacher dashboard after admin review.",
    )
    teacher_approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username

    def mark_google_connected(self, email):
        self.google_email = email
        self.google_connected_at = timezone.now()

    def can_access_teacher_dashboard(self):
        return self.is_active and self.role == self.Role.TEACHER and self.is_teacher_approved


class TeacherManager(UserManager):
    def get_queryset(self):
        return super().get_queryset().filter(role=User.Role.TEACHER)


class Teacher(User):
    objects = TeacherManager()

    class Meta:
        proxy = True
        verbose_name = "teacher"
        verbose_name_plural = "teachers"
