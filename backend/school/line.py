import json
import logging
from urllib import error
from urllib import parse, request

from django.conf import settings
from django.urls import reverse


logger = logging.getLogger(__name__)


class LineProfileError(Exception):
    pass


def normalize_line_profile(profile):
    return {
        "line_user_id": (profile.get("line_user_id") or profile.get("userId") or "").strip(),
        "line_display_name": (
            profile.get("line_display_name") or profile.get("displayName") or profile.get("name") or ""
        ).strip(),
        "line_picture_url": (
            profile.get("line_picture_url") or profile.get("pictureUrl") or profile.get("picture") or ""
        ).strip(),
    }


def verify_line_id_token(id_token):
    if not settings.LINE_LOGIN_CHANNEL_ID:
        raise LineProfileError("LINE_LOGIN_CHANNEL_ID is not configured")
    if not id_token:
        raise LineProfileError("Missing LINE ID token")

    body = parse.urlencode(
        {
            "id_token": id_token,
            "client_id": settings.LINE_LOGIN_CHANNEL_ID,
        }
    ).encode("utf-8")
    verify_request = request.Request(
        "https://api.line.me/oauth2/v2.1/verify",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with request.urlopen(verify_request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise LineProfileError("Unable to verify LINE ID token") from exc

    profile = normalize_line_profile(
        {
            "line_user_id": payload.get("sub", ""),
            "line_display_name": payload.get("name", ""),
            "line_picture_url": payload.get("picture", ""),
        }
    )
    if not profile["line_user_id"]:
        raise LineProfileError("Verified LINE profile does not contain user id")
    return profile


def build_public_url(path):
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    if not base_url:
        return path
    return f"{base_url}{path}"


def build_liff_or_public_url(path):
    if settings.LINE_LIFF_ENABLED and settings.LINE_LIFF_ID:
        return f"https://liff.line.me/{settings.LINE_LIFF_ID}{path}"
    return build_public_url(path)


def result_url(line_user_id):
    path = reverse("school:announcement_result")
    if line_user_id:
        path = f"{path}?{parse.urlencode({'line_user_id': line_user_id})}"
    return build_liff_or_public_url(path)


def payment_url():
    return build_liff_or_public_url(reverse("school:student_payment_upload"))


def line_push_unavailable_reason(person):
    if not getattr(person, "line_user_id", ""):
        return "missing_line_user_id"
    if not settings.LINE_MESSAGING_CHANNEL_ACCESS_TOKEN:
        return "missing_channel_access_token"
    return ""


def send_line_push_message(line_user_id, messages):
    channel_access_token = settings.LINE_MESSAGING_CHANNEL_ACCESS_TOKEN
    if not line_user_id:
        logger.warning("LINE push skipped: missing line_user_id")
        return False
    if not channel_access_token:
        logger.warning("LINE push skipped for %s: missing channel access token", line_user_id)
        return False

    body = json.dumps(
        {
            "to": line_user_id,
            "messages": messages,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    push_request = request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=body,
        headers={
            "Authorization": f"Bearer {channel_access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(push_request, timeout=8):
            return True
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        logger.warning(
            "LINE push failed for %s: status=%s body=%s",
            line_user_id,
            exc.code,
            response_body,
        )
        return False
    except Exception as exc:
        logger.warning("LINE push failed for %s: %s", line_user_id, exc, exc_info=True)
        return False


def build_interview_passed_flex_message(person, student):
    admission_type = (
        "ผ่านสัมภาษณ์ (ออนไลน์)"
        if person.admission_type == person.AdmissionType.ONLINE
        else "ผ่านสัมภาษณ์"
    )
    payment_status = (
        "ชำระเรียบร้อย" if student.is_paid
        else "รอตรวจสอบการชำระเงิน" if student.payment_slip
        else "รอชำระเงิน"
    )
    rows = [
        build_flex_row("ผลการคัดเลือก", admission_type),
        build_flex_row("สถานะการชำระเงิน", payment_status, color="#425B46" if student.is_paid else "#A44928"),
    ]
    if student.is_paid:
        rows.append(build_flex_row("รหัสนักศึกษา", student.student_id))
    result_link = result_url(person.line_user_id)
    pay_link = payment_url()
    return {
        "type": "flex",
        "altText": f"ยินดีด้วย {person.full_name} ผ่านการคัดเลือกแล้ว ดูประกาศผลได้ที่นี่",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "20px",
                "backgroundColor": "#12271D",
                "contents": [
                    {
                        "type": "text",
                        "text": "BRI Admission Result",
                        "color": "#C2A256",
                        "size": "xs",
                        "weight": "bold",
                    },
                    {
                        "type": "text",
                        "text": "ยินดีด้วย คุณผ่านการคัดเลือก",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold",
                        "wrap": True,
                        "margin": "sm",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": person.full_name,
                        "weight": "bold",
                        "size": "md",
                        "color": "#12271D",
                        "wrap": True,
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": rows,
                    },
                    {
                        "type": "text",
                        "text": "กดดูประกาศผลเพื่ออ่านรายละเอียดและขั้นตอนถัดไป",
                        "size": "sm",
                        "color": "#5F6B63",
                        "wrap": True,
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#F3F0E8",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "color": "#425B46",
                        "action": {
                            "type": "uri",
                            "label": "ดูประกาศผล",
                            "uri": result_link,
                        },
                    },
                    {
                        "type": "button",
                        "style": "secondary",
                        "height": "sm",
                        "action": {
                            "type": "uri",
                            "label": "ไปหน้าชำระเงิน",
                            "uri": pay_link,
                        },
                    },
                ],
            },
        },
    }


def build_payment_approved_flex_message(person, student):
    if not student.is_paid:
        raise ValueError("Payment approval message requires is_paid=True")
    result_link = result_url(person.line_user_id)
    return {
        "type": "flex",
        "altText": f"BRI ยืนยันการชำระเงินแล้ว รหัสนักศึกษา {student.student_id}",
        "contents": {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "20px",
                "backgroundColor": "#12271D",
                "contents": [
                    {
                        "type": "text",
                        "text": "BRI Payment Confirmed",
                        "color": "#C2A256",
                        "size": "xs",
                        "weight": "bold",
                    },
                    {
                        "type": "text",
                        "text": "ยินดีด้วย ยืนยันการชำระเงินแล้ว",
                        "color": "#FFFFFF",
                        "size": "lg",
                        "weight": "bold",
                        "wrap": True,
                        "margin": "sm",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"ยินดีด้วยคุณ {person.full_name}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#12271D",
                        "wrap": True,
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            build_flex_row("สถานะการชำระเงิน", "ชำระเรียบร้อย", color="#425B46"),
                            build_flex_row("รหัสนักศึกษา", student.student_id),
                        ],
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#F3F0E8",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "height": "sm",
                        "color": "#425B46",
                        "action": {
                            "type": "uri",
                            "label": "ดูข้อมูลของฉัน",
                            "uri": result_link,
                        },
                    },
                ],
            },
        },
    }


def build_flex_row(label, value, *, color="#12271D"):
    return {
        "type": "box",
        "layout": "baseline",
        "spacing": "sm",
        "contents": [
            {
                "type": "text",
                "text": label,
                "wrap": True,
                "color": "#5F6B63",
                "size": "sm",
                "flex": 3,
            },
            {
                "type": "text",
                "text": value,
                "wrap": True,
                "color": color,
                "size": "sm",
                "weight": "bold",
                "flex": 5,
            },
        ],
    }


def notify_interview_passed(person, student):
    return send_line_push_message(
        person.line_user_id,
        [build_interview_passed_flex_message(person, student)],
    )


def notify_payment_approved(person, student):
    if not student.is_paid:
        return False
    return send_line_push_message(
        person.line_user_id,
        [build_payment_approved_flex_message(person, student)],
    )
