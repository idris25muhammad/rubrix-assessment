"""Read/write the SO-PI (Student Outcome / Performance Indicator) sets from the database.

The SO-PI data used to live in static/data/so-pi.json. It now lives in the
database (tables so_pis / performance_indicators / proficiency_levels) so that
Tim Kurikulum can edit it through the admin UI. The JSON file is only used as
an initial seed (see modules.seed.seed_so_pi).
"""

from modules.models import Pi, ProficiencyLevel, So, db

# Study programs of Jurusan Teknik Informatika, Politeknik Negeri Batam
# (from https://if.polibatam.ac.id/program-studi)
PROGRAMS = {
    "D3-TI": "D3 Teknik Informatikas",
    "D4-TRM": "D4 Teknologi Rekayasa Multimedia",
    "D3-TG": "D3 Teknologi Geomatika",
    "D4-ANIM": "D4 Animasi",
    "RKS": "D4 Rekayasa Keamanan Siber",
    "D4-TRPL": "D4 Teknologi Rekayasa Perangkat Lunak",
    "D4-TP": "D4 Teknologi Permainan",
    "S2-TK": "S2 Teknik Komputer",
}


def get_so_pi(study_program):
    """Return the SO-PI set for a study program as a dict, or None if absent.

    Shape mirrors the old so-pi.json: {study_program, student_outcome, proficiency_levels}.
    """
    sos = (
        So.query.filter_by(study_program=study_program)
        .order_by(So.sort_order, So.so_code)
        .all()
    )
    if not sos:
        return None
    return {
        "study_program": study_program,
        "student_outcome": [so.to_dict() for so in sos],
        "proficiency_levels": get_proficiency_levels(),
    }


def get_proficiency_levels():
    return [p.to_dict() for p in ProficiencyLevel.query.order_by(ProficiencyLevel.level).all()]


def get_so_by_id(so_id):
    return db.session.get(So, so_id)


def get_pi_by_id(pi_id):
    return db.session.get(Pi, pi_id)


def _course_refs(study_program):
    """Yield (course_code, set_of_so_codes_in_cpls, list_of_component_cpl_pi_mappings)."""
    from modules.models import Course

    courses = Course.query.filter_by(study_program=study_program).all()
    for c in courses:
        cpl_sos = set()
        for cpl in c.cpls:
            cpl_sos.update(cpl.get_so_codes())
        mappings = []
        for cat in c.categories:
            for comp in cat.components:
                mappings.extend(comp.get_cpl_pis())
        yield c.course_code, cpl_sos, mappings


def so_references(study_program, so_code):
    """Course codes that reference the given SO code (via CPLs or component mappings)."""
    refs = []
    for course_code, cpl_sos, mappings in _course_refs(study_program):
        used = so_code in cpl_sos or any(m.get("so") == so_code for m in mappings)
        if used:
            refs.append(course_code)
    return refs


def pi_references(study_program, so_code, pi_code):
    """Course codes whose components map to the given SO+PI pair."""
    refs = []
    for course_code, _cpl_sos, mappings in _course_refs(study_program):
        used = any(m.get("so") == so_code and m.get("pi") == pi_code for m in mappings)
        if used:
            refs.append(course_code)
    return refs
