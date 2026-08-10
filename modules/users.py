from flask import Blueprint, jsonify, render_template, request

from modules.auth import ROLE_LECTURER, ROLE_TIM_KURIKULUM, api_login_required, current_user, hash_password, role_required
from modules.models import User, db
from modules.so_pi import PROGRAMS

bp = Blueprint("users", __name__, url_prefix="/users")


def _normalize_study_program(payload, role):
    """Return (study_program_code, None) or (None, error_response)."""
    if role != ROLE_TIM_KURIKULUM:
        return None, None  # keep existing / not relevant for lecturers
    if "study_program" not in payload:
        return None, None  # keep existing
    value = (payload.get("study_program") or "").strip()
    if not value:
        return "RKS", None  # default
    if value not in PROGRAMS:
        return None, (jsonify({"error": f"prodi tidak dikenal: {value}"}), 400)
    return value, None


@bp.route("")
@bp.route("/")
@role_required(ROLE_TIM_KURIKULUM)
def index():
    return render_template("users.html")


@bp.route("/api/share-options")
@api_login_required
def api_share_options():
    """Lightweight user list for the course-share picker (any logged-in role)."""
    users = User.query.order_by(User.name).all()
    return jsonify(
        [
            {"id": u.id, "name": u.name, "email": u.email, "role": u.role}
            for u in users
        ]
    )


@bp.route("/api/users", methods=["GET", "POST"])
@api_login_required
def api_users():
    user = current_user()
    if user["role"] != ROLE_TIM_KURIKULUM:
        return jsonify({"error": "not authorized"}), 403

    if request.method == "POST":
        payload = request.json or {}
        name = payload.get("name", "").strip()
        email = payload.get("email", "").strip().lower()
        role = payload.get("role", ROLE_LECTURER)
        password = payload.get("password", "")
        if not name or not email:
            return jsonify({"error": "name and email are required"}), 400
        if role not in (ROLE_LECTURER, ROLE_TIM_KURIKULUM):
            return jsonify({"error": "invalid role"}), 400
        if len(password) < 6:
            return jsonify({"error": "password must be at least 6 characters"}), 400
        study_program, err = _normalize_study_program(payload, role)
        if err:
            return err
        existing = User.query.filter_by(email=email).first()
        if existing:
            return jsonify({"error": "email already registered"}), 400
        if study_program is None:
            study_program = "RKS"  # default for tim_kurikulum
        db.session.add(User(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role=role,
            study_program=study_program,
        ))
        db.session.commit()
        return jsonify({"ok": True})

    search = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", 10))))

    q = User.query
    if search:
        q = q.filter(User.name.like(f"%{search}%"))
    total = q.count()
    rows = (
        q.order_by(User.role, User.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return jsonify(
        {
            "items": [u.to_dict() for u in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, -(-total // page_size)),
        }
    )


@bp.route("/api/users/<int:user_id>", methods=["PUT", "DELETE"])
@api_login_required
def api_user(user_id):
    user = current_user()
    if user["role"] != ROLE_TIM_KURIKULUM:
        return jsonify({"error": "not authorized"}), 403

    if request.method == "DELETE":
        u = db.session.get(User, user_id)
        if u:
            db.session.delete(u)
            db.session.commit()
        return jsonify({"ok": True})

    if request.method == "PUT":
        payload = request.json or {}
        name = payload.get("name", "").strip()
        email = payload.get("email", "").strip().lower()
        role = payload.get("role", ROLE_LECTURER)
        if not name or not email:
            return jsonify({"error": "name and email are required"}), 400
        if role not in (ROLE_LECTURER, ROLE_TIM_KURIKULUM):
            return jsonify({"error": "invalid role"}), 400
        u = db.session.get(User, user_id)
        if not u:
            return jsonify({"error": "user not found"}), 404
        existing = User.query.filter(User.email == email, User.id != user_id).first()
        if existing:
            return jsonify({"error": "email already in use"}), 400
        study_program, err = _normalize_study_program(payload, role)
        if err:
            return err
        u.name = name
        u.email = email
        u.role = role
        if study_program is not None:
            u.study_program = study_program
        if payload.get("password"):
            if len(payload["password"]) < 6:
                return jsonify({"error": "password must be at least 6 characters"}), 400
            u.password_hash = hash_password(payload["password"])
        db.session.commit()
        return jsonify({"ok": True})
