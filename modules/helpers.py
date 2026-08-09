import json

from modules.models import Component


def _get(comp, key, default=None):
    """Fetch attribute from an ORM object or a dict."""
    if isinstance(comp, dict):
        return comp.get(key, default)
    return getattr(comp, key, default)


def cpl_pis_of(component):
    """Parse component.cpl_pis -> [{cpl, so, pi}, ...]."""
    raw = _get(component, "cpl_pis")
    if isinstance(raw, list):
        return raw
    if raw:
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return []
    return []


def so_pi_labels(cpl_pis):
    """SO-PI display labels: CPL{idx}-{pi} for each mapping."""
    result = []
    for m in cpl_pis:
        cpl = m.get("cpl") or m.get("cpl_code") or "CPL"
        pi = m.get("pi") or m.get("pi_code") or ""
        result.append(f"{cpl}-{pi}")
    return result


def grade_of_score(score):
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 65:
        return "C"
    if score >= 50:
        return "D"
    return "E"


def _cpls_data_from(cpls):
    """Normalize cpl rows (ORM objects or dicts) into [{code, description, proficiency_level, so_codes}]."""
    result = []
    for cpl in (cpls or []):
        code = _get(cpl, "code")
        level = _get(cpl, "proficiency_level", 3)
        description = _get(cpl, "description", "")
        so_codes = _get(cpl, "so_codes")
        if isinstance(so_codes, str):
            try:
                so_codes = json.loads(so_codes)
            except (TypeError, ValueError):
                so_codes = []
        result.append({
            "code": code,
            "description": description,
            "proficiency_level": level,
            "so_codes": so_codes,
        })
    return result


def _component_json(co, cpls=None):
    _cpls_data_from(cpls)  # validate/parse (kept for consistency)
    mappings = cpl_pis_of(co)
    return {
        "id": _get(co, "id"),
        "name": _get(co, "name"),
        "cpl_pis": mappings,
        "so_pi": so_pi_labels(mappings),
        "weight": _get(co, "weight"),
        "category_id": _get(co, "category_id"),
    }


def _cpls_list(cpl_rows):
    result = []
    for cpl in (cpl_rows or []):
        so_codes = _get(cpl, "so_codes")
        if isinstance(so_codes, str):
            try:
                so_codes = json.loads(so_codes)
            except (TypeError, ValueError):
                so_codes = []
        result.append(
            {
                "id": _get(cpl, "id"),
                "code": _get(cpl, "code"),
                "description": _get(cpl, "description"),
                "proficiency_level": _get(cpl, "proficiency_level"),
                "so_codes": so_codes,
            }
        )
    return result
