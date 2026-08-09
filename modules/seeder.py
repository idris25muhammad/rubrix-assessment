import json

from modules.models import (
    Category,
    Component,
    Course,
    Cpl,
    Criteria,
    CriteriaSubject,
    db,
)
from modules.validation import validate_course_json


def seed_course_data(data, owner_id=None):
    """Insert a course (dict) into the DB. Validates first, dedupes by code+semester."""
    validate_course_json(data)
    existing = Course.query.filter_by(
        course_code=data["course_code"], semester=data.get("semester", "")
    ).first()
    if existing:
        return existing.id

    course = Course(
        owner_id=owner_id,
        course_code=data["course_code"],
        course_name=data["course_name"],
        sks=data.get("sks", 0),
        semester=data.get("semester", ""),
        study_program=data.get("study_program", ""),
        is_pbl=bool(data.get("is_pbl")),
        raw_json=json.dumps(data, ensure_ascii=False),
    )
    db.session.add(course)
    db.session.flush()

    for ci, cat in enumerate(data["categories"]):
        category = Category(course_id=course.id, key=cat["key"], label=cat["label"], sort_order=ci)
        db.session.add(category)
        db.session.flush()
        for ri, comp in enumerate(cat["components"]):
            component = Component(
                category_id=category.id,
                name=comp["name"],
                cpl_pis=json.dumps(comp.get("cpl_pis") or [], ensure_ascii=False),
                weight=comp["weight"],
                sort_order=ri,
            )
            db.session.add(component)
            db.session.flush()
            for li, crit in enumerate(comp.get("criteria", [])):
                criteria = Criteria(
                    component_id=component.id,
                    level=crit["level"],
                    label=crit["label"],
                    score_min=crit["score_min"],
                    score_max=crit["score_max"],
                    sort_order=li,
                )
                db.session.add(criteria)
                db.session.flush()
                for si, subject in enumerate(crit.get("subjects", [])):
                    db.session.add(CriteriaSubject(criteria_id=criteria.id, subject=subject, sort_order=si))

    for ci, cpl in enumerate(data.get("cpls", [])):
        db.session.add(Cpl(
            course_id=course.id,
            code=cpl["code"],
            description=cpl.get("description", ""),
            proficiency_level=int(cpl.get("proficiency_level", 3) or 3),
            so_codes=json.dumps(cpl.get("so_codes", []), ensure_ascii=False),
            sort_order=ci,
        ))

    db.session.commit()
    return course.id


def seed_course_from_json(path, owner_id=None):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return seed_course_data(data, owner_id=owner_id)
