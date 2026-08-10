from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    google_email = models.EmailField(blank=True)
    google_connected_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.username

    def mark_google_connected(self, email):
        self.google_email = email
        self.google_connected_at = timezone.now()
