import json
from urllib import parse, request

from django.conf import settings
from django.urls import reverse


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


def result_url(line_user_id):
    path = reverse("school:announcement_result")
    if line_user_id:
        path = f"{path}?{parse.urlencode({'line_user_id': line_user_id})}"
    return build_public_url(path)


def payment_url():
    return build_public_url(reverse("school:student_payment_upload"))


def send_line_push_message(line_user_id, messages):
    channel_access_token = settings.LINE_MESSAGING_CHANNEL_ACCESS_TOKEN
    if not channel_access_token or not line_user_id:
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
    except Exception:
        return False


def notify_interview_passed(person, student):
    admission_type = person.admission_type_name or "ผ่านสัมภาษณ์"
    text = (
        f"ยินดีด้วยคุณ {person.full_name}\n"
        f"ผลของคุณคือ: {admission_type}\n"
        f"รหัสนักศึกษา: {student.student_id}\n"
        f"ดูประกาศผลและขั้นตอนถัดไปได้ที่ {result_url(person.line_user_id)}"
    )
    return send_line_push_message(
        person.line_user_id,
        [{"type": "text", "text": text}],
    )


def notify_payment_approved(person, student):
    text = (
        f"ยืนยันการชำระเงินเรียบร้อยแล้ว\n"
        f"ยินดีด้วยคุณ {person.full_name} คุณเป็นนักศึกษา BRI อย่างสมบูรณ์\n"
        f"รหัสนักศึกษา: {student.student_id}\n"
        f"ตรวจสอบข้อมูลของคุณได้ที่ {result_url(person.line_user_id)}"
    )
    return send_line_push_message(
        person.line_user_id,
        [{"type": "text", "text": text}],
    )
