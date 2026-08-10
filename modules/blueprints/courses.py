import json

from flask import Blueprint, jsonify, render_template, request, send_file

from modules.auth import api_login_required, current_user, login_required
from modules.data import _get_class_data, _get_course_structure, user_owns_class, user_owns_course
from modules.seeder import seed_course_data
from modules.excel import build_sid_workbook, build_workbook, load_workbook_bytes, workbook_bytes
from modules.helpers import cpl_pis_of
from modules.models import Category, Class, Component, Course, Score, Student, Cpl, Criteria, CriteriaSubject, User, db
from modules.portfolio import compute_portfolio

bp = Blueprint("courses", __name__)

MAX_STUDENTS = 40


def _courses_for_user(user, q_param="", semester="", page=1, per_page=10):
    q = Course.query
    if user["role"] == "tim_kurikulum":
        program = (user.get("study_program") or "").strip() or "RKS"
        q = q.filter(Course.study_program == program)
    else:
        accessible_ids = {
            c.id for c in Course.query.all()
            if c.owner_id == user["id"] or user["id"] in c.get_shared_with()
        }
        q = Course.query.filter(Course.id.in_(accessible_ids))

    if q_param:
        q = q.filter(
            db.or_(
                Course.course_code.ilike(f"%{q_param}%"),
                Course.course_name.ilike(f"%{q_param}%")
            )
        )

    if semester:
        q = q.filter(Course.semester == semester)

    total_count = q.count()
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    page = max(1, min(total_pages, page))

    rows = q.order_by(Course.id.desc()).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for c in rows:
        result.append(
            {
                "id": c.id,
                "course_code": c.course_code,
                "course_name": c.course_name,
                "sks": c.sks,
                "semester": c.semester,
                "study_program": c.study_program,
                "component_count": Component.query.join(Category)
                .filter(Category.course_id == c.id).count(),
                "class_count": Class.query.filter_by(course_id=c.id).count(),
                "owner_name": c.owner.name if c.owner else "-",
                "can_share": user["role"] == "tim_kurikulum" or c.owner_id == user["id"],
                "shared": user["id"] in c.get_shared_with(),
            }
        )
    return {
        "courses": result,
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page
    }


# ------------------------- pages -------------------------

@bp.route("/courses/<int:course_id>/classes")
@login_required
def manage_classes_page(course_id):
    user = current_user()
    if not user_owns_course(user, course_id):
        return jsonify({"error": "not authorized"}), 403
    course = db.session.get(Course, course_id)
    can_manage = can_manage_course(user, course)
    return render_template("manage_classes.html", course_id=course_id, can_manage=can_manage)


@bp.route("/assess/<int:class_id>")
@login_required
def assess_page(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    return render_template("assess.html", class_id=class_id)


@bp.route("/portfolio/<int:class_id>")
@login_required
def portfolio_page(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    return render_template("portfolio.html", class_id=class_id)


@bp.route("/portfolio/course/<int:course_id>")
@login_required
def portfolio_course_page(course_id):
    user = current_user()
    if not user_owns_course(user, course_id):
        return jsonify({"error": "not authorized"}), 403
    return render_template("portfolio_course.html", course_id=course_id)


# ------------------------- course API -------------------------

@bp.route("/api/courses")
@api_login_required
def api_courses():
    user = current_user()
    q_param = request.args.get("q", "").strip()
    semester = request.args.get("semester", "").strip()
    page = int(request.args.get("page", 1))
    return jsonify(_courses_for_user(user, q_param, semester, page))


@bp.route("/api/semesters")
@api_login_required
def api_semesters():
    user = current_user()
    if user["role"] == "tim_kurikulum":
        program = (user.get("study_program") or "").strip() or "RKS"
        semesters = db.session.query(Course.semester).filter(Course.study_program == program).distinct().all()
    else:
        accessible_ids = {
            c.id for c in Course.query.all()
            if c.owner_id == user["id"] or user["id"] in c.get_shared_with()
        }
        semesters = db.session.query(Course.semester).filter(Course.id.in_(accessible_ids)).distinct().all()

    sem_list = [s[0] for s in semesters if s[0] and s[0].strip()]
    sem_list.sort(reverse=True)
    return jsonify(sem_list)


@bp.route("/api/courses/create", methods=["POST"])
@api_login_required
def api_create_course():
    user = current_user()
    from modules.rubric_builder import build_rubric_from_wizard

    payload = request.json or {}
    try:
        data = build_rubric_from_wizard(payload)
        course_id = seed_course_data(data, owner_id=user["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "course_id": course_id, "course_code": data["course_code"]})


@bp.route("/api/courses/upload", methods=["POST"])
@api_login_required
def api_upload_course():
    user = current_user()
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "no file uploaded"}), 400
    try:
        raw = file.read()
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        return jsonify({"error": f"invalid JSON: {e}"}), 400
    try:
        course_id = seed_course_data(data, owner_id=user["id"])
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "course_id": course_id, "course_code": data["course_code"]})


