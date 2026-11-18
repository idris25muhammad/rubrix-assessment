"""Build a course rubric JSON from the "Create Rubric" wizard input (CPL-based)."""

from modules.so_pi import get_so_pi

CATEGORIES = [
    ("partisipatif", "Partisipatif"),
    ("tugas", "Tugas"),
    ("kuis", "Kuis"),
    ("ats", "Asesmen Tengah Semester (ATS)"),
    ("aas", "Asesmen Akhir Semester (AAS)"),
    ("proyek", "Proyek"),
]

DEFAULT_CRITERIA = [
    {"level": 1, "score_min": 0, "score_max": 30, "label": "Sangat Kurang"},
    {"level": 2, "score_min": 31, "score_max": 55, "label": "Kurang"},
    {"level": 3, "score_min": 56, "score_max": 70, "label": "Cukup"},
    {"level": 4, "score_min": 75, "score_max": 84, "label": "Baik"},
    {"level": 5, "score_min": 85, "score_max": 100, "label": "Sangat Baik"},
]

PHRASES = [
    "tidak terlaksana",
    "terlaksana sebagian kecil",
    "terlaksana sebagian besar dengan kualitas cukup",
    "terlaksana seluruhnya dengan baik",
    "terlaksana seluruhnya secara konsisten dan menonjol",
]


def _load_so_pi(study_program):
    sopi = get_so_pi(study_program)
    if not sopi:
        raise ValueError(
            f"Set SO-PI untuk program studi '{study_program}' belum tersedia. "
            "Hubungi Tim Kurikulum untuk membuatnya."
        )
    return sopi


def _criteria_for(name):
    criteria = []
    for cr, phrase in zip(DEFAULT_CRITERIA, PHRASES):
        criteria.append(
            {
                "level": cr["level"],
                "score_min": cr["score_min"],
                "score_max": cr["score_max"],
                "label": cr["label"],
                "subjects": [
                    f"{name} {phrase}",
                    f"Secara keseluruhan dinilai {cr['label'].lower()} (skor {cr['score_min']}-{cr['score_max']})",
                ],
            }
        )
    return criteria


