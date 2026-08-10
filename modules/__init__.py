import os
import re

from flask import Flask, url_for
from flask_migrate import Migrate

from config import SECRET_KEY, SQLALCHEMY_DATABASE_URI
from modules.models import db


def _url_pat(endpoint, arg):
    """Build a url_for pattern with a '{id}' placeholder for a dynamic int segment."""
    return re.sub(r"/0(?=/|$)", "/{id}", url_for(endpoint, **{arg: 0}))


def create_app():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        template_folder=os.path.join(base, "templates"),
        static_folder=os.path.join(base, "static"),
    )
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["SESSION_PERMANENT"] = True
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    Migrate(app, db)

    # NOTE: schema is managed by Flask-Migrate (flask db upgrade).
    # Seed users after tables exist (migrations run via CLI before app import in prod).
    try:
        with app.app_context():
            from modules.seed import seed_so_pi, seed_users

            seed_users()
            seed_so_pi()
    except Exception:
        # Tables may not exist yet (before first migration) - that's fine.
        pass

    @app.context_processor
    def inject_user():
        from modules.auth import current_user

        return {"user": current_user()}

    @app.context_processor
    def inject_urls():
        """Expose a url_for-based JS URL table. Dynamic ids use a '{id}' placeholder."""
        urls = {
            "dashboard": url_for("dashboard.index"),
            "login": url_for("auth.login"),
            "logout": url_for("auth.logout"),
            "change_password": url_for("auth.change_password"),
            "users": url_for("users.index"),
            "course_template": url_for("courses.api_course_template"),
            "so_pi": url_for("courses.api_so_pi"),
            "programs": url_for("courses.api_programs"),
            "sopi": url_for("sopi.index"),
            "sopi_api": url_for("sopi.api_sopi"),
            "sopi_programs": url_for("sopi.api_sopi_programs"),
            "sopi_create_so": url_for("sopi.api_create_so"),
            "sopi_so": _url_pat("sopi.api_so", "so_id"),
            "sopi_create_pi": url_for("sopi.api_create_pi"),
            "sopi_pi": _url_pat("sopi.api_pi", "pi_id"),
            "sopi_levels": url_for("sopi.api_levels"),
            "sopi_statistics": url_for("sopi.statistics"),
            "sopi_api_statistics_semesters": url_for("sopi.api_statistics_semesters"),
            "sopi_api_statistics": url_for("sopi.api_statistics"),
            "manage_classes": _url_pat("courses.manage_classes_page", "course_id"),
            "assess": _url_pat("courses.assess_page", "class_id"),
            "portfolio": _url_pat("courses.portfolio_page", "class_id"),
            "portfolio_course": _url_pat("courses.portfolio_course_page", "course_id"),
            "api_courses": url_for("courses.api_courses"),
            "api_semesters": url_for("courses.api_semesters"),
            "api_dashboard": url_for("courses.api_dashboard"),
            "api_upload": url_for("courses.api_upload_course"),
            "api_create": url_for("courses.api_create_course"),
            "api_course": _url_pat("courses.api_course", "course_id"),
            "api_course_editable": _url_pat("courses.api_course_editable", "course_id"),
            "api_course_share": _url_pat("courses.api_course_share", "course_id"),
            "api_classes": _url_pat("courses.api_classes", "course_id"),
            "api_class": _url_pat("courses.api_class", "class_id"),
            "api_save": _url_pat("courses.api_save", "class_id"),
            "api_export": _url_pat("courses.api_export", "class_id"),
            "api_export_sid": _url_pat("courses.api_export_sid", "class_id"),
            "api_import": _url_pat("courses.api_import", "class_id"),
            "api_class_portfolio": _url_pat("courses.api_class_portfolio", "class_id"),
            "api_course_portfolio": _url_pat("courses.api_course_portfolio", "course_id"),
            "api_users": url_for("users.api_users"),
            "api_user": _url_pat("users.api_user", "user_id"),
            "share_options": url_for("users.api_share_options"),
        }
        return {"urls": urls}

    from modules import auth, dashboard, users
    from modules.blueprints import courses, sopi

    app.register_blueprint(auth.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(courses.bp)
    app.register_blueprint(sopi.bp)

    return app
