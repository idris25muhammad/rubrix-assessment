import json

from modules.helpers import _component_json, _cpls_data_from, _get, cpl_pis_of, grade_of_score, so_pi_labels


def compute_portfolio(course, categories, components, criteria, cpls, students, scores):
    # Find student IDs that have at least one score
    assessed_student_ids = { _get(sc, "student_id") for sc in scores if _get(sc, "score") is not None }

    # Filter out blank student placeholder rows (where name and NIM are empty and there are no scores)
    actual_students = [
        s for s in students 
        if (_get(s, "name") and str(_get(s, "name")).strip() != "") or 
           (_get(s, "nim") and str(_get(s, "nim")).strip() != "") or
           (_get(s, "id") in assessed_student_ids)
    ]

    score_rows = {_get(s, "id"): {} for s in actual_students}
    for sc in scores:
        sid = _get(sc, "student_id")
        if sid in score_rows:
            score_rows[sid][_get(sc, "component_id")] = _get(sc, "score")

    def level_of(score, component_id=None):
        for cr in criteria:
            if component_id is not None and cr["component_id"] != component_id:
                continue
            if cr["score_min"] <= score <= cr["score_max"]:
                return cr["level"]
        return None

    cpls_data = _cpls_data_from(cpls)

    totals = []
    per_component_scores = {_get(co, "id"): [] for co in components}
    for sid, scores_map in score_rows.items():
        if not scores_map:
            continue
        s = sum((scores_map.get(_get(co, "id")) or 0) * (_get(co, "weight") / 100.0) for co in components)
        totals.append(s)
        for co in components:
            if scores_map.get(_get(co, "id")) is not None:
                per_component_scores[_get(co, "id")].append(scores_map[_get(co, "id")])

    component_stats = []
    for co in components:
        cid = _get(co, "id")
        vals = per_component_scores[cid]
        cat = next((c for c in categories if c["id"] == _get(co, "category_id")), None)
        component_stats.append(
            {
                "id": cid,
                "name": _get(co, "name"),
                "cpl_pis": cpl_pis_of(co),
                "so_pi": so_pi_labels(cpl_pis_of(co)),
                "code_pi": ", ".join(so_pi_labels(cpl_pis_of(co))),
                "weight": _get(co, "weight"),
                "category": cat["label"] if cat else "",
                "n": len(vals),
                "mean": round(sum(vals) / len(vals), 2) if vals else None,
                "std": (
                    round((sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / len(vals)) ** 0.5, 2)
                    if vals
                    else None
                ),
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "level_counts": {lv: 0 for lv in sorted({c["level"] for c in criteria})},
            }
        )
        for v in vals:
            lv = level_of(v, cid)
            if lv is not None:
                component_stats[-1]["level_counts"][lv] += 1

    dist_levels = sorted({c["level"] for c in criteria})
    total_level_dist = {lv: 0 for lv in dist_levels}
    # For overall total scores, use the criteria of the first component as standard range
    first_comp_id = components[0]["id"] if components else None
    for t in totals:
        lv = level_of(t, first_comp_id)
        if lv is not None:
            total_level_dist[lv] += 1

    # Overall grade distribution (A-E)
    grade_dist = {g: sum(1 for t in totals if grade_of_score(t) == g) for g in "ABCDE"}

    weight_sum = round(sum(_get(co, "weight") for co in components), 2)

    # Per-code breakdown keyed by SO-PI label (e.g. "CPL1-1a").
    code_map = {}
    for co in components:
        for label in so_pi_labels(cpl_pis_of(co)):
            code_map.setdefault(label, {"id": label, "components": [], "scores": [], "weight": 0.0})
            entry = code_map[label]
            entry["components"].append(_get(co, "name"))
            entry["weight"] += _get(co, "weight")
            entry["scores"].extend(per_component_scores[_get(co, "id")])
    code_stats = []
    for code in sorted(code_map):
        e = code_map[code]
        vals = e["scores"]
        code_stats.append(
            {
                "code_pi": e["id"],
                "n_components": len(e["components"]),
                "components": e["components"],
                "total_weight": e["weight"],
                "n": len(vals),
                "mean": round(sum(vals) / len(vals), 2) if vals else None,
                "std": (
                    round((sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / len(vals)) ** 0.5, 2)
                    if vals
                    else None
                ),
                "min": min(vals) if vals else None,
                "max": max(vals) if vals else None,
                "grade_counts": {g: sum(1 for v in vals if grade_of_score(v) == g) for g in "ABCDE"},
            }
        )

    # CPL mapping: CPL -> so_codes -> components that mapped any PI from those SOs.
    cpl_stats = []
    for cpl in cpls_data:
        cpl_code = cpl["code"]
        indicators = []
        for co in components:
            for m in cpl_pis_of(co):
                if m.get("cpl") == cpl_code:
                    indicators.append(
                        {
                            "cpl": cpl_code,
                            "so": m.get("so", ""),
                            "pi": m.get("pi", ""),
                            "label": f"{cpl_code}-{m.get('pi', '')}",
                            "component_id": _get(co, "id"),
                            "component": _get(co, "name"),
                            "weight": _get(co, "weight"),
                        }
                    )
        cpl_stats.append(
            {
                "code": cpl_code,
                "description": cpl["description"],
                "proficiency_level": cpl["proficiency_level"],
                "so_codes": cpl["so_codes"],
                "indicators": indicators,
                "n_indicators": len(indicators),
            }
        )

    return {
        "course": dict(course),
        "categories": [dict(c) for c in categories],
        "components": [_component_json(co, cpls) for co in components],
        "criteria_levels": [
            dict(level_info)
            for level_info in {
                (c["level"], c["label"], c["score_min"], c["score_max"]): {
                    "level": c["level"],
                    "label": c["label"],
                    "score_min": c["score_min"],
                    "score_max": c["score_max"],
                }
                for c in criteria
            }.values()
        ],
        "n_students_assessed": len(totals),
        "total_students": len(actual_students),
        "avg_total": round(sum(totals) / len(totals), 2) if totals else None,
        "median_total": (
            round(
                (sorted(totals)[len(totals) // 2] if len(totals) % 2 == 1 else (sorted(totals)[len(totals) // 2 - 1] + sorted(totals)[len(totals) // 2]) / 2.0),
                2
            ) if totals else None
        ),
        "weight_sum": weight_sum,
        "total_level_dist": total_level_dist,
        "grade_dist": grade_dist,
        "component_stats": component_stats,
        "code_stats": code_stats,
        "cpls": cpl_stats,
    }
