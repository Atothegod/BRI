from .models import TeacherGroup


def default_teacher_group_name(user):
    nickname = str(getattr(user, "nickname", "") or "").strip()
    if nickname:
        return nickname

    full_name = " ".join(
        part
        for part in (
            str(getattr(user, "first_name", "") or "").strip(),
            str(getattr(user, "last_name", "") or "").strip(),
        )
        if part
    )
    return full_name or str(getattr(user, "username", "") or "").strip()


def ensure_default_teacher_group(user):
    if not getattr(user, "pk", None):
        return None

    group_name = default_teacher_group_name(user)
    if not group_name:
        return None

    group, _ = TeacherGroup.objects.get_or_create(
        teacher=user,
        defaults={
            "group_name": group_name,
            "is_active": True,
        },
    )
    return group
