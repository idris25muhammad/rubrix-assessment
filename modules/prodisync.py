"""ProdiSync REST API v1 client, SO-PI synchronization, and rubric payload normalization."""

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import config
from modules.models import Pi, ProficiencyLevel, So, db
from modules.so_pi import pi_references, so_references


class ProdiSyncError(Exception):
    """Raised when a ProdiSync API call fails or returns invalid data."""

    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


RUBRIX_TO_PRODISYNC_PRODI = {
    "RKS": "RKS",
    "D4-TP": "TP",
    "D4-TRM": "TRM",
    "D3-TI": "TI",
    "D4-TRPL": "TRPL",
    "D3-TG": "TG",
    "D4-ANIM": "ANIM",
    "S2-TK": "S2-TK",
}

PRODISYNC_TO_RUBRIX_PRODI = {v: k for k, v in RUBRIX_TO_PRODISYNC_PRODI.items()}

DEFAULT_PRODISYNC_PROGRAMS = {"RKS", "D4-TP", "D4-TRM"}
_prodi_cache = {"codes": None, "expires_at": 0.0}


def get_prodisync_programs(force_refresh=False):
    """Return the set of RubriX study program codes managed by ProdiSync."""
    now = time.monotonic()
    if not force_refresh and _prodi_cache["codes"] is not None and now < _prodi_cache["expires_at"]:
        return set(_prodi_cache["codes"])
    try:
        res = fetch_prodi_list()
        codes = {
            p["rubrix_code"].upper()
            for p in (res.get("prodi") or [])
            if p.get("rubrix_code")
        }
        if codes:
            _prodi_cache["codes"] = codes
            _prodi_cache["expires_at"] = now + 300.0
            return set(codes)
    except ProdiSyncError:
        pass
    if _prodi_cache["codes"] is not None:
        return set(_prodi_cache["codes"])
    return set(DEFAULT_PRODISYNC_PROGRAMS)


def is_prodisync_program(study_program):
    """True if the given RubriX study program code is managed via ProdiSync API."""
    clean = str(study_program or "").strip().upper()
    if not clean:
        return False
    return clean in get_prodisync_programs()


def to_prodisync_prodi(code):
    """Convert a RubriX study program code (e.g. 'D4-TP') to a ProdiSync code ('TP')."""
    clean = str(code or "").strip().upper()
    return RUBRIX_TO_PRODISYNC_PRODI.get(clean, clean)


def to_rubrix_prodi(code):
    """Convert a ProdiSync study program code (e.g. 'TP') to a RubriX code ('D4-TP')."""
    clean = str(code or "").strip().upper()
    return PRODISYNC_TO_RUBRIX_PRODI.get(clean, clean)


