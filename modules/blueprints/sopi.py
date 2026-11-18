"""SO-PI and Statistics endpoints for Admin and KPS.

All writes require a logged-in user with role "admin" or "kps".
Admin manages all study programs; KPS manages only their own study program.
"""

from flask import Blueprint, jsonify, render_template, request

from modules.auth import ROLE_ADMIN, ROLE_KPS, api_login_required, current_user, role_required
from modules.helpers import angkatan_from_nim, cpl_pis_of, grade_of_score
from modules.models import Category, Class, Component, Course, Cpl, Pi, ProficiencyLevel, Score, So, Student, db
from modules.permissions import is_admin, is_kps, user_program
from modules.so_pi import PROGRAMS, get_pi_by_id, get_so_by_id, get_so_pi, pi_references, so_references

bp = Blueprint("sopi", __name__, url_prefix="/sopi")


def _allowed_programs(user):
    """Programs the logged-in user may manage."""
    if is_admin(user):
        return list(PROGRAMS.keys())
    if is_kps(user):
        prog = user_program(user)
        return [prog] if prog in PROGRAMS else ["RKS"]
    return []


def _require_admin_or_kps():
    user = current_user()
    if not user:
        return None, None, (jsonify({"error": "authentication required"}), 401)
    if not (is_admin(user) or is_kps(user)):
        return None, None, (jsonify({"error": "not authorized"}), 403)
    allowed = _allowed_programs(user)
    return user, allowed, None


def _check_program(allowed, program):
    """Return an error tuple if the program is not allowed, else None."""
    if program not in allowed:
        return jsonify({"error": f"tidak berwenang mengelola prodi '{program}'"}), 403
    return None


@bp.route("")
@bp.route("/")
@role_required(ROLE_ADMIN, ROLE_KPS)
def index():
    return render_template("sopi.html")


@bp.route("/api/programs")
@api_login_required
def api_sopi_programs():
    _user, allowed, err = _require_admin_or_kps()
    if err:
        return err
    return jsonify([{"code": p, "label": PROGRAMS[p]} for p in allowed])


@bp.route("/api")
@api_login_required
def api_sopi():
    program = request.args.get("program", "").strip() or "RKS"
    _, allowed, err = _require_admin_or_kps()
    if err:
        return err
    err = _check_program(allowed, program)
    if err:
        return err
    data = get_so_pi(program)
    if data is None:
        return jsonify(
            {
                "study_program": program,
                "student_outcome": [],
                "proficiency_levels": [],
            }
        )
    return jsonify(data)


@bp.route("/api/so", methods=["POST"])
@api_login_required
def api_create_so():
    _, allowed, err = _require_admin_or_kps()
    if err:
        return err

    payload = request.json or {}
    program = str(payload.get("study_program", "")).strip()
    so_code = str(payload.get("so_code", "")).strip()
    description = str(payload.get("so_description", "")).strip()
    if not program:
        return jsonify({"error": "study_program is required"}), 400
    err = _check_program(allowed, program)
    if err:
        return err
    if not so_code:
        return jsonify({"error": "so_code is required"}), 400
    if So.query.filter_by(study_program=program, so_code=so_code).first():
        return jsonify({"error": f"SO '{so_code}' sudah ada untuk prodi ini"}), 400

    last = (
        So.query.filter_by(study_program=program)
        .order_by(So.sort_order.desc())
        .first()
    )
    so = So(
        study_program=program,
        so_code=so_code,
        so_description=description,
        sort_order=(last.sort_order + 1) if last else 0,
    )
    db.session.add(so)
    db.session.commit()
    return jsonify({"ok": True, "so": so.to_dict()})


