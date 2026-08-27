from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        RedirectView.as_view(pattern_name="school:login", permanent=False),
        name="account_login_redirect",
    ),
    path(
        "accounts/signup/",
        RedirectView.as_view(pattern_name="school:teacher_register", permanent=False),
        name="account_signup_redirect",
    ),
    path("accounts/", include("allauth.urls")),
    path("", include("school.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
