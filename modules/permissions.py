"""Centralized role and resource permission helpers."""

from modules.auth import ROLE_ADMIN, ROLE_KPS
from modules.models import Class, Course, db


def is_admin(user):
    return bool(user and user.get("role") == ROLE_ADMIN)


def is_kps(user):
    return bool(user and user.get("role") == ROLE_KPS)


def user_program(user):
    """Return the user's study program code (defaults to 'RKS' if unset)."""
    if not user:
        return "RKS"
    return (user.get("study_program") or "").strip() or "RKS"


def scoped_courses_query(user):
    """Return a SQLAlchemy query for courses visible to the user."""
    if is_admin(user):
        return Course.query
    if is_kps(user):
        return Course.query.filter(Course.study_program == user_program(user))
    uid = user["id"]
    return Course.query.filter(
        db.or_(
            Course.owner_id == uid,
            Course.classes.any(Class.lecturer_id == uid),
        )
    )


def can_view_course(user, course):
    """Whether the user can view a course (admin, KPS of prodi, owner, or assigned lecturer)."""
    if not user or not course:
        return False
    if is_admin(user):
        return True
    if is_kps(user):
        return course.study_program == user_program(user)
    if course.owner_id == user["id"]:
        return True
    return Class.query.filter_by(course_id=course.id, lecturer_id=user["id"]).first() is not None


def can_edit_course(user, course):
    """Whether the user can edit course rubric, add classes, or view combined portfolio."""
    if not user or not course:
        return False
    if is_admin(user):
        return True
    if is_kps(user):
        return course.study_program == user_program(user)
    return course.owner_id == user["id"]


def can_delete_course(user, course):
    """Only admin or the original course owner may delete a course."""
    if not user or not course:
        return False
    if is_admin(user):
        return True
    return course.owner_id == user["id"]


def can_view_class(user, klass):
    """Whether the user can view/assess/export/portfolio a specific class."""
    if not user or not klass or not klass.course:
        return False
    if is_admin(user):
        return True
    if is_kps(user):
        return klass.course.study_program == user_program(user)
    if klass.course.owner_id == user["id"]:
        return True
    return klass.lecturer_id == user["id"]


def can_edit_class(user, klass):
    """Whether the user can edit class info, scores, import/export, or assessment links."""
    return can_view_class(user, klass)


def can_delete_class(user, klass):
    """Only admin or the original course owner may delete a class."""
    if not user or not klass or not klass.course:
        return False
    if is_admin(user):
        return True
    return klass.course.owner_id == user["id"]