@bp.route("/api/so/<int:so_id>", methods=["PUT", "DELETE"])
@api_login_required
def api_so(so_id):
    _, allowed, err = _require_admin_or_kps()
    if err:
        return err

    so = get_so_by_id(so_id)
    if not so:
        return jsonify({"error": "SO not found"}), 404
    err = _check_program(allowed, so.study_program)
    if err:
        return err

    if request.method == "DELETE":
        refs = so_references(so.study_program, so.so_code)
        if refs:
            return jsonify(
                {"error": f"SO '{so.so_code}' masih dipakai oleh kursus: {', '.join(refs)}"}
            ), 400
        pi_refs = []
        for pi in so.performance_indicators:
            pi_refs += pi_references(so.study_program, so.so_code, pi.pi_code)
        if pi_refs:
            return jsonify(
                {"error": f"PI dari SO '{so.so_code}' masih dipakai oleh kursus: {', '.join(sorted(set(pi_refs)))}"}
            ), 400
        db.session.delete(so)
        db.session.commit()
        return jsonify({"ok": True})

    payload = request.json or {}
    so_code = str(payload.get("so_code", "")).strip()
    if not so_code:
        return jsonify({"error": "so_code is required"}), 400
    dup = So.query.filter(
        So.study_program == so.study_program,
        So.so_code == so_code,
        So.id != so_id,
    ).first()
    if dup:
        return jsonify({"error": f"SO '{so_code}' sudah ada untuk prodi ini"}), 400

    so.so_code = so_code
    if "so_description" in payload:
        so.so_description = str(payload.get("so_description", "")).strip()
    db.session.commit()
    return jsonify({"ok": True, "so": so.to_dict()})


@bp.route("/api/pi", methods=["POST"])
@api_login_required
def api_create_pi():
    _, allowed, err = _require_admin_or_kps()
    if err:
        return err

    payload = request.json or {}
    so = get_so_by_id(payload.get("so_id"))
    if not so:
        return jsonify({"error": "SO not found"}), 404
    err = _check_program(allowed, so.study_program)
    if err:
        return err
    pi_code = str(payload.get("pi_code", "")).strip()
    if not pi_code:
        return jsonify({"error": "pi_code is required"}), 400
    if Pi.query.filter_by(so_id=so.id, pi_code=pi_code).first():
        return jsonify({"error": f"PI '{pi_code}' sudah ada pada SO ini"}), 400
    try:
        proficiency_level = int(payload.get("proficiency_level", 3) or 3)
    except (TypeError, ValueError):
        return jsonify({"error": "proficiency_level harus angka 1-5"}), 400
    if proficiency_level not in (1, 2, 3, 4, 5):
        return jsonify({"error": "proficiency_level harus antara 1 dan 5"}), 400

    last = Pi.query.filter_by(so_id=so.id).order_by(Pi.sort_order.desc()).first()
    pi = Pi(
        so_id=so.id,
        pi_code=pi_code,
        pi_description=str(payload.get("pi_description", "")).strip(),
        proficiency_level=proficiency_level,
        sort_order=(last.sort_order + 1) if last else 0,
    )
    db.session.add(pi)
    db.session.commit()
    return jsonify({"ok": True, "pi": pi.to_dict()})


@bp.route("/api/pi/<int:pi_id>", methods=["PUT", "DELETE"])
@api_login_required
def api_pi(pi_id):
    _, allowed, err = _require_admin_or_kps()
    if err:
        return err

    pi = get_pi_by_id(pi_id)
    if not pi:
        return jsonify({"error": "PI not found"}), 404
    err = _check_program(allowed, pi.so.study_program)
    if err:
        return err

    if request.method == "DELETE":
        refs = pi_references(pi.so.study_program, pi.so.so_code, pi.pi_code)
        if refs:
            return jsonify(
                {"error": f"PI '{pi.pi_code}' masih dipakai oleh kursus: {', '.join(refs)}"}
            ), 400
        db.session.delete(pi)
        db.session.commit()
        return jsonify({"ok": True})

    payload = request.json or {}
    pi_code = str(payload.get("pi_code", "")).strip()
    if not pi_code:
        return jsonify({"error": "pi_code is required"}), 400
    dup = Pi.query.filter(Pi.so_id == pi.so_id, Pi.pi_code == pi_code, Pi.id != pi_id).first()
    if dup:
        return jsonify({"error": f"PI '{pi_code}' sudah ada pada SO ini"}), 400

    pi.pi_code = pi_code
    pi.pi_description = str(payload.get("pi_description", pi.pi_description)).strip()
    if "proficiency_level" in payload:
        try:
            lvl = int(payload.get("proficiency_level") or 3)
        except (TypeError, ValueError):
            return jsonify({"error": "proficiency_level harus angka 1-5"}), 400
        if lvl not in (1, 2, 3, 4, 5):
            return jsonify({"error": "proficiency_level harus antara 1 dan 5"}), 400
        pi.proficiency_level = lvl
    db.session.commit()
    return jsonify({"ok": True, "pi": pi.to_dict()})


