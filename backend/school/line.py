import json
from urllib import parse, request

from django.conf import settings


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
