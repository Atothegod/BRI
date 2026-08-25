from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


app_name = "school"

urlpatterns = [
    path("", views.registration, name="registration"),
    path("liff/profile/", views.liff_profile_sync, name="liff_profile_sync"),
    path(
        "agent/notifications/<str:user_key>/",
        views.agent_notifications,
        name="agent_notifications",
    ),
    path(
        "agent/notifications/<str:user_key>/latest-closed-loop/",
        views.latest_closed_loop_notification,
        name="latest_closed_loop_notification",
    ),
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
    path("school-admin/dashboard/", views.admin_overview_dashboard, name="admin_overview_dashboard"),
    path("teachers/register/", views.teacher_register, name="teacher_register"),
    path("teachers/pending/", views.teacher_pending_approval, name="teacher_pending_approval"),
    path("teachers/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("students/payment/", views.student_payment_upload, name="student_payment_upload"),
]