@bp.route("/api/course-template")
def api_course_template():
    from config import DATA_FILE

    return send_file(
        DATA_FILE,
        as_attachment=True,
        download_name="course_template.json",
        mimetype="application/json",
    )


@bp.route("/api/so-pi")
def api_so_pi():
    from modules.so_pi import get_so_pi

    program = request.args.get("program", "").strip() or "RKS"
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


@bp.route("/api/programs")
def api_programs():
    # Program studi Jurusan Teknik Informatika, Politeknik Negeri Batam
    from modules.so_pi import PROGRAMS

    return jsonify([{"code": code, "label": label} for code, label in PROGRAMS.items()])


@bp.route("/api/dashboard")
@api_login_required
def api_dashboard():
    user = current_user()
    if user["role"] == "tim_kurikulum":
        program = (user.get("study_program") or "").strip() or "RKS"
        course_ids = [c.id for c in Course.query.filter_by(study_program=program).all()]
        course_count = len(course_ids)
        if course_ids:
            class_q = Class.query.filter(Class.course_id.in_(course_ids))
            class_ids = [cl.id for cl in class_q.all()]
            class_count = len(class_ids)
            if class_ids:
                student_count = Student.query.filter(
                    Student.class_id.in_(class_ids),
                    db.func.trim(Student.nim) != "",
                    db.func.trim(Student.name) != "",
                ).count()
                assessed_count = db.session.query(Score.student_id).join(Student).filter(
                    Student.class_id.in_(class_ids)
                ).distinct().count()
                total_scores = Score.query.join(Student).filter(
                    Student.class_id.in_(class_ids)
                ).count()
            else:
                student_count = 0
                assessed_count = 0
                total_scores = 0
        else:
            class_count = 0
            student_count = 0
            assessed_count = 0
            total_scores = 0
    else:
        accessible_courses = [
            c.id for c in Course.query.all()
            if c.owner_id == user["id"] or user["id"] in c.get_shared_with()
        ]
        course_count = len(accessible_courses)

        classes_q = Class.query.filter(
            (Class.owner_id == user["id"]) | (Class.course_id.in_(accessible_courses))
        ) if accessible_courses else Class.query.filter_by(owner_id=user["id"])

        class_count = classes_q.count()
        user_class_ids = [cl.id for cl in classes_q.all()]
        
        if user_class_ids:
            student_count = Student.query.filter(
                Student.class_id.in_(user_class_ids),
                db.func.trim(Student.nim) != "",
                db.func.trim(Student.name) != ""
            ).count()
            
            assessed_count = db.session.query(Score.student_id).join(Student).filter(
                Student.class_id.in_(user_class_ids)
            ).distinct().count()
            
            total_scores = Score.query.join(Student).filter(
                Student.class_id.in_(user_class_ids)
            ).count()
        else:
            student_count = 0
            assessed_count = 0
            total_scores = 0
    return jsonify(
        {
            "course_count": course_count,
            "class_count": class_count,
            "student_count": student_count,
            "assessed_count": assessed_count,
            "total_scores": total_scores,
        }
    )


