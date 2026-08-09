import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(255), nullable=False)
    email = db.Column(String(255), nullable=False, unique=True)
    password_hash = db.Column(String(255), nullable=False)
    role = db.Column(String(30), nullable=False, default="lecturer")
    created_at = db.Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(Integer, primary_key=True)
    owner_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    course_code = db.Column(String(30), nullable=False)
    course_name = db.Column(String(255), nullable=False)
    sks = db.Column(Integer, default=0)
    semester = db.Column(String(60), default="")
    study_program = db.Column(String(120), default="")
    is_pbl = db.Column(Boolean, default=False)
    raw_json = db.Column(Text, nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", backref="courses")

    def to_dict(self):
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "course_code": self.course_code,
            "course_name": self.course_name,
            "sks": self.sks,
            "semester": self.semester,
            "study_program": self.study_program,
            "is_pbl": bool(self.is_pbl),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Class(db.Model):
    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("course_id", "name", name="uq_classes_course_name"),)

    id = db.Column(Integer, primary_key=True)
    course_id = db.Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    owner_id = db.Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = db.Column(String(120), nullable=False)
    lecturer = db.Column(String(255), default="")
    created_at = db.Column(DateTime, default=datetime.utcnow)

    course = relationship("Course", backref=db.backref("classes", passive_deletes=True))
    owner = relationship("User", backref="owned_classes")

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "owner_id": self.owner_id,
            "name": self.name,
            "lecturer": self.lecturer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(Integer, primary_key=True)
    course_id = db.Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    key = db.Column(String(60), nullable=False)
    label = db.Column(String(180), nullable=False)
    sort_order = db.Column(Integer, default=0)

    course = relationship("Course", backref=db.backref("categories", passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "key": self.key,
            "label": self.label,
            "sort_order": self.sort_order,
        }


class Component(db.Model):
    __tablename__ = "components"

    id = db.Column(Integer, primary_key=True)
    category_id = db.Column(Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name = db.Column(String(255), nullable=False)
    cpl_pis = db.Column(Text, default="[]")
    weight = db.Column(db.Float, nullable=False)
    sort_order = db.Column(Integer, default=0)

    category = relationship("Category", backref=db.backref("components", passive_deletes=True))

    def get_cpl_pis(self):
        try:
            return json.loads(self.cpl_pis or "[]")
        except (TypeError, ValueError):
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "category_id": self.category_id,
            "name": self.name,
            "cpl_pis": self.get_cpl_pis(),
            "weight": self.weight,
            "sort_order": self.sort_order,
        }


class Criteria(db.Model):
    __tablename__ = "criteria"

    id = db.Column(Integer, primary_key=True)
    component_id = db.Column(Integer, ForeignKey("components.id", ondelete="CASCADE"), nullable=False)
    level = db.Column(Integer, nullable=False)
    label = db.Column(String(120), nullable=False)
    score_min = db.Column(Integer, nullable=False)
    score_max = db.Column(Integer, nullable=False)
    sort_order = db.Column(Integer, default=0)

    component = relationship("Component", backref=db.backref("criteria", passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "component_id": self.component_id,
            "level": self.level,
            "label": self.label,
            "score_min": self.score_min,
            "score_max": self.score_max,
            "sort_order": self.sort_order,
        }


class CriteriaSubject(db.Model):
    __tablename__ = "criteria_subjects"

    id = db.Column(Integer, primary_key=True)
    criteria_id = db.Column(Integer, ForeignKey("criteria.id", ondelete="CASCADE"), nullable=False)
    subject = db.Column(Text, nullable=False)
    sort_order = db.Column(Integer, default=0)

    criteria = relationship("Criteria", backref=db.backref("subjects", passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "criteria_id": self.criteria_id,
            "subject": self.subject,
            "sort_order": self.sort_order,
        }


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(Integer, primary_key=True)
    class_id = db.Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    row_no = db.Column(Integer, nullable=False)
    nim = db.Column(String(40), default="")
    name = db.Column(String(255), default="")

    klass = relationship("Class", backref=db.backref("students", passive_deletes=True))

    def to_dict(self):
        return {
            "id": self.id,
            "class_id": self.class_id,
            "row_no": self.row_no,
            "nim": self.nim,
            "name": self.name,
        }


class Cpl(db.Model):
    __tablename__ = "cpls"

    id = db.Column(Integer, primary_key=True)
    course_id = db.Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    code = db.Column(String(30), nullable=False)
    description = db.Column(Text, nullable=True)
    proficiency_level = db.Column(Integer, default=3)
    so_codes = db.Column(Text, default="[]")
    sort_order = db.Column(Integer, default=0)

    course = relationship("Course", backref=db.backref("cpls", passive_deletes=True))

    def get_so_codes(self):
        try:
            return json.loads(self.so_codes or "[]")
        except (TypeError, ValueError):
            return []

    def to_dict(self):
        return {
            "id": self.id,
            "course_id": self.course_id,
            "code": self.code,
            "description": self.description,
            "proficiency_level": self.proficiency_level,
            "so_codes": self.get_so_codes(),
            "sort_order": self.sort_order,
        }


class Score(db.Model):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("student_id", "component_id", name="uq_scores"),)

    id = db.Column(Integer, primary_key=True)
    student_id = db.Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    component_id = db.Column(Integer, ForeignKey("components.id", ondelete="CASCADE"), nullable=False)
    score = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "component_id": self.component_id,
            "score": self.score,
        }
