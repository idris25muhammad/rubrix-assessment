from functools import wraps

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for

from modules.models import User, db

bp = Blueprint("auth", __name__)
hasher = PasswordHasher()

ROLE_TIM_KURIKULUM = "tim_kurikulum"
ROLE_LECTURER = "lecturer"


def hash_password(password):
    return hasher.hash(password)


def verify_password(password_hash, password):
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    user = db.session.get(User, uid)
    if not user:
        return None
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "study_program": user.get_study_program(),
        "password_hash": user.password_hash,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login", next=request.path))
            if user["role"] not in roles:
                flash("You do not have permission for this action.", "error")
                return redirect(url_for("dashboard.index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/", methods=["GET", "POST"])
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard.index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and verify_password(user.password_hash, password):
            session["user_id"] = user.id
            session.permanent = True
            nxt = request.args.get("next") or url_for("dashboard.index")
            return redirect(nxt)
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()
    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not verify_password(user["password_hash"], old):
            flash("Current password is incorrect.", "error")
        elif len(new) < 6:
            flash("New password must be at least 6 characters.", "error")
        elif new != confirm:
            flash("New passwords do not match.", "error")
        else:
            u = db.session.get(User, user["id"])
            u.password_hash = hash_password(new)
            db.session.commit()
            session.clear()
            flash("Password changed successfully. Please log in with your new password.", "success")
            return redirect(url_for("auth.login"))
    return render_template("change_password.html", user=user)


@bp.route("/api/me")
def api_me():
    return jsonify(current_user())


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return jsonify({"error": "authentication required"}), 401
        return view(*args, **kwargs)

    return wrapped
