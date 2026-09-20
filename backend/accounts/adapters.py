from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from django.contrib.auth import get_user_model
from django.utils import timezone


class TeacherGoogleSocialAccountAdapter(DefaultSocialAccountAdapter):
    def _get_google_email(self, sociallogin, data=None):
        email = None
        if data:
            email = data.get("email")
        if not email:
            email = sociallogin.account.extra_data.get("email")
        if not email and sociallogin.user:
            email = sociallogin.user.email
        return email.strip().lower() if email else ""

    def _mark_google_connected(
        self,
        user,
        google_email,
        ensure_teacher=False,
        require_reapproval=False,
    ):
        update_fields = []
        if ensure_teacher and user.role != user.Role.TEACHER:
            user.role = user.Role.TEACHER
            update_fields.append("role")
        if require_reapproval and user.is_teacher_approved:
            user.is_teacher_approved = False
            user.teacher_approved_at = None
            update_fields.extend(["is_teacher_approved", "teacher_approved_at"])
        if google_email and user.google_email != google_email:
            user.google_email = google_email
            update_fields.append("google_email")
        if google_email:
            user.google_connected_at = timezone.now()
            update_fields.append("google_connected_at")
        if update_fields:
            user.save(update_fields=sorted(set(update_fields)))

    def pre_social_login(self, request, sociallogin):
        if sociallogin.account.provider != "google":
            return

        google_email = self._get_google_email(sociallogin)
        if sociallogin.is_existing:
            if sociallogin.user and sociallogin.user.role == sociallogin.user.Role.TEACHER:
                self._mark_google_connected(sociallogin.user, google_email)
            return

        if not google_email:
            return

        User = get_user_model()
        teacher = (
            User.objects.filter(role=User.Role.TEACHER, google_email__iexact=google_email)
            .order_by("pk")
            .first()
        )
        if teacher:
            sociallogin.user = teacher
            self._mark_google_connected(teacher, google_email)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        if sociallogin.account.provider == "google":
            user.role = user.Role.TEACHER
            user.is_teacher_approved = False
            google_email = self._get_google_email(sociallogin, data)
            if google_email:
                user.email = user.email or google_email
                user.google_email = google_email
                user.google_connected_at = timezone.now()
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if sociallogin.account.provider != "google":
            return user

        self._mark_google_connected(
            user,
            self._get_google_email(sociallogin),
            ensure_teacher=True,
            require_reapproval=True,
        )
        return user
