import json
import os

from config import BASE_DIR

SO_PI_PATH = os.path.join(BASE_DIR, "static", "data", "so-pi.json")


def _load_so_pi():
    with open(SO_PI_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_course_json(data):
    """Validate the course rubric JSON (CPL-based schema). Raises ValueError on problems."""
    required_top = ["course_code", "course_name", "categories"]
    for k in required_top:
        if k not in data:
            raise ValueError(f"Missing required field: '{k}'")
    if not isinstance(data["categories"], list) or not data["categories"]:
        raise ValueError("'categories' must be a non-empty list")

    sopi = _load_so_pi()
    so_map = {so["so_code"]: so for so in sopi["student_outcome"]}

    # Collect component CPL-PI mappings.
    component_cpls = {}  # cpl_code -> set of pi codes used

    for ci, cat in enumerate(data["categories"]):
        if not isinstance(cat, dict) or "key" not in cat or "label" not in cat:
            raise ValueError(f"Category #{ci + 1} must have 'key' and 'label'")
        comps = cat.get("components")
        if not isinstance(comps, list) or not comps:
            raise ValueError(f"Category '{cat.get('label')}' has no components")
        for ri, comp in enumerate(comps):
            if not isinstance(comp, dict) or "name" not in comp or "weight" not in comp:
                raise ValueError(f"Component #{ri + 1} in '{cat.get('label')}' must have 'name' and 'weight'")
            weight = comp.get("weight")
            if not isinstance(weight, (int, float)) or weight < 0:
                raise ValueError(f"Component '{comp.get('name')}' weight must be >= 0")
            cpl_pis = comp.get("cpl_pis")
            if not isinstance(cpl_pis, list) or not cpl_pis:
                raise ValueError(f"Component '{comp.get('name')}' needs at least one cpl_pis mapping")
            for m in cpl_pis:
                cpl_code = m.get("cpl")
                so_code = m.get("so")
                pi_code = m.get("pi")
                if not cpl_code or not so_code or not pi_code:
                    raise ValueError(f"Component '{comp.get('name')}' has an incomplete CPL-PI mapping")
                if so_code not in so_map:
                    raise ValueError(f"SO '{so_code}' not found in so-pi.json")
                valid_pis = {p["pi_code"] for p in so_map[so_code]["performance_indicator"]}
                if pi_code not in valid_pis:
                    raise ValueError(
                        f"PI '{pi_code}' is not valid for SO '{so_code}' in component '{comp.get('name')}'"
                    )
                component_cpls.setdefault(cpl_code, set()).add(pi_code)

    weight_sum = sum(c["weight"] for cat in data["categories"] for c in cat["components"])
    if abs(weight_sum - 100) > 0.001:
        raise ValueError(f"Total weight must be 100%, got {weight_sum}%")

    # Validate CPLs.
    cpls = data.get("cpls") or []
    if not cpls:
        raise ValueError("Course must define at least one CPL")
    cpl_codes = set()
    for cpl in cpls:
        if "code" not in cpl:
            raise ValueError("Each CPL must have a 'code'")
        cpl_codes.add(cpl["code"])
        level = cpl.get("proficiency_level")
        if level not in (1, 2, 3, 4, 5):
            raise ValueError(f"CPL {cpl['code']} proficiency_level must be 1-5")
        for so_code in (cpl.get("so_codes") or []):
            if so_code not in so_map:
                raise ValueError(f"CPL {cpl['code']} references unknown SO '{so_code}'")

    # Every component CPL must be declared.
    for cpl_code in component_cpls:
        if cpl_code not in cpl_codes:
            raise ValueError(f"Component references undeclared CPL '{cpl_code}'")

    # PBL rule: if PBL, partisipatif + proyek >= 50%.
    if data.get("is_pbl"):
        by_key = {cat["key"]: cat for cat in data["categories"]}
        pbl_weight = 0.0
        for key in ("partisipatif", "proyek"):
            cat = by_key.get(key)
            if cat:
                pbl_weight += sum(c["weight"] for c in cat["components"])
        if pbl_weight < 50:
            raise ValueError(
                f"Untuk PBL, total bobot Partisipatif + Proyek harus >= 50%, sekarang {pbl_weight:g}%"
            )

    return True