def check_course_editable(course_id):
    class_ids = [c.id for c in Class.query.filter_by(course_id=course_id).all()]
    if not class_ids:
        return True, ""
        
    has_filled_student = Student.query.filter(
        Student.class_id.in_(class_ids),
        (
            (Student.nim.isnot(None) & (db.func.trim(Student.nim) != "")) |
            (Student.name.isnot(None) & (db.func.trim(Student.name) != ""))
        )
    ).first()
    if has_filled_student:
        return False, "Rubrik tidak dapat diedit karena sudah ada data mahasiswa yang diisi di kelas."
        
    has_scores = Score.query.join(Student).filter(Student.class_id.in_(class_ids)).first()
    if has_scores:
        return False, "Rubrik tidak dapat diedit karena sudah ada nilai mahasiswa yang dimasukkan."
        
    return True, ""


def update_course_rubric(course, data):
    course.course_code = data["course_code"]
    course.course_name = data["course_name"]
    course.sks = data.get("sks", 0)
    course.semester = data.get("semester", "")
    course.study_program = data.get("study_program", "")
    course.is_pbl = bool(data.get("is_pbl"))
    course.raw_json = json.dumps(data, ensure_ascii=False)

    Cpl.query.filter_by(course_id=course.id).delete()
    Category.query.filter_by(course_id=course.id).delete()
    
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


@bp.route("/api/courses/<int:course_id>/editable", methods=["GET"])
@api_login_required
def api_course_editable(course_id):
    user = current_user()
    if not user_owns_course(user, course_id):
        return jsonify({"error": "not authorized"}), 403
    
    editable, reason = check_course_editable(course_id)
    return jsonify({"editable": editable, "error": reason})


@bp.route("/api/courses/<int:course_id>", methods=["GET", "PUT", "DELETE"])
@api_login_required
def api_course(course_id):
    user = current_user()
    if request.method == "GET":
        if not user_owns_course(user, course_id):
            return jsonify({"error": "not authorized"}), 403
        structure = _get_course_structure(course_id)
        if not structure:
            return jsonify({"error": "course not found"}), 404
        return jsonify(structure)
    if request.method == "DELETE":
        course = db.session.get(Course, course_id)
        if not can_manage_course(user, course):
            return jsonify({"error": "not authorized"}), 403
        if course:
            db.session.delete(course)
            db.session.commit()
        return jsonify({"ok": True})
    if request.method == "PUT":
        course = db.session.get(Course, course_id)
        if not can_manage_course(user, course):
            return jsonify({"error": "not authorized"}), 403
        if not course:
            return jsonify({"error": "course not found"}), 404
            
        editable, reason = check_course_editable(course_id)
        if not editable:
            return jsonify({"error": reason}), 400
            
        payload = request.json or {}
        from modules.rubric_builder import build_rubric_from_wizard
        
        try:
            data = build_rubric_from_wizard(payload)
            update_course_rubric(course, data)
            db.session.commit()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
            
        return jsonify({"ok": True, "course_code": course.course_code})


def can_manage_course(user, course):
    """Whether the user may edit/delete/share a course (owner or tim_kurikulum of the program)."""
    if not course:
        return False
    if user["role"] == "tim_kurikulum":
        program = (user.get("study_program") or "").strip() or "RKS"
        return course.study_program == program
    return course.owner_id == user["id"]


def can_manage_class(user, class_id):
    """Whether the user may edit/delete a class (owner or tim_kurikulum of its course)."""
    klass = db.session.get(Class, class_id)
    if not klass or not klass.course:
        return False
    return can_manage_course(user, klass.course)


