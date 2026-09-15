from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import escape
from django.utils.timezone import now


SITEMAP_ROUTES = (
    ("school:registration", "daily", "1.0"),
    ("school:registration_success", "monthly", "0.2"),
    ("school:announcement_result", "daily", "0.6"),
    ("school:login", "monthly", "0.3"),
    ("school:teacher_register", "monthly", "0.4"),
    ("school:teacher_pending_approval", "monthly", "0.2"),
    ("school:student_payment_upload", "weekly", "0.5"),
    ("school:appointment_confirmation", "weekly", "0.3"),
    ("school:legacy_interview_confirmation", "monthly", "0.1"),
    ("school:admin_overview_dashboard", "weekly", "0.2"),
    ("school:student_group_assignment", "weekly", "0.2"),
    ("school:appointment_schedule", "weekly", "0.2"),
)


def public_sitemap_urls(request):
    site_root = request.build_absolute_uri("/")
    urls = []
    for route_name, changefreq, priority in SITEMAP_ROUTES:
        location = request.build_absolute_uri(reverse(route_name))
        urls.append(
            {
                "loc": location,
                "changefreq": changefreq,
                "priority": priority,
            }
        )
    urls.sort(key=lambda item: (item["loc"] != site_root, item["loc"]))
    return urls


def sitemap_xml(request):
    today = now().date().isoformat()
    entries = "\n".join(
        "  <url>\n"
        f"    <loc>{escape(item['loc'])}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>{item['changefreq']}</changefreq>\n"
        f"    <priority>{item['priority']}</priority>\n"
        "  </url>"
        for item in public_sitemap_urls(request)
    )
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )
    return HttpResponse(content, content_type="application/xml; charset=utf-8")
