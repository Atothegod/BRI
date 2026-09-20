from django import template

from school.date_formats import thai_date as format_thai_date


register = template.Library()


@register.filter
def thai_date(value, mode="long"):
    return format_thai_date(
        value,
        include_weekday=mode in {"weekday", "weekday_time"},
        include_time=mode in {"time", "weekday_time"},
        month_year=mode == "month_year",
    )
