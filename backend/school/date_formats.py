from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.utils import timezone


THAI_MONTHS = (
    "",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)

THAI_WEEKDAYS = (
    "จันทร์",
    "อังคาร",
    "พุธ",
    "พฤหัสบดี",
    "ศุกร์",
    "เสาร์",
    "อาทิตย์",
)

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def bangkok_datetime(value):
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value, BANGKOK_TZ)
        return value.replace(tzinfo=BANGKOK_TZ)
    return value


def thai_date(value, *, include_weekday=False, include_time=False, month_year=False):
    if not isinstance(value, (date, datetime)):
        return ""

    local_value = bangkok_datetime(value)
    if month_year:
        return f"{THAI_MONTHS[local_value.month]} {local_value.year}"

    label = f"{local_value.day} {THAI_MONTHS[local_value.month]} {local_value.year}"
    if include_weekday:
        label = f"{THAI_WEEKDAYS[local_value.weekday()]}ที่ {label}"
    if include_time and isinstance(local_value, datetime):
        label = f"{label} {local_value:%H:%M} น."
    return label
