from modules.helpers import _component_json, _cpls_list
from modules.models import Category, Class, Component, Course, Criteria, CriteriaSubject, Cpl, Student, Score, db


def _course_categories_components(course_id):
    categories = (
        Category.query.filter_by(course_id=course_id)
        .order_by(Category.sort_order)
        .all()
    )
    components = (
        Component.query.join(Category)
        .filter(Category.course_id == course_id)
        .order_by(Category.sort_order, Component.sort_order)
        .all()
    )
    criteria = (
        Criteria.query.join(Component).join(Category)
        .filter(Category.course_id == course_id)
        .all()
    )
    subjects = (
        CriteriaSubject.query.join(Criteria).join(Component).join(Category)
        .filter(Category.course_id == course_id)
        .all()
    )
    return categories, components, criteria, subjects


def _categories_payload(categories, components, criteria, subjects, cpls):
    comps_by_cat = {}
    for co in components:
        comps_by_cat.setdefault(co.category_id, []).append(co)
    crit_by_comp = {}
    for cr in criteria:
        crit_by_comp.setdefault(cr.component_id, []).append(cr)
    subj_by_crit = {}
    for s in subjects:
        subj_by_crit.setdefault(s.criteria_id, []).append(s.subject)

    result = []
    for cat in sorted(categories, key=lambda c: c.sort_order):
        comps = []
        for co in sorted(comps_by_cat.get(cat.id, []), key=lambda c: c.sort_order):
            comps.append({
                **_component_json(co, cpls),
                "criteria": [
                    {
                        "id": cr.id,
                        "level": cr.level,
                        "label": cr.label,
                        "score_min": cr.score_min,
                        "score_max": cr.score_max,
                        "subjects": subj_by_crit.get(cr.id, []),
                    }
                    for cr in sorted(crit_by_comp.get(co.id, []), key=lambda c: c.sort_order)
                ],
            })
        result.append({"id": cat.id, "key": cat.key, "label": cat.label, "components": comps})
    return result


def _get_course_structure(course_id):
    """Rubric structure of a course: categories/components/criteria/cpls (no students)."""
    course = db.session.get(Course, course_id)
    if not course:
        return None
    categories, components, criteria, subjects = _course_categories_components(course_id)
    cpls = Cpl.query.filter_by(course_id=course_id).order_by(Cpl.sort_order).all()
    classes = Class.query.filter_by(course_id=course_id).order_by(Class.name).all()

    return {
        "course": course.to_dict(),
        "categories": _categories_payload(categories, components, criteria, subjects, cpls),
        "components": [_component_json(co, cpls) for co in components],
        "criteria": [cr.to_dict() for cr in criteria],
        "cpls": _cpls_list(cpls),
        "classes": [
            {
                "id": cl.id,
                "name": cl.name,
                "lecturer": cl.lecturer,
                "owner_id": cl.owner_id,
                "student_count": Student.query.filter(
                    Student.class_id == cl.id,
                    db.func.trim(Student.nim) != "",
                    db.func.trim(Student.name) != "",
                ).count(),
            }
            for cl in classes
        ],
    }


def _get_class_data(class_id):
    """A class plus its course rubric structure and students/scores."""
    klass = db.session.get(Class, class_id)
    if not klass:
        return None
    course = db.session.get(Course, klass.course_id)
    if not course:
        return None
    categories, components, criteria, subjects = _course_categories_components(klass.course_id)
    cpls = Cpl.query.filter_by(course_id=klass.course_id).order_by(Cpl.sort_order).all()
    students = Student.query.filter_by(class_id=class_id).order_by(Student.row_no).all()
    scores = Score.query.filter(Score.student_id.in_([s.id for s in students])).all() if students else []

    return {
        "course": course.to_dict(),
        "class": klass.to_dict(),
        "categories": _categories_payload(categories, components, criteria, subjects, cpls),
        "components": [_component_json(co, cpls) for co in components],
        "criteria": [cr.to_dict() for cr in criteria],
        "students": [s.to_dict() for s in students],
        "scores": [s.to_dict() for s in scores],
        "cpls": _cpls_list(cpls),
    }


def user_owns_course(user, course_id):
    course = db.session.get(Course, course_id)
    if not course:
        return False
    if user["role"] == "tim_kurikulum":
        program = (user.get("study_program") or "").strip() or "RKS"
        return course.study_program == program
    return course.owner_id == user["id"] or user["id"] in course.get_shared_with()


def user_owns_class(user, class_id):
    klass = db.session.get(Class, class_id)
    if not klass:
        return False
    course = klass.course
    if user["role"] == "tim_kurikulum":
        program = (user.get("study_program") or "").strip() or "RKS"
        return bool(course and course.study_program == program)
    if course and (course.owner_id == user["id"] or user["id"] in course.get_shared_with()):
        return True
    return klass.owner_id == user["id"]
