from modules.auth import ROLE_LECTURER, ROLE_TIM_KURIKULUM, hash_password
from modules.models import User, db

# Lecturers sourced from https://rks.polibatam.ac.id/#dosen
# Password defaults to the email, as requested.
LECTURERS = [
    {"name": "Maidel Fani, S.Pd., M.Kom.", "email": "maidelfani@polibatam.ac.id", "role": ROLE_TIM_KURIKULUM},
    {"name": "Hamdani Arif, S.Pd., M.Sc", "email": "hamdaniarif@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Nur Cahyono Kushardianto, S.Si., M.T., M.Sc, Ph.D", "email": "nurkushardianto@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Andy Triwinarko, ST, M.T., Ph.D", "email": "andy@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Agus Fatulloh, S.T., M.T", "email": "agusfatulloh@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Supardianto, M.Eng.", "email": "supardianto@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Nelmiawati, B.CS., M.Comp.Sc", "email": "nelmiawati@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Dodi Prima Resda, S.Pd., M.Kom", "email": "dodi@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Antoni Haikal, S.S.T., MT", "email": "antoni@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Muhammad Idris, S.Tr., M.Tr.Kom", "email": "idris@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Festy Winda Sari, M.Sc", "email": "festy@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Hajrul Khaira, S.Tr.Kom", "email": "hajrul@polibatam.ac.id", "role": ROLE_LECTURER},
    {"name": "Agus Riady, A.Md.Kom", "email": "agusriady@polibatam.ac.id", "role": ROLE_LECTURER},
]

# An explicit tim_kurikulum account that can always be used.
TIM_KURIKULUM_ACCOUNTS = [
    {"name": "Tim Kurikulum RKS", "email": "timkurikulum@polibatam.ac.id", "role": ROLE_TIM_KURIKULUM},
]


def seed_users():
    """Insert all lecturers + tim_kurikulum accounts if they don't exist yet."""
    accounts = list(LECTURERS) + list(TIM_KURIKULUM_ACCOUNTS)
    for acc in accounts:
        existing = User.query.filter_by(email=acc["email"]).first()
        if existing:
            continue
        db.session.add(User(
            name=acc["name"],
            email=acc["email"],
            password_hash=hash_password(acc["email"]),
            role=acc["role"],
        ))
    db.session.commit()