@bp.route("/api/levels", methods=["GET", "PUT"])
@api_login_required
def api_levels():
    if request.method == "GET":
        return jsonify({"proficiency_levels": [p.to_dict() for p in ProficiencyLevel.query.order_by(ProficiencyLevel.level).all()]})

    _, _, err = _require_admin_or_kps()
    if err:
        return err

    payload = request.json or {}
    levels = payload.get("proficiency_levels") or []
    if not levels:
        return jsonify({"error": "proficiency_levels is required"}), 400
    seen = set()
    for item in levels:
        try:
            level = int(item.get("level"))
        except (TypeError, ValueError):
            return jsonify({"error": "level harus angka"}), 400
        if level in seen:
            return jsonify({"error": f"level {level} duplikat"}), 400
        seen.add(level)
        label = str(item.get("label", "")).strip()
        if not label:
            return jsonify({"error": f"label level {level} kosong"}), 400
        row = ProficiencyLevel.query.filter_by(level=level).first()
        if row:
            row.label = label
    db.session.commit()
    return jsonify({"ok": True})


# -------------------------------------------------------------
# Statistics per Prodi / Angkatan / Tahun Ajaran
# -------------------------------------------------------------

def _master_so_codes(study_program):
    """Return ordered list of SO codes for a study program (or all programs if 'all')."""
    if study_program and study_program != "all":
        rows = So.query.filter_by(study_program=study_program).order_by(So.sort_order, So.so_code).all()
        return [s.so_code for s in rows]
    rows = So.query.order_by(So.sort_order, So.so_code).all()
    seen = set()
    codes = []
    for s in rows:
        if s.so_code not in seen:
            seen.add(s.so_code)
            codes.append(s.so_code)
    return codes


def _sort_group_key(label):
    if label == "Tidak diketahui":
        return (1, label)
    return (0, label)


