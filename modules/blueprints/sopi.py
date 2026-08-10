"""SO-PI admin endpoints for Tim Kurikulum.

All writes require a logged-in user with role "tim_kurikulum". The SO-PI set
for a study program is stored in the DB (so_pis / performance_indicators) and
read by the course wizard and validation.
"""

from flask import Blueprint, jsonify, render_template, request

from modules.auth import ROLE_TIM_KURIKULUM, api_login_required, current_user, role_required
from modules.models import Pi, ProficiencyLevel, So, db
from modules.so_pi import PROGRAMS, get_pi_by_id, get_so_by_id, get_so_pi, pi_references, so_references

bp = Blueprint("sopi", __name__, url_prefix="/sopi")


def _allowed_programs(user):
    """Programs the logged-in user may manage. A tim_kurikulum user manages exactly one."""
    program = (user.get("study_program") or "").strip()
    if program in PROGRAMS:
        return [program]
    return ["RKS"]  # default


def _require_tim_kurikulum():
    user = current_user()
    if not user:
        return None, None, (jsonify({"error": "authentication required"}), 401)
    if user["role"] != ROLE_TIM_KURIKULUM:
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
@role_required(ROLE_TIM_KURIKULUM)
def index():
    return render_template("sopi.html")


@bp.route("/api/programs")
@api_login_required
def api_sopi_programs():
    _user, allowed, err = _require_tim_kurikulum()
    if err:
        return err
    return jsonify([{"code": p, "label": PROGRAMS[p]} for p in allowed])


@bp.route("/api")
@api_login_required
def api_sopi():
    program = request.args.get("program", "").strip() or "RKS"
    _, allowed, err = _require_tim_kurikulum()
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
    _, allowed, err = _require_tim_kurikulum()
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
    _, allowed, err = _require_tim_kurikulum()
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
    _, allowed, err = _require_tim_kurikulum()
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

    last = Pi.query.filter_by(so_id=so.id).order_by(Pi.sort_order.desc()).first()
    pi = Pi(
        so_id=so.id,
        pi_code=pi_code,
        pi_description=str(payload.get("pi_description", "")).strip(),
        sort_order=(last.sort_order + 1) if last else 0,
    )
    db.session.add(pi)
    db.session.commit()
    return jsonify({"ok": True, "pi": pi.to_dict()})


@bp.route("/api/pi/<int:pi_id>", methods=["PUT", "DELETE"])
@api_login_required
def api_pi(pi_id):
    _, allowed, err = _require_tim_kurikulum()
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
    db.session.commit()
    return jsonify({"ok": True, "pi": pi.to_dict()})


@bp.route("/api/levels", methods=["GET", "PUT"])
@api_login_required
def api_levels():
    if request.method == "GET":
        return jsonify({"proficiency_levels": [p.to_dict() for p in ProficiencyLevel.query.order_by(ProficiencyLevel.level).all()]})

    _, _, err = _require_tim_kurikulum()
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
# Statistics per Prodi & Semester
# -------------------------------------------------------------
from modules.models import Course, Class, Student, Score, Component, Category, Cpl
from modules.helpers import cpl_pis_of, grade_of_score