@bp.route("/api/courses/<int:course_id>/share", methods=["PUT"])
@api_login_required
def api_course_share(course_id):
    user = current_user()
    course = db.session.get(Course, course_id)
    if not course:
        return jsonify({"error": "course not found"}), 404
    if not can_manage_course(user, course):
        return jsonify({"error": "not authorized"}), 403

    payload = request.json or {}
    user_ids = payload.get("user_ids")
    if not isinstance(user_ids, list):
        return jsonify({"error": "user_ids must be a list"}), 400
    if any(not isinstance(i, int) for i in user_ids):
        return jsonify({"error": "user_ids must be integers"}), 400

    user_ids = list(dict.fromkeys(user_ids))
    existing_ids = {u[0] for u in db.session.query(User.id).filter(User.id.in_(user_ids)).all()}
    invalid = [i for i in user_ids if i not in existing_ids]
    if invalid:
        return jsonify({"error": f"user(s) not found: {', '.join(map(str, invalid))}"}), 400

    course.shared_with = json.dumps(user_ids, ensure_ascii=False)
    db.session.commit()
    return jsonify({"ok": True, "shared_with": course.get_shared_with()})


@bp.route("/api/courses/<int:course_id>/classes", methods=["GET", "POST"])
@api_login_required
def api_classes(course_id):
    user = current_user()
    if request.method == "GET":
        if not user_owns_course(user, course_id):
            return jsonify({"error": "not authorized"}), 403
        structure = _get_course_structure(course_id)
        if not structure:
            return jsonify({"error": "course not found"}), 404
        return jsonify({"course": structure["course"], "classes": structure["classes"]})
    if request.method == "POST":
        course = db.session.get(Course, course_id)
        if not can_manage_course(user, course):
            return jsonify({"error": "not authorized"}), 403
        payload = request.json or {}
        name = payload.get("name", "").strip()
        lecturer = payload.get("lecturer", "").strip()
        if not name:
            return jsonify({"error": "class name is required"}), 400
        existing = Class.query.filter_by(course_id=course_id, name=name).first()
        if existing:
            return jsonify({"error": f"class '{name}' already exists"}), 400
        klass = Class(course_id=course_id, owner_id=user["id"], name=name, lecturer=lecturer)
        db.session.add(klass)
        db.session.flush()
        for n in range(1, MAX_STUDENTS + 1):
            db.session.add(Student(class_id=klass.id, row_no=n, nim="", name=""))
        db.session.commit()
        return jsonify({"ok": True, "class_id": klass.id})


# ------------------------- class API -------------------------

@bp.route("/api/classes/<int:class_id>", methods=["GET", "PUT", "DELETE"])
@api_login_required
def api_class(class_id):
    user = current_user()
    if request.method == "GET":
        if not user_owns_class(user, class_id):
            return jsonify({"error": "not authorized"}), 403
        data = _get_class_data(class_id)
        if not data:
            return jsonify({"error": "class not found"}), 404
        return jsonify(data)
    if request.method == "DELETE":
        if not can_manage_class(user, class_id):
            return jsonify({"error": "not authorized"}), 403
        klass = db.session.get(Class, class_id)
        if klass:
            db.session.delete(klass)
            db.session.commit()
        return jsonify({"ok": True})
    if request.method == "PUT":
        if not can_manage_class(user, class_id):
            return jsonify({"error": "not authorized"}), 403
        payload = request.json or {}
        name = payload.get("name", "").strip()
        lecturer = payload.get("lecturer", "").strip()
        if not name:
            return jsonify({"error": "class name is required"}), 400
        klass = db.session.get(Class, class_id)
        if not klass:
            return jsonify({"error": "class not found"}), 404
        existing = Class.query.filter(
            Class.course_id == klass.course_id, Class.name == name, Class.id != class_id
        ).first()
        if existing:
            return jsonify({"error": f"class '{name}' already exists"}), 400
        klass.name = name
        klass.lecturer = lecturer
        db.session.commit()
        return jsonify({"ok": True})