def get_statistics(study_program="all", mode="angkatan", value="all", semester=None):
    """Compute curriculum statistics filtered by study_program, mode (angkatan|tahun_ajaran), value, and optional semester."""
    q = Course.query
    if study_program and study_program != "all":
        q = q.filter_by(study_program=study_program)
    if semester:
        q = q.filter_by(semester=semester)
    courses = q.all()

    so_codes = _master_so_codes(study_program)
    if not courses:
        return {
            "total_courses": 0,
            "total_classes": 0,
            "total_students": 0,
            "total_assessed": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
            "so_stats": [{"so_code": code, "avg_score": None} for code in so_codes],
            "course_stats": [],
            "comparison": [],
        }

    course_ids = [c.id for c in courses]
    all_classes = Class.query.filter(Class.course_id.in_(course_ids)).all()
    all_class_ids = [cl.id for cl in all_classes]

    components_by_course = {}
    for c in courses:
        comps = []
        for cat in c.categories:
            comps.extend(cat.components)
        components_by_course[c.id] = comps

    all_students = Student.query.filter(Student.class_id.in_(all_class_ids)).all() if all_class_ids else []
    student_ids = [s.id for s in all_students]
    scores = Score.query.filter(Score.student_id.in_(student_ids)).all() if student_ids else []

    scores_by_student = {s.id: {} for s in all_students}
    for sc in scores:
        if sc.student_id in scores_by_student:
            scores_by_student[sc.student_id][sc.component_id] = sc.score

    assessed_student_ids = {sc.student_id for sc in scores if sc.score is not None}
    actual_students = [
        s for s in all_students
        if (s.name and s.name.strip()) or (s.nim and s.nim.strip()) or (s.id in assessed_student_ids)
    ]

    class_by_id = {cl.id: cl for cl in all_classes}
    course_by_id = {c.id: c for c in courses}

    # Build comparison across all cohorts / academic years in the scoped study_program
    comparison_groups = {}
    for s in actual_students:
        cl = class_by_id.get(s.class_id)
        if not cl:
            continue
        c = course_by_id.get(cl.course_id)
        if not c:
            continue
        grp_label = (
            angkatan_from_nim(s.nim)
            if mode == "angkatan"
            else ((cl.academic_year or "").strip() or "Tidak diketahui")
        )
        grp = comparison_groups.setdefault(grp_label, {"totals": [], "students": 0, "assessed": 0})
        grp["students"] += 1
        student_scores = scores_by_student.get(s.id, {})
        if s.id in assessed_student_ids and student_scores:
            comps = components_by_course.get(c.id, [])
            total_score = sum((student_scores.get(co.id) or 0) * (co.weight / 100.0) for co in comps)
            grp["totals"].append(total_score)
            grp["assessed"] += 1

    comparison = [
        {
            "label": label,
            "avg_score": round(sum(g["totals"]) / len(g["totals"]), 2) if g["totals"] else None,
            "student_count": g["students"],
            "assessed_count": g["assessed"],
        }
        for label, g in sorted(comparison_groups.items(), key=lambda kv: _sort_group_key(kv[0]))
    ]

    # Apply value filter for main stats
    if mode == "tahun_ajaran" and value and value != "all":
        filtered_classes = [cl for cl in all_classes if (cl.academic_year or "").strip() == value]
        filtered_class_ids = {cl.id for cl in filtered_classes}
        filtered_students = [s for s in actual_students if s.class_id in filtered_class_ids]
    elif mode == "angkatan" and value and value != "all":
        filtered_students = [s for s in actual_students if angkatan_from_nim(s.nim) == value]
        filtered_class_ids = {s.class_id for s in filtered_students}
        filtered_classes = [cl for cl in all_classes if cl.id in filtered_class_ids]
    else:
        filtered_classes = all_classes
        filtered_students = actual_students

    filtered_assessed_ids = {s.id for s in filtered_students if s.id in assessed_student_ids}

    totals_by_course = {c.id: [] for c in courses}
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}
    so_scores = {}

    for s in filtered_students:
        cl = class_by_id.get(s.class_id)
        if not cl:
            continue
        c = course_by_id.get(cl.course_id)
        if not c:
            continue
        comps = components_by_course.get(c.id, [])
        student_scores = scores_by_student.get(s.id, {})
        if not student_scores:
            continue

        total_score = sum((student_scores.get(co.id) or 0) * (co.weight / 100.0) for co in comps)
        totals_by_course[c.id].append(total_score)
        grade_dist[grade_of_score(total_score)] += 1

        for co in comps:
            score_val = student_scores.get(co.id)
            if score_val is not None:
                for mapping in cpl_pis_of(co):
                    so_code = mapping.get("so")
                    if so_code:
                        so_scores.setdefault(so_code, []).append(score_val)

    course_stats = []
    for c in courses:
        final_scores = totals_by_course[c.id]
        avg_score = round(sum(final_scores) / len(final_scores), 2) if final_scores else None
        passed = sum(1 for sc in final_scores if grade_of_score(sc) in ("A", "B", "C", "D"))
        pass_rate = round(passed / len(final_scores) * 100, 2) if final_scores else 0
        c_classes = [cl for cl in filtered_classes if cl.course_id == c.id]
        course_stats.append({
            "course_code": c.course_code,
            "course_name": c.course_name,
            "study_program": c.study_program,
            "sks": c.sks,
            "class_count": len(c_classes),
            "avg_score": avg_score,
            "pass_rate": pass_rate,
        })

    # Include any extra SO codes present in scores even if not in master list
    all_so_codes = list(so_codes)
    for code in sorted(so_scores.keys()):
        if code not in all_so_codes:
            all_so_codes.append(code)

    so_stats = []
    for code in all_so_codes:
        vals = so_scores.get(code, [])
        avg = round(sum(vals) / len(vals), 2) if vals else None
        so_stats.append({"so_code": code, "avg_score": avg})

    return {
        "total_courses": len(courses),
        "total_classes": len(filtered_classes),
        "total_students": len(filtered_students),
        "total_assessed": len(filtered_assessed_ids),
        "grade_distribution": grade_dist,
        "so_stats": so_stats,
        "course_stats": course_stats,
        "comparison": comparison,
    }


