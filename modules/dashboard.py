from flask import Blueprint, render_template

from modules.auth import current_user, login_required

bp = Blueprint("dashboard", __name__)


@bp.route("/dashboard")
@login_required
def index():
    return render_template("index.html")
