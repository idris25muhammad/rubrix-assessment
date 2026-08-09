import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "course_dummy.json")

LEVELS = [
    ("0-30", "Sangat Kurang"),
    ("31-55", "Kurang"),
    ("56-70", "Cukup"),
    ("71-89", "Baik"),
    ("90-100", "Sangat Baik"),
]

PHRASES = [
    "tidak terlaksana",
    "terlaksana sebagian kecil",
    "terlaksana sebagian besar dengan kualitas cukup",
    "terlaksana seluruhnya dengan baik",
    "terlaksana seluruhnya secara konsisten dan menonjol",
]

# key, label, components(name, weight, [cpl_pi mappings])
CATEGORIES = [
    ("partisipatif", "Partisipatif", [
        ("Kehadiran & Keaktifan Kelas", 5, [{"cpl": "CPL1", "so": "SO1", "pi": "1a"}]),
        ("Kontribusi Diskusi", 5, [{"cpl": "CPL2", "so": "SO3", "pi": "3c"}]),
    ]),
    ("tugas", "Tugas", [
        ("Tugas 1 - Pengumpulan & Kebenaran", 10, [{"cpl": "CPL2", "so": "SO2", "pi": "2a"}]),
        ("Tugas 2 - Kualitas Penyelesaian", 10, [{"cpl": "CPL3", "so": "SO4", "pi": "4c"}]),
        ("Tugas 3 - Kerja Mandiri & Ketepatan", 10, [{"cpl": "CPL1", "so": "SO1", "pi": "1b"}]),
    ]),
    ("kuis", "Kuis", [
        ("Kuis 1", 5, [{"cpl": "CPL3", "so": "SO3", "pi": "3d"}]),
        ("Kuis 2", 5, [{"cpl": "CPL1", "so": "SO1", "pi": "1c"}]),
    ]),
    ("ats", "Asesmen Tengah Semester (ATS)", [
        ("ATS - Ujian Tengah", 15, [{"cpl": "CPL4", "so": "SO5", "pi": "5b"}]),
    ]),
    ("aas", "Asesmen Akhir Semester (AAS)", [
        ("AAS - Ujian Akhir", 20, [{"cpl": "CPL4", "so": "SO4", "pi": "4a"}]),
    ]),
    ("proyek", "Proyek", [
        ("Proyek Akhir", 15, [{"cpl": "CPL5", "so": "SO9", "pi": "9a"}, {"cpl": "CPL5", "so": "SO8", "pi": "8a"}]),
    ]),
]

CPLS = [
    {"code": "CPL1", "description": "Menguasai konsep dasar keamanan siber dan mampu menerapkannya.",
     "proficiency_level": 3, "so_codes": ["SO1"]},
    {"code": "CPL2", "description": "Mampu menganalisis dan merancang solusi keamanan yang relevan.",
     "proficiency_level": 4, "so_codes": ["SO2", "SO3"]},
    {"code": "CPL3", "description": "Mampu mengimplementasikan dan mengevaluasi pengamanan sistem.",
     "proficiency_level": 4, "so_codes": ["SO3", "SO4"]},
    {"code": "CPL4", "description": "Mampu melakukan investigasi dan penilaian keamanan siber.",
     "proficiency_level": 4, "so_codes": ["SO4", "SO5"]},
    {"code": "CPL5", "description": "Mampu bekerja dalam tim dan berkomunikasi secara profesional.",
     "proficiency_level": 3, "so_codes": ["SO8", "SO9"]},
]


def build_criteria(name):
    criteria = []
    for i, ((rng, label), phrase) in enumerate(zip(LEVELS, PHRASES)):
        low, high = rng.split("-")
        criteria.append({
            "level": i + 1,
            "score_min": int(low),
            "score_max": int(high),
            "label": label,
            "subjects": [f"{name} {phrase}", f"Secara keseluruhan dinilai {label.lower()} (skor {rng})"],
        })
    return criteria


def build_course():
    categories = []
    for key, label, comps in CATEGORIES:
        categories.append({
            "key": key,
            "label": label,
            "components": [
                {"name": name, "weight": weight, "cpl_pis": cpl_pis, "criteria": build_criteria(name)}
                for name, weight, cpl_pis in comps
            ],
        })
    return {
        "course_code": "INF2201",
        "course_name": "Pengembangan Aplikasi Berbasis Web",
        "sks": 3,
        "semester": "Ganjil 2026/2027",
        "study_program": "RKS",
        "is_pbl": False,
        "categories": categories,
        "cpls": CPLS,
    }


def main():
    course = build_course()
    total = sum(c["weight"] for cat in course["categories"] for c in cat["components"])
    pbl = sum(c["weight"] for cat in course["categories"] if cat["key"] in ("partisipatif", "proyek") for c in cat["components"])
    print("components:", sum(len(c["components"]) for c in course["categories"]))
    print("weight sum:", total, "| PBL weight:", pbl)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(course, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
