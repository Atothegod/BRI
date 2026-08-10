from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


app_name = "school"

urlpatterns = [
    path("", views.registration, name="registration"),
    path("liff/profile/", views.liff_profile_sync, name="liff_profile_sync"),
    path("registration/success/", views.registration_success, name="registration_success"),
    path("results/", views.announcement_result, name="announcement_result"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="school/login.html"),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="school:login"),
        name="logout",
    ),
    path("teachers/register/", views.teacher_register, name="teacher_register"),
    path("teachers/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("students/payment/", views.student_payment_upload, name="student_payment_upload"),
]