def get_prodi_semester_statistics(study_program, semester):
    courses = Course.query.filter_by(study_program=study_program, semester=semester).all()
    if not courses:
        return None

    course_ids = [c.id for c in courses]
    classes = Class.query.filter(Class.course_id.in_(course_ids)).all()
    class_ids = [cl.id for cl in classes]

    # Map course components
    components_by_course = {}
    for c in courses:
        comps = []
        for cat in c.categories:
            comps.extend(cat.components)
        components_by_course[c.id] = comps

    # Fetch students and scores
    students = Student.query.filter(Student.class_id.in_(class_ids)).all()
    student_ids = [s.id for s in students]
    scores = Score.query.filter(Score.student_id.in_(student_ids)).all()

    # Map scores by student id
    scores_by_student = {s.id: {} for s in students}
    for sc in scores:
        if sc.student_id in scores_by_student:
            scores_by_student[sc.student_id][sc.component_id] = sc.score

    # Filter actual students
    actual_students = []
    assessed_student_ids = {sc.student_id for sc in scores if sc.score is not None}
    for s in students:
        if (s.name and s.name.strip()) or (s.nim and s.nim.strip()) or (s.id in assessed_student_ids):
            actual_students.append(s)

    class_by_id = {cl.id: cl for cl in classes}
    course_by_id = {c.id: c for c in courses}

    totals_by_course = {c.id: [] for c in courses}
    overall_totals = []
    grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}

    # Track scores for SO averages
    so_scores = {}

    for s in actual_students:
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

        # Compute student total score
        total_score = sum((student_scores.get(co.id) or 0) * (co.weight / 100.0) for co in comps)
        totals_by_course[c.id].append(total_score)
        overall_totals.append(total_score)
        
        # Grade
        g = grade_of_score(total_score)
        grade_dist[g] += 1

        # SO mappings
        for co in comps:
            score_val = student_scores.get(co.id)
            if score_val is not None:
                for mapping in cpl_pis_of(co):
                    so_code = mapping.get("so")
                    if so_code:
                        so_scores.setdefault(so_code, []).append(score_val)

    # Calculate average and pass rate per course
    course_stats = []
    for c in courses:
        final_scores = totals_by_course[c.id]
        avg_score = round(sum(final_scores) / len(final_scores), 2) if final_scores else None
        
        passed = sum(1 for s in final_scores if grade_of_score(s) in ("A", "B", "C", "D"))
        pass_rate = round(passed / len(final_scores) * 100, 2) if final_scores else 0
        
        c_classes = [cl for cl in classes if cl.course_id == c.id]
        
        course_stats.append({
            "course_code": c.course_code,
            "course_name": c.course_name,
            "sks": c.sks,
            "class_count": len(c_classes),
            "avg_score": avg_score,
            "pass_rate": pass_rate
        })

    # SO averages (Get all master SOs for the study program, show None if not assessed)
    so_stats = []
    all_sos = So.query.filter_by(study_program=study_program).order_by(So.sort_order, So.so_code).all()
    for s_item in all_sos:
        code = s_item.so_code
        vals = so_scores.get(code, [])
        avg = round(sum(vals) / len(vals), 2) if vals else None
        so_stats.append({
            "so_code": code,
            "avg_score": avg
        })

    return {
        "total_courses": len(courses),
        "total_classes": len(classes),
        "total_students": len(actual_students),
        "total_assessed": len(assessed_student_ids),
        "grade_distribution": grade_dist,
        "so_stats": so_stats,
        "course_stats": course_stats
    }


@bp.route("/statistics")
@role_required(ROLE_TIM_KURIKULUM)
def statistics():
    return render_template("statistics.html")


@bp.route("/api/statistics/semesters")
@api_login_required
def api_statistics_semesters():
    user = current_user()
    if not user or user["role"] != ROLE_TIM_KURIKULUM:
        return jsonify({"error": "not authorized"}), 403
    
    study_program = user.get("study_program")
    if not study_program:
        return jsonify([])
        
    semesters = (
        db.session.query(Course.semester)
        .filter_by(study_program=study_program)
        .distinct()
        .all()
    )
    sem_list = [s[0] for s in semesters if s[0] and s[0].strip()]
    sem_list.sort(reverse=True)
    return jsonify(sem_list)


@bp.route("/api/statistics")
@api_login_required
def api_statistics():
    user = current_user()
    if not user or user["role"] != ROLE_TIM_KURIKULUM:
        return jsonify({"error": "not authorized"}), 403
        
    study_program = user.get("study_program")
    if not study_program:
        return jsonify({"error": "user has no study program"}), 400
        
    semester = request.args.get("semester", "").strip()
    if not semester:
        # Default to the latest semester
        latest_course = (
            Course.query.filter_by(study_program=study_program)
            .order_by(Course.created_at.desc())
            .first()
        )
        if latest_course:
            semester = latest_course.semester
            
    if not semester:
        all_sos = So.query.filter_by(study_program=study_program).order_by(So.sort_order, So.so_code).all()
        so_stats = [{"so_code": s.so_code, "avg_score": None} for s in all_sos]
        return jsonify({
            "total_courses": 0,
            "total_classes": 0,
            "total_students": 0,
            "total_assessed": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
            "so_stats": so_stats,
            "course_stats": [],
            "semester": ""
        })
        
    stats = get_prodi_semester_statistics(study_program, semester)
    if stats is None:
        all_sos = So.query.filter_by(study_program=study_program).order_by(So.sort_order, So.so_code).all()
        so_stats = [{"so_code": s.so_code, "avg_score": None} for s in all_sos]
        return jsonify({
            "total_courses": 0,
            "total_classes": 0,
            "total_students": 0,
            "total_assessed": 0,
            "grade_distribution": {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0},
            "so_stats": so_stats,
            "course_stats": [],
            "semester": semester
        })
        
    stats["semester"] = semester
    stats["study_program"] = study_program
    return jsonify(stats)