def _request_json(path, params=None):
    """Perform a GET request against ProdiSync API v1 and return parsed JSON."""
    base_url = (config.PRODISYNC_BASE_URL or "").rstrip("/")
    api_key = (config.PRODISYNC_API_KEY or "").strip()
    if not base_url:
        raise ProdiSyncError("PRODISYNC_BASE_URL belum dikonfigurasi", status_code=500)
    if not api_key:
        raise ProdiSyncError("RKS_PRODISYNC_API_KEY belum dikonfigurasi di .env", status_code=500)

    url = f"{base_url}/{path.lstrip('/')}"
    if params:
        filtered = {k: v for k, v in params.items() if v is not None and str(v).strip() != ""}
        if filtered:
            url = f"{url}?{urlencode(filtered)}"

    req = Request(
        url,
        method="GET",
        headers={
            "X-API-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "RubriX/1.0",
        },
    )
    try:
        with urlopen(req, timeout=config.PRODISYNC_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as e:
        detail = ""
        try:
            err_body = json.loads(e.read().decode("utf-8"))
            detail = err_body.get("error") or err_body.get("message") or ""
        except Exception:
            detail = ""
        msg = f"ProdiSync API HTTP {e.code}" + (f": {detail}" if detail else "")
        raise ProdiSyncError(msg, status_code=e.code if 400 <= e.code < 500 else 502) from e
    except (URLError, TimeoutError, OSError) as e:
        raise ProdiSyncError(f"Gagal terhubung ke ProdiSync API: {e}", status_code=502) from e
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ProdiSyncError(f"Respons ProdiSync API tidak valid: {e}", status_code=502) from e


def ping():
    return _request_json("/ping")


def fetch_prodi_list():
    resp = _request_json("/prodi")
    items = []
    for p in resp.get("data") or []:
        kode = p.get("kode") or ""
        items.append({
            "prodisync_code": kode,
            "rubrix_code": to_rubrix_prodi(kode),
            "nama": p.get("nama") or "",
            "jenjang": p.get("jenjang") or "",
        })
    meta = resp.get("meta") or {}
    return {
        "prodi": items,
        "tahun_ajaran_aktif": meta.get("tahun_ajaran_aktif") or {},
    }


def fetch_proficiency_levels():
    resp = _request_json("/proficiency-levels")
    return resp.get("data") or []


def fetch_so_pi(study_program):
    prodi_code = to_prodisync_prodi(study_program)
    resp = _request_json(f"/prodi/{quote(prodi_code, safe='')}/so-pi")
    return resp.get("data") or {}, resp.get("meta") or {}


def fetch_matakuliah(study_program, rps_status="approved", ta=None, semester=None):
    prodi_code = to_prodisync_prodi(study_program)
    resp = _request_json(
        f"/prodi/{quote(prodi_code, safe='')}/matakuliah",
        params={"rps_status": rps_status, "ta": ta, "semester": semester},
    )
    return resp.get("data") or [], resp.get("meta") or {}


def fetch_matakuliah_rubrik(study_program, kode_mk, ta=None):
    prodi_code = to_prodisync_prodi(study_program)
    resp = _request_json(
        f"/prodi/{quote(prodi_code, safe='')}/matakuliah/{quote(kode_mk, safe='')}/rubrik",
        params={"ta": ta},
    )
    return resp.get("data") or {}, resp.get("meta") or {}


def fetch_rubrik_courses(study_program, rps_status="approved", ta=None, semester=None):
    prodi_code = to_prodisync_prodi(study_program)
    resp = _request_json(
        f"/prodi/{quote(prodi_code, safe='')}/rubrik-courses",
        params={"rps_status": rps_status, "ta": ta, "semester": semester},
    )
    return resp.get("data") or [], resp.get("meta") or {}


def sync_so_pi_from_prodisync(study_program):
    """Synchronize ProficiencyLevels, SO, and PI for a study program from ProdiSync."""
    rubrix_program = str(study_program or "").strip() or "RKS"
    prodisync_code = to_prodisync_prodi(rubrix_program)

    data, meta = fetch_so_pi(rubrix_program)
    levels = data.get("proficiency_levels") or []
    if not levels:
        levels = fetch_proficiency_levels()

    for lvl in levels:
        lvl_num = int(lvl.get("level"))
        label = str(lvl.get("label") or "").strip()
        if not label:
            continue
        row = ProficiencyLevel.query.filter_by(level=lvl_num).first()
        if row:
            row.label = label
        else:
            db.session.add(ProficiencyLevel(level=lvl_num, label=label))

    outcomes = data.get("student_outcomes") or []
    so_created = 0
    so_updated = 0
    so_deleted = 0
    pi_created = 0
    pi_updated = 0
    pi_deleted = 0
    kept_referenced = []

    existing_sos = {
        s.so_code: s for s in So.query.filter_by(study_program=rubrix_program).all()
    }
    incoming_so_codes = set()

    for si, so_in in enumerate(outcomes):
        if so_in.get("is_active") is False:
            continue
        so_code = str(so_in.get("so_code") or "").strip()
        if not so_code:
            continue
        incoming_so_codes.add(so_code)
        so_desc = str(so_in.get("description") or "").strip()

        so_row = existing_sos.get(so_code)
        if so_row:
            so_row.so_description = so_desc
            so_row.sort_order = si
            so_updated += 1
        else:
            so_row = So(
                study_program=rubrix_program,
                so_code=so_code,
                so_description=so_desc,
                sort_order=si,
            )
            db.session.add(so_row)
            db.session.flush()
            existing_sos[so_code] = so_row
            so_created += 1

        existing_pis = {
            p.pi_code: p for p in Pi.query.filter_by(so_id=so_row.id).all()
        }
        incoming_pi_codes = set()

        for pi_i, pi_in in enumerate(so_in.get("performance_indicators") or []):
            pi_code = str(pi_in.get("pi_code") or "").strip()
            if not pi_code:
                continue
            incoming_pi_codes.add(pi_code)
            pi_desc = str(pi_in.get("description") or "").strip()
            try:
                pi_lvl = int(pi_in.get("level") or 3)
            except (TypeError, ValueError):
                pi_lvl = 3
            if pi_lvl not in (1, 2, 3, 4, 5):
                pi_lvl = 3

            pi_row = existing_pis.get(pi_code)
            if pi_row:
                pi_row.pi_description = pi_desc
                pi_row.proficiency_level = pi_lvl
                pi_row.sort_order = pi_i
                pi_updated += 1
            else:
                db.session.add(
                    Pi(
                        so_id=so_row.id,
                        pi_code=pi_code,
                        pi_description=pi_desc,
                        proficiency_level=pi_lvl,
                        sort_order=pi_i,
                    )
                )
                pi_created += 1

        # Remove PIs absent from ProdiSync only if unreferenced by existing courses.
        for old_pi_code, old_pi_row in existing_pis.items():
            if old_pi_code not in incoming_pi_codes:
                refs = pi_references(rubrix_program, so_code, old_pi_code)
                if refs:
                    kept_referenced.append(f"{so_code}/{old_pi_code} (dipakai: {', '.join(refs)})")
                else:
                    db.session.delete(old_pi_row)
                    pi_deleted += 1

    # Remove SOs absent from ProdiSync only if unreferenced by existing courses.
    for old_so_code, old_so_row in existing_sos.items():
        if old_so_code not in incoming_so_codes:
            refs = so_references(rubrix_program, old_so_code)
            for p in old_so_row.performance_indicators:
                refs.extend(pi_references(rubrix_program, old_so_code, p.pi_code))
            if refs:
                kept_referenced.append(f"{old_so_code} (dipakai: {', '.join(sorted(set(refs)))})")
            else:
                db.session.delete(old_so_row)
                so_deleted += 1

    db.session.commit()

    return {
        "study_program": rubrix_program,
        "prodisync_prodi": prodisync_code,
        "so_created": so_created,
        "so_updated": so_updated,
        "so_deleted": so_deleted,
        "pi_created": pi_created,
        "pi_updated": pi_updated,
        "pi_deleted": pi_deleted,
        "kept_referenced": kept_referenced,
        "total_so": len(incoming_so_codes),
        "total_pi": meta.get("pi_count") or (pi_created + pi_updated),
    }


def normalize_prodisync_rubrik(payload, requested_program=None):
    """Normalize a ProdiSync /rubrik payload into RubriX's wizard-ready structure."""
    if not isinstance(payload, dict):
        raise ProdiSyncError("Payload rubrik ProdiSync tidak valid", status_code=502)

    raw_program = payload.get("study_program") or requested_program or "RKS"
    study_program = requested_program or to_rubrix_prodi(raw_program)

    cpls_out = []
    for cpl in payload.get("cpls") or []:
        if not isinstance(cpl, dict):
            continue
        pi_codes = []
        seen_pi = set()
        for p in cpl.get("pi_codes") or []:
            ps = str(p).strip()
            if ps and ps not in seen_pi:
                seen_pi.add(ps)
                pi_codes.append(ps)
        for pair in cpl.get("so_pi_pairs") or []:
            if isinstance(pair, dict):
                ps = str(pair.get("pi_code") or "").strip()
                if ps and ps not in seen_pi:
                    seen_pi.add(ps)
                    pi_codes.append(ps)
        assessment_rubric = cpl.get("assessment_rubric")
        if isinstance(assessment_rubric, dict):
            for ps in assessment_rubric.keys():
                ps_clean = str(ps).strip()
                if ps_clean and ps_clean not in seen_pi:
                    seen_pi.add(ps_clean)
                    pi_codes.append(ps_clean)
        else:
            assessment_rubric = None

        try:
            prof_lvl = int(cpl.get("proficiency_level") or 3)
        except (TypeError, ValueError):
            prof_lvl = 3
        if prof_lvl not in (1, 2, 3, 4, 5):
            prof_lvl = 3

        cpl_entry = {
            "code": str(cpl.get("code") or "").strip(),
            "description": str(cpl.get("description") or "").strip(),
            "proficiency_level": prof_lvl,
            "so_codes": [str(s).strip() for s in (cpl.get("so_codes") or []) if str(s).strip()],
            "pi_codes": pi_codes,
            "so_pi_pairs": cpl.get("so_pi_pairs") or [],
        }
        if assessment_rubric:
            cpl_entry["assessment_rubric"] = assessment_rubric
        cpls_out.append(cpl_entry)

    try:
        sks = int(payload.get("sks") or 0)
    except (TypeError, ValueError):
        sks = 0

    try:
        target_attainment = int(payload.get("target_attainment") if payload.get("target_attainment") is not None else 60)
    except (TypeError, ValueError):
        target_attainment = 60

    return {
        "course_code": str(payload.get("course_code") or "").strip(),
        "course_name": str(payload.get("course_name") or "").strip(),
        "sks": sks,
        "semester": str(payload.get("semester") or "").strip(),
        "study_program": study_program,
        "is_pbl": bool(payload.get("is_pbl")),
        "target_attainment": target_attainment,
        "rps_status": payload.get("rps_status") or "approved",
        "semester_ke": payload.get("semester_ke"),
        "cpls": cpls_out,
        "categories": payload.get("categories") or [],
    }
