from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView

from . import views
from . import interviews
from . import student_groups


app_name = "school"

urlpatterns = [
    path(
        "school-admin/student-groups/",
        student_groups.student_group_assignment,
        name="student_group_assignment",
    ),
    path("school-admin/appointments/", interviews.interview_schedule, name="appointment_schedule"),
    path("school-admin/appointments/<int:pk>/notify/", interviews.interview_notify, name="appointment_notify"),
    path("school-admin/appointments/status/", interviews.interview_confirmation_status, name="appointment_confirmation_status"),
    path("appointments/confirm/", interviews.interview_confirmation, name="appointment_confirmation"),
    path(
        "school-admin/interviews/",
        RedirectView.as_view(pattern_name="school:appointment_schedule", permanent=False, query_string=True),
        name="legacy_interview_schedule",
    ),
    path("school-admin/interviews/<int:pk>/notify/", interviews.interview_notify, name="legacy_interview_notify"),
    path("school-admin/interviews/status/", interviews.interview_confirmation_status, name="legacy_interview_confirmation_status"),
    path(
        "interviews/confirm/",
        RedirectView.as_view(pattern_name="school:appointment_confirmation", permanent=False, query_string=True),
        name="legacy_interview_confirmation",
    ),
    path("", views.registration, name="registration"),
    path("liff/profile/", views.liff_profile_sync, name="liff_profile_sync"),
    path("line/results/", views.liff_results_launch, name="liff_results_launch"),
    path("line/payment/", views.liff_payment_launch, name="liff_payment_launch"),
    path("line/students/", views.liff_student_dashboard_launch, name="liff_student_dashboard_launch"),
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
        views.TeacherLoginView.as_view(),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="school:login"),
        name="logout",
    ),
    path("login/redirect/", views.post_login_redirect, name="post_login_redirect"),
    path("school-admin/dashboard/", views.admin_overview_dashboard, name="admin_overview_dashboard"),
    path("teachers/register/", views.teacher_register, name="teacher_register"),
    path("teachers/pending/", views.teacher_pending_approval, name="teacher_pending_approval"),
    path("teachers/dashboard/", views.teacher_dashboard, name="teacher_dashboard"),
    path("teachers/calendar/", views.teacher_calendar, name="teacher_calendar"),
    path("teachers/calendar/participants/<int:pk>/notify/", views.teacher_calendar_notify, name="teacher_calendar_notify"),
    path("students/dashboard/", views.student_dashboard, name="student_dashboard"),
    path("students/homework/", views.student_homework_upload, name="student_homework_upload"),
    path("students/payment/", views.student_payment_upload, name="student_payment_upload"),
]