def build_rubric_from_wizard(payload):
    """Build the CPL-based course JSON from the wizard payload.

    payload:
    {
      course_code, course_name, sks, semester, study_program, is_pbl,
      cpls: [{code, description, proficiency_level, so_codes:[...]}],
      categories: {
        partisipatif: [{name, weight, cpl_pis: [{cpl, so, pi}]}],
        ...
      }
    }
    """
    course_code = str(payload.get("course_code", "")).strip()
    course_name = str(payload.get("course_name", "")).strip()
    if not course_code or not course_name:
        raise ValueError("course_code and course_name are required")

    sopi = _load_so_pi(str(payload.get("study_program", "")).strip() or "RKS")
    so_map = {so["so_code"]: so for so in sopi["student_outcome"]}

    cpls_in = payload.get("cpls") or []
    if not isinstance(cpls_in, list) or not cpls_in:
        raise ValueError("Minimal 1 CPL harus diisi")

    # Validate CPLs and build normalized list.
    cpls = []
    cpl_codes = set()
    for ci, cpl in enumerate(cpls_in):
        code = str(cpl.get("code", "")).strip()
        if not code:
            raise ValueError(f"CPL #{ci + 1} belum memiliki kode")
        level = cpl.get("proficiency_level")
        try:
            level = int(level)
        except (TypeError, ValueError):
            raise ValueError(f"CPL {code} proficiency_level harus angka 1-5")
        if level not in (1, 2, 3, 4, 5):
            raise ValueError(f"CPL {code} proficiency_level harus 1-5")
        so_codes = []
        for so_code in (cpl.get("so_codes") or []):
            so_code = str(so_code).strip()
            if so_code not in so_map:
                raise ValueError(f"CPL {code} memilih SO '{so_code}' yang tidak dikenal")
            so_codes.append(so_code)
        if not so_codes:
            raise ValueError(f"CPL {code} harus memetakan minimal 1 SO")
        cpl_entry = {
            "code": code,
            "description": str(cpl.get("description", "")).strip(),
            "proficiency_level": level,
            "so_codes": so_codes,
        }
        if isinstance(cpl.get("assessment_rubric"), dict):
            cpl_entry["assessment_rubric"] = cpl["assessment_rubric"]
        pi_codes = [str(p).strip() for p in (cpl.get("pi_codes") or []) if str(p).strip()]
        if pi_codes:
            cpl_entry["pi_codes"] = pi_codes
        if isinstance(cpl.get("so_pi_pairs"), list):
            cpl_entry["so_pi_pairs"] = cpl["so_pi_pairs"]
        cpls.append(cpl_entry)
        cpl_codes.add(code)

    cpl_rubric_pis = {}
    for c in cpls:
        pis = set()
        if isinstance(c.get("assessment_rubric"), dict):
            pis |= set(c["assessment_rubric"].keys())
        if c.get("pi_codes"):
            pis |= set(c["pi_codes"])
        for pair in (c.get("so_pi_pairs") or []):
            if isinstance(pair, dict) and pair.get("pi_code"):
                pis.add(str(pair["pi_code"]).strip())
        if pis:
            cpl_rubric_pis[c["code"]] = pis

    # Build categories / components.
    cats_in = payload.get("categories") or {}
    if not isinstance(cats_in, dict):
        cats_in = {}
    cat_labels = payload.get("category_labels") or {}
    if not isinstance(cat_labels, dict):
        cat_labels = {}

    # Standard categories first (preserving order), then any extra categories
    # provided by the payload (e.g. an uploaded JSON that uses custom keys).
    # Only categories actually present in the payload are emitted, so categories
    # with zero components are not created.
    category_defs = []
    seen = set()
    for key, label in CATEGORIES:
        if key in cats_in:
            category_defs.append((key, label))
            seen.add(key)
    for key in cats_in.keys():
        if key not in seen:
            category_defs.append((key, str(cat_labels.get(key) or key).strip() or key))
            seen.add(key)

    categories = []
    for key, label in category_defs:
        comps_in = cats_in.get(key) or []
        if not isinstance(comps_in, list):
            comps_in = []
        comps = []
        for ri, comp in enumerate(comps_in):
            name = str(comp.get("name", "")).strip()
            weight = comp.get("weight")
            if not name:
                raise ValueError(f"Komponen #{ri + 1} pada {label} belum diisi namanya")
            try:
                weight = float(weight)
            except (TypeError, ValueError):
                raise ValueError(f"Bobot komponen '{name}' harus berupa angka")
            if weight < 0 or weight > 100:
                raise ValueError(f"Bobot komponen '{name}' harus antara 0 dan 100")
            mappings = []
            for m in (comp.get("cpl_pis") or []):
                cpl_code = str(m.get("cpl", "")).strip()
                so_code = str(m.get("so", "")).strip()
                pi_code = str(m.get("pi", "")).strip()
                if cpl_code not in cpl_codes:
                    raise ValueError(f"Komponen '{name}' memilih CPL '{cpl_code}' yang belum didefinisikan")
                if so_code not in so_map:
                    raise ValueError(f"Komponen '{name}' memilih SO '{so_code}' yang tidak dikenal")
                valid_pis = {p["pi_code"] for p in so_map[so_code]["performance_indicator"]}
                valid_pis |= cpl_rubric_pis.get(cpl_code, set())
                if pi_code not in valid_pis:
                    raise ValueError(f"PI '{pi_code}' tidak valid untuk SO '{so_code}' pada komponen '{name}'")
                mappings.append({"cpl": cpl_code, "so": so_code, "pi": pi_code})
            criteria_in = comp.get("criteria")
            if isinstance(criteria_in, list) and len(criteria_in) >= 1:
                criteria = []
                for idx, cr in enumerate(criteria_in):
                    level = cr.get("level")
                    label_cr = str(cr.get("label", "")).strip()
                    score_min = cr.get("score_min")
                    score_max = cr.get("score_max")
                    subjects = cr.get("subjects") or []
                    
                    try:
                        level = int(level)
                        score_min = int(score_min)
                        score_max = int(score_max)
                    except (TypeError, ValueError):
                        raise ValueError(f"Kriteria level/skor pada '{name}' harus berupa angka")
                        
                    if not isinstance(subjects, list):
                        subjects = [str(subjects)]
                    else:
                        subjects = [str(s).strip() for s in subjects if str(s).strip()]
                        
                    fallback_label = DEFAULT_CRITERIA[idx]["label"] if idx < len(DEFAULT_CRITERIA) else f"Level {idx + 1}"
                    criteria.append({
                        "level": level,
                        "label": label_cr if label_cr else fallback_label,
                        "score_min": score_min,
                        "score_max": score_max,
                        "subjects": subjects
                    })
            else:
                criteria = _criteria_for(name)

            comps.append(
                {
                    "name": name,
                    "weight": weight,
                    "cpl_pis": mappings,
                    "criteria": criteria,
                }
            )
        categories.append({"key": key, "label": label, "components": comps})

    weight_sum = sum(c["weight"] for cat in categories for c in cat["components"])
    if abs(weight_sum - 100) > 0.001:
        raise ValueError(f"Total bobot harus 100%, sekarang {weight_sum:g}%")

    is_pbl = bool(payload.get("is_pbl"))
    if is_pbl:
        by_key = {c["key"]: c for c in categories}
        pbl_weight = sum(
            sum(c["weight"] for c in by_key[k]["components"]) for k in ("partisipatif", "proyek") if k in by_key
        )
        if pbl_weight < 50:
            raise ValueError(f"Untuk PBL, Partisipatif + Proyek harus >= 50%, sekarang {pbl_weight:g}%")

    # Finalization validation: every CPL/CLO and PI must be mapped to the rubric.
    all_comps = [comp for cat in categories for comp in cat["components"]]
    unmapped_weighted = [comp["name"] for comp in all_comps if comp["weight"] > 0 and not comp["cpl_pis"]]
    if unmapped_weighted:
        raise ValueError(
            f"Komponen berbobot berikut belum dipetakan ke CPL/PI: {', '.join(unmapped_weighted)}. "
            "Silakan kaji ulang sebelum membuat rubrik."
        )

    used_cpls = {m["cpl"] for comp in all_comps for m in comp["cpl_pis"]}
    unmapped_cpls = [c["code"] for c in cpls if c["code"] not in used_cpls]
    if unmapped_cpls:
        raise ValueError(
            f"CPL/CLO berikut belum dipetakan ke komponen rubrik: {', '.join(unmapped_cpls)}. "
            "Silakan kaji ulang sebelum membuat rubrik."
        )

    used_cpl_pis = {(m["cpl"], m["pi"]) for comp in all_comps for m in comp["cpl_pis"]}
    unmapped_pis = [
        f"{c['code']}-{pi_code}"
        for c in cpls
        for pi_code in sorted(cpl_rubric_pis.get(c["code"], set()))
        if (c["code"], pi_code) not in used_cpl_pis
    ]
    if unmapped_pis:
        raise ValueError(
            f"PI berikut belum dipetakan ke komponen rubrik: {', '.join(unmapped_pis)}. "
            "Silakan kaji ulang sebelum membuat rubrik."
        )

    return {
        "course_code": course_code,
        "course_name": course_name,
        "sks": int(payload.get("sks", 0) or 0),
        "semester": str(payload.get("semester", "")).strip(),
        "study_program": str(payload.get("study_program", "")).strip(),
        "is_pbl": is_pbl,
        "target_attainment": int(payload.get("target_attainment", 80)),
        "cpls": cpls,
        "categories": categories,
    }
