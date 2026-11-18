import json
import os

from config import BASE_DIR

from modules.auth import ROLE_ADMIN, ROLE_KPS, hash_password
from modules.models import Pi, ProficiencyLevel, So, User, db

ADMIN_ACCOUNTS = [
    {"name": "Admin", "email": "admin@polibatam.ac.id", "role": ROLE_ADMIN, "study_program": None},
    {"name": "Kajur Teknik Informatika", "email": "kajur-if@polibatam.ac.id", "role": ROLE_ADMIN, "study_program": None},
]

# One KPS account per study program (each manages exactly one program).
# Password defaults to the email, as requested.
KPS_ACCOUNTS = [
    {"name": "KPS RKS", "email": "rks@polibatam.ac.id", "role": ROLE_KPS, "study_program": "RKS"},
    {"name": "KPS D3 Teknik Informatika", "email": "ti@polibatam.ac.id", "role": ROLE_KPS, "study_program": "D3-TI"},
    {"name": "KPS D4 Teknologi Rekayasa Multimedia", "email": "trm@polibatam.ac.id", "role": ROLE_KPS, "study_program": "D4-TRM"},
    {"name": "KPS D3 Teknologi Geomatika", "email": "tg@polibatam.ac.id", "role": ROLE_KPS, "study_program": "D3-TG"},
    {"name": "KPS D4 Animasi", "email": "an@polibatam.ac.id", "role": ROLE_KPS, "study_program": "D4-ANIM"},
    {"name": "KPS D4 Teknologi Rekayasa Perangkat Lunak", "email": "trpl@polibatam.ac.id", "role": ROLE_KPS, "study_program": "D4-TRPL"},
    {"name": "KPS D4 Teknologi Permainan", "email": "tp@polibatam.ac.id", "role": ROLE_KPS, "study_program": "D4-TP"},
    {"name": "KPS S2 Teknik Komputer", "email": "s2tk@polibatam.ac.id", "role": ROLE_KPS, "study_program": "S2-TK"},
]


def seed_users():
    for acc in ADMIN_ACCOUNTS:
        existing = User.query.filter_by(email=acc["email"]).first()
        if not existing:
            db.session.add(User(
                name=acc["name"],
                email=acc["email"],
                password_hash=hash_password(acc["email"]),
                role=acc["role"],
                study_program=None,
            ))

    for acc in KPS_ACCOUNTS:
        sp = acc.get("study_program") or "RKS"
        existing = User.query.filter_by(email=acc["email"]).first()
        if existing:
            # Backfill the default assignment only if never set (never overwrite admin edits).
            if not existing.get_study_program():
                existing.study_program = sp
            continue
        db.session.add(User(
            name=acc["name"],
            email=acc["email"],
            password_hash=hash_password(acc["email"]),
            role=acc["role"],
            study_program=sp,
        ))
    db.session.commit()


SO_PI_PATH = os.path.join(BASE_DIR, "static", "data", "so-pi.json")


def seed_so_pi():
    """Seed SO-PI sets + proficiency levels from static/data/so-pi.json.

    Idempotent: a study program's set is only inserted when it has no rows yet,
    so edits made by Tim Kurikulum in the admin UI are never overwritten.
    """
    if not os.path.exists(SO_PI_PATH):
        return

    with open(SO_PI_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Proficiency levels are a global list; only seed when empty.
    if ProficiencyLevel.query.count() == 0:
        for pl in data.get("proficiency_levels", []):
            db.session.add(ProficiencyLevel(level=pl["level"], label=pl["label"]))

    program = data.get("study_program") or "RKS"
    if So.query.filter_by(study_program=program).count() == 0:
        for si, so in enumerate(data.get("student_outcome", [])):
            so_row = So(
                study_program=program,
                so_code=so["so_code"],
                so_description=so.get("so_description", ""),
                sort_order=si,
            )
            db.session.add(so_row)
            db.session.flush()
            for pi_i, pi in enumerate(so.get("performance_indicator", [])):
                db.session.add(Pi(
                    so_id=so_row.id,
                    pi_code=pi["pi_code"],
                    pi_description=pi.get("pi_description", ""),
                    proficiency_level=int(pi.get("proficiency_level") or 3),
                    sort_order=pi_i,
                ))

    db.session.commit()