def get_prodi_semester_statistics(study_program, semester):
    """Backward-compatible wrapper for semester-based statistics."""
    courses = Course.query.filter_by(study_program=study_program, semester=semester).all()
    if not courses:
        return None
    return get_statistics(study_program=study_program, semester=semester)


@bp.route("/statistics")
@role_required(ROLE_ADMIN, ROLE_KPS)
def statistics():
    return render_template("statistics.html")


@bp.route("/api/statistics/filters")
@api_login_required
def api_statistics_filters():
    user, _, err = _require_admin_or_kps()
    if err:
        return err

    if is_kps(user):
        program = user_program(user)
        programs = [{"code": program, "label": PROGRAMS.get(program, program)}]
    else:
        program = request.args.get("study_program", "all").strip() or "all"
        programs = [{"code": k, "label": v} for k, v in PROGRAMS.items()]

    q = Course.query
    if program != "all":
        q = q.filter_by(study_program=program)
    course_ids = [c.id for c in q.all()]

    if course_ids:
        classes = Class.query.filter(Class.course_id.in_(course_ids)).all()
        class_ids = [cl.id for cl in classes]
        academic_years = sorted(
            {(cl.academic_year or "").strip() for cl in classes if (cl.academic_year or "").strip()},
            reverse=True,
        )
        students = Student.query.filter(Student.class_id.in_(class_ids)).all() if class_ids else []
        actual_students = [
            s for s in students
            if (s.nim and s.nim.strip()) or (s.name and s.name.strip())
        ]
        angkatans = sorted(
            {angkatan_from_nim(s.nim) for s in actual_students},
            key=_sort_group_key,
        )
    else:
        academic_years = []
        angkatans = []

    return jsonify({
        "angkatans": angkatans,
        "academic_years": academic_years,
        "programs": programs,
        "is_admin": is_admin(user),
        "default_program": "all" if is_admin(user) else user_program(user),
    })


@bp.route("/api/statistics/semesters")
@api_login_required
def api_statistics_semesters():
    user, _, err = _require_admin_or_kps()
    if err:
        return err

    q = db.session.query(Course.semester)
    if is_kps(user):
        q = q.filter(Course.study_program == user_program(user))
    semesters = q.distinct().all()
    sem_list = [s[0] for s in semesters if s[0] and s[0].strip()]
    sem_list.sort(reverse=True)
    return jsonify(sem_list)


@bp.route("/api/statistics")
@api_login_required
def api_statistics():
    user, _, err = _require_admin_or_kps()
    if err:
        return err

    if is_kps(user):
        study_program = user_program(user)
    else:
        study_program = request.args.get("study_program", "all").strip() or "all"
        if study_program != "all" and study_program not in PROGRAMS:
            return jsonify({"error": f"prodi tidak dikenal: {study_program}"}), 400

    mode = request.args.get("mode", "angkatan").strip() or "angkatan"
    if mode not in ("angkatan", "tahun_ajaran"):
        return jsonify({"error": "mode harus 'angkatan' atau 'tahun_ajaran'"}), 400

    value = request.args.get("value", "all").strip() or "all"
    semester = request.args.get("semester", "").strip() or None

    stats = get_statistics(
        study_program=study_program,
        mode=mode,
        value=value,
        semester=semester,
    )
    stats["mode"] = mode
    stats["value"] = value
    stats["study_program"] = study_program
    if semester:
        stats["semester"] = semester
    return jsonify(stats)