@bp.route("/api/classes/<int:class_id>/save", methods=["POST"])
@api_login_required
def api_save(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    payload = request.json
    klass = db.session.get(Class, class_id)
    if not klass:
        return jsonify({"error": "class not found"}), 404

    student_ids = [s.id for s in Student.query.filter_by(class_id=class_id).all()]
    Score.query.filter(Score.student_id.in_(student_ids)).delete(synchronize_session=False) if student_ids else None

    for entry in payload.get("rows", []):
        student_id = entry.get("student_id")
        nim = entry.get("nim", "")
        name = entry.get("name", "")
        st = db.session.get(Student, student_id)
        if st and st.class_id == class_id:
            st.nim = nim
            st.name = name
        for component_id, score in (entry.get("scores") or {}).items():
            if score in (None, ""):
                continue
            s = max(0.0, min(100.0, float(score)))
            existing = Score.query.filter_by(student_id=student_id, component_id=component_id).first()
            if existing:
                existing.score = s
            else:
                db.session.add(Score(student_id=student_id, component_id=component_id, score=s))
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/classes/<int:class_id>/export")
@api_login_required
def api_export(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    data = _get_class_data(class_id)
    if not data:
        return jsonify({"error": "class not found"}), 404
    wb = build_workbook(data, include_formulas=True)
    filename = f"rubrik_{data['course']['course_code']}_{data['class']['name']}.xlsx"
    return send_file(
        workbook_bytes(wb),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/api/classes/<int:class_id>/export-sid")
@api_login_required
def api_export_sid(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    data = _get_class_data(class_id)
    if not data:
        return jsonify({"error": "class not found"}), 404
    wb = build_sid_workbook(data)
    filename = f"rubrik_sid_{data['course']['course_code']}_{data['class']['name']}.xlsx"
    return send_file(
        workbook_bytes(wb),
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/api/classes/<int:class_id>/import", methods=["POST"])
@api_login_required
def api_import(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "no file uploaded"}), 400
    try:
        wb = load_workbook_bytes(file.read())
    except Exception:
        return jsonify({"error": "invalid excel file"}), 400
    ws = wb.active
    data = _get_class_data(class_id)
    if not data:
        return jsonify({"error": "class not found"}), 404

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 5:
        return jsonify({"error": "file too short, expected header + data rows"}), 400

    header_row = rows[2]
    col_meta = {}  # col -> {codes, name}
    for idx, cell in enumerate(header_row, start=1):
        if cell:
            text = str(cell).strip()
            name = ""
            codes = []
            if "(" in text:
                name = text[: text.index("(")].strip()
                if ")" in text:
                    codes = [cd.strip() for cd in text[text.index("(") + 1 : text.rindex(")")].split(",") if cd.strip()]
            else:
                name = text
            col_meta[idx] = {"codes": codes, "name": name}
    if not any(m["codes"] for m in col_meta.values()) and not any(m["name"] for m in col_meta.values()):
        return jsonify({"error": "no component columns matched (missing code/name header row)"}), 400

    student_by_no = {s["row_no"]: s for s in data["students"]}
    components = data["components"]

    def _raw_code(cd):
        s = str(cd).strip()
        if "-" in s:
            return s.rsplit("-", 1)[1]
        return s

    def match_component(meta, position_index):
        codes = meta["codes"]
        name = meta["name"].strip().lower()

        # The exported sheet always lists components in data["components"] order
        # starting at column 4, so use position as a tie-breaker for ambiguous
        # headers (e.g. ATS & AAS components with the same name + codes).
        positional = components[position_index] if 0 <= position_index < len(components) else None

        best_comp = None
        best_score = -1.0

        for co in components:
            score = 0.0
            co_name = co["name"].strip().lower()

            # 1. Name matching (exact match gets highest priority, substring matches get partial priority)
            if name and co_name:
                if name == co_name:
                    score += 10
                elif name in co_name or co_name in name:
                    score += 5

            # 2. Code matching (exact SO-PI label matching, e.g., CPL1-1a)
            co_so_pi = co.get("so_pi") or []
            has_code_match = False
            for cd in codes:
                if cd in co_so_pi:
                    has_code_match = True
                    break

            if has_code_match:
                score += 4
            else:
                # 3. Raw PI code matching fallback (e.g., matching "1a" in CPL-PI mapping)
                co_pis = [m.get("pi") for m in co.get("cpl_pis") or [] if m.get("pi")]
                has_raw_match = False
                for cd in codes:
                    raw = _raw_code(cd)
                    if raw in co_pis:
                        has_raw_match = True
                        break
                if has_raw_match:
                    score += 2

            if positional and score > 0 and co["id"] == positional["id"]:
                score += 0.5

            if score > best_score:
                best_score = score
                best_comp = co

        if best_score > 0:
            return best_comp
        return None

    def resolve(meta, position_index):
        return match_component(meta, position_index)

    updates = []
    for raw in rows[4:]:
        if not any(raw):
            continue
        no = raw[0]
        if no is None:
            continue
        try:
            no = int(no)
        except (TypeError, ValueError):
            continue
        st = student_by_no.get(no)
        if not st:
            continue
        nim = str(raw[1]) if raw[1] is not None else ""
        name = str(raw[2]) if raw[2] is not None else ""
        scores = {}
        comp_col_index = 0
        for col, meta in col_meta.items():
            if col > len(raw):
                continue
            if not meta["codes"] and not meta["name"]:
                continue
            comp = resolve(meta, comp_col_index)
            comp_col_index += 1
            if not comp:
                continue
            val = raw[col - 1]
            if val is None or val == "":
                continue
            try:
                f = float(val)
            except (TypeError, ValueError):
                continue
            scores[comp["id"]] = max(0.0, min(100.0, f))
        updates.append({"student_id": st["id"], "nim": nim, "name": name, "scores": scores})

    student_ids = [s.id for s in Student.query.filter_by(class_id=class_id).all()]
    Score.query.filter(Score.student_id.in_(student_ids)).delete(synchronize_session=False) if student_ids else None
    for u in updates:
        st = db.session.get(Student, u["student_id"])
        if st:
            st.nim = u["nim"]
            st.name = u["name"]
        for comp_id, val in u["scores"].items():
            existing = Score.query.filter_by(student_id=u["student_id"], component_id=comp_id).first()
            if existing:
                existing.score = val
            else:
                db.session.add(Score(student_id=u["student_id"], component_id=comp_id, score=val))
    db.session.commit()
    return jsonify({"ok": True, "imported": len(updates)})


@bp.route("/api/classes/<int:class_id>/portfolio")
@api_login_required
def api_class_portfolio(class_id):
    user = current_user()
    if not user_owns_class(user, class_id):
        return jsonify({"error": "not authorized"}), 403
    data = _get_class_data(class_id)
    if not data:
        return jsonify({"error": "class not found"}), 404
    payload = compute_portfolio(
        data["course"], data["categories"], data["components"], data["criteria"],
        data["cpls"], data["students"], data["scores"],
    )
    payload["class"] = data["class"]
    return jsonify(payload)


@bp.route("/api/courses/<int:course_id>/portfolio")
@api_login_required
def api_course_portfolio(course_id):
    user = current_user()
    if not user_owns_course(user, course_id):
        return jsonify({"error": "not authorized"}), 403
    structure = _get_course_structure(course_id)
    if not structure:
        return jsonify({"error": "course not found"}), 404

    class_ids = [c.id for c in Class.query.filter_by(course_id=course_id).all()]
    classes = Class.query.filter_by(course_id=course_id).order_by(Class.name).all()
    students = (
        Student.query.filter(Student.class_id.in_(class_ids)).order_by(Student.row_no).all()
        if class_ids else []
    )
    student_ids = [s.id for s in students]
    scores = (
        Score.query.filter(Score.student_id.in_(student_ids)).all()
        if student_ids else []
    )
    payload = compute_portfolio(
        structure["course"], structure["categories"], structure["components"],
        structure["criteria"], structure["cpls"],
        [{"id": s.id, "nim": s.nim, "name": s.name, "class_id": s.class_id} for s in students],
        [s.to_dict() for s in scores],
    )
    payload["classes"] = [{"id": c.id, "name": c.name, "lecturer": c.lecturer} for c in classes]
    return jsonify(payload)
