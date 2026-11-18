import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)
os.environ["RKS_DB_ENGINE"] = "sqlite"
os.environ["RKS_DB_FILE"] = _DB_PATH

from modules import create_app  # noqa: E402
from modules.models import Course, Pi, ProficiencyLevel, So, User, db  # noqa: E402
from modules.prodisync import (  # noqa: E402
    normalize_prodisync_rubrik,
    sync_so_pi_from_prodisync,
    to_prodisync_prodi,
    to_rubrix_prodi,
)
from modules.rubric_builder import build_rubric_from_wizard  # noqa: E402


MOCK_SO_PI_PAYLOAD = (
    {
        "prodi": {"kode": "RKS", "nama": "Rekayasa Keamanan Siber", "jenjang": "D4"},
        "proficiency_levels": [
            {"level": 1, "label": "to have experienced or been exposed to"},
            {"level": 2, "label": "to be able to participate in and contribute to"},
            {"level": 3, "label": "to be able to understand and explain"},
            {"level": 4, "label": "to be skilled in the practice or implementation of"},
            {"level": 5, "label": "to be able to lead or innovate in"},
        ],
        "student_outcomes": [
            {
                "so_code": "SO9",
                "description": "SO9 from ProdiSync",
                "is_active": True,
                "performance_indicators": [
                    {"pi_code": "PI-09.4", "description": "PI 9.4", "level": 3},
                ],
            },
            {
                "so_code": "SO10",
                "description": "SO10 from ProdiSync",
                "is_active": True,
                "performance_indicators": [
                    {"pi_code": "PI-10.1", "description": "PI 10.1", "level": 4},
                ],
            },
        ],
    },
    {"prodi": "RKS", "so_count": 2, "pi_count": 2},
)


MOCK_MATAKULIAH = (
    [
        {
            "kode": "MKU004",
            "nama": "English for Workspace Communication",
            "sks": 3,
            "semester": None,
            "kurikulum": "v2 IABEE",
            "tipe": "wajib",
            "rps": {
                "status": "approved",
                "tahun_ajaran": "2026/2027 Ganjil",
                "clo_count": 1,
                "so_codes": ["SO9"],
                "pi_codes": ["PI-09.4"],
            },
        },
        {
            "kode": "MPK002RKS",
            "nama": "Pancasila Education",
            "sks": 2,
            "semester": None,
            "kurikulum": "v2 IABEE",
            "tipe": "wajib",
            "rps": None,
        },
    ],
    {"prodi": "RKS", "tahun_ajaran": "2026/2027 Ganjil", "count": 2},
)


MOCK_RUBRIK_MKU004 = (
    {
        "course_code": "MKU004",
        "course_name": "English for Workspace Communication",
        "sks": 3,
        "semester": "2026/2027 Ganjil",
        "study_program": "RKS",
        "is_pbl": False,
        "target_attainment": 60,
        "rps_status": "approved",
        "cpls": [
            {
                "code": "CPL1",
                "description": "Use professional terminology",
                "proficiency_level": 2,
                "so_codes": ["SO9"],
                "pi_codes": ["PI-09.4"],
                "so_pi_pairs": [{"so_code": "SO9", "pi_code": "PI-09.4", "level": 3}],
                "assessment_rubric": None,
            }
        ],
        "categories": [
            {
                "key": "tugas",
                "label": "Tugas",
                "components": [
                    {
                        "name": "Tugas 1",
                        "weight": 100,
                        "cpl_pis": [],
                        "criteria": [
                            {"level": 1, "label": "Sangat Kurang", "score_min": 0, "score_max": 30, "subjects": ["Kurang"]},
                            {"level": 2, "label": "Kurang", "score_min": 31, "score_max": 55, "subjects": ["Kurang"]},
                            {"level": 3, "label": "Cukup", "score_min": 56, "score_max": 70, "subjects": ["Cukup"]},
                            {"level": 4, "label": "Baik", "score_min": 71, "score_max": 89, "subjects": ["Baik"]},
                            {"level": 5, "label": "Sangat Baik", "score_min": 90, "score_max": 100, "subjects": ["Sangat Baik"]},
                        ],
                    }
                ],
            }
        ],
    },
    {"prodi": "RKS", "tahun_ajaran": "2026/2027 Ganjil"},
)


class ProdiSyncIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()
            from modules.seed import seed_users

            seed_users()
            if not ProficiencyLevel.query.count():
                for i in range(1, 6):
                    db.session.add(ProficiencyLevel(level=i, label=f"Level {i}"))
            if not User.query.filter_by(email="dosen@polibatam.ac.id").first():
                from modules.auth import hash_password

                db.session.add(User(
                    name="Dosen Test",
                    email="dosen@polibatam.ac.id",
                    password_hash=hash_password("dosen@polibatam.ac.id"),
                    role="lecturer",
                    study_program="RKS",
                ))
            db.session.commit()

    def setUp(self):
        self.client = self.app.test_client()

    def _login(self, email):
        return self.client.post(
            "/login",
            data={"email": email, "password": email},
            follow_redirects=False,
        )

    def test_prodi_code_mapping(self):
        self.assertEqual(to_prodisync_prodi("D4-TP"), "TP")
        self.assertEqual(to_prodisync_prodi("D4-TRM"), "TRM")
        self.assertEqual(to_prodisync_prodi("RKS"), "RKS")
        self.assertEqual(to_rubrix_prodi("TP"), "D4-TP")
        self.assertEqual(to_rubrix_prodi("TRM"), "D4-TRM")

    def test_sopi_sync_and_readonly_lock(self):
        self._login("rks@polibatam.ac.id")

        with patch("modules.prodisync.get_prodisync_programs", return_value={"RKS", "D4-TP", "D4-TRM"}):
            # ProdiSync-managed prodi (RKS): manual mutations must return 403
            res_get = self.client.get("/sopi/api?program=RKS")
            self.assertEqual(res_get.status_code, 200)
            self.assertTrue(res_get.get_json()["is_prodisync"])

            res_create_so = self.client.post("/sopi/api/so", json={"study_program": "RKS", "so_code": "SO99"})
            self.assertEqual(res_create_so.status_code, 403)
            res_levels = self.client.put("/sopi/api/levels", json={"proficiency_levels": [{"level": 1, "label": "X"}]})
            self.assertEqual(res_levels.status_code, 403)

            # Sync endpoint should upsert SO-PI
            with patch("modules.prodisync.fetch_so_pi", return_value=MOCK_SO_PI_PAYLOAD):
                res_sync = self.client.post("/sopi/api/sync", json={"study_program": "RKS"})
                self.assertEqual(res_sync.status_code, 200)
                body = res_sync.get_json()
                self.assertTrue(body["ok"])
                self.assertEqual(body["sync"]["total_so"], 2)

        with self.app.app_context():
            so9 = So.query.filter_by(study_program="RKS", so_code="SO9").first()
            self.assertIsNotNone(so9)
            self.assertEqual(so9.so_description, "SO9 from ProdiSync")
            pi94 = Pi.query.filter_by(so_id=so9.id, pi_code="PI-09.4").first()
            self.assertIsNotNone(pi94)

            # Second sync should be idempotent (0 created)
            with patch("modules.prodisync.fetch_so_pi", return_value=MOCK_SO_PI_PAYLOAD):
                summary2 = sync_so_pi_from_prodisync("RKS")
                self.assertEqual(summary2["so_created"], 0)
                self.assertEqual(summary2["pi_created"], 0)

    def test_manual_sopi_allowed_for_non_prodisync_program(self):
        self._login("admin@polibatam.ac.id")

        with patch("modules.prodisync.get_prodisync_programs", return_value={"RKS", "D4-TP", "D4-TRM"}):
            res_get = self.client.get("/sopi/api?program=D3-TI")
            self.assertEqual(res_get.status_code, 200)
            self.assertFalse(res_get.get_json()["is_prodisync"])

            # Create SO & PI manually for D3-TI
            res_so = self.client.post(
                "/sopi/api/so",
                json={"study_program": "D3-TI", "so_code": "SO1", "so_description": "Manual SO1"},
            )
            self.assertEqual(res_so.status_code, 200)
            so_id = res_so.get_json()["so"]["id"]

            res_pi = self.client.post(
                "/sopi/api/pi",
                json={"so_id": so_id, "pi_code": "PI-01.1", "pi_description": "Manual PI", "proficiency_level": 3},
            )
            self.assertEqual(res_pi.status_code, 200)
            pi_id = res_pi.get_json()["pi"]["id"]

            # Clean up
            self.assertEqual(self.client.delete(f"/sopi/api/pi/{pi_id}").status_code, 200)
            self.assertEqual(self.client.delete(f"/sopi/api/so/{so_id}").status_code, 200)

    def test_prodisync_course_catalog_and_rubrik_with_null_assessment_rubric(self):
        self._login("dosen@polibatam.ac.id")

        with patch(
            "modules.prodisync.fetch_prodi_list",
            return_value={
                "prodi": [
                    {"prodisync_code": "RKS", "rubrix_code": "RKS", "nama": "Rekayasa Keamanan Siber", "jenjang": "D4"},
                    {"prodisync_code": "TP", "rubrix_code": "D4-TP", "nama": "Teknologi Permainan", "jenjang": "D4"},
                ],
                "tahun_ajaran_aktif": {"label": "2026/2027 Ganjil"},
            },
        ):
            res_prodi = self.client.get("/api/prodisync/programs")
            self.assertEqual(res_prodi.status_code, 200)
            prodi_codes = [p["code"] for p in res_prodi.get_json()["programs"]]
            self.assertEqual(prodi_codes, ["RKS", "D4-TP"])

        with patch("modules.prodisync.fetch_matakuliah", return_value=MOCK_MATAKULIAH):
            res = self.client.get("/api/prodisync/courses?program=RKS")
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(len(data["courses"]), 2)
            self.assertEqual(data["courses"][0]["kode"], "MKU004")
            self.assertFalse(data["courses"][0]["already_exists"])

        with (
            patch("modules.prodisync.fetch_so_pi", return_value=MOCK_SO_PI_PAYLOAD),
            patch("modules.prodisync.fetch_matakuliah_rubrik", return_value=MOCK_RUBRIK_MKU004),
        ):
            res = self.client.get("/api/prodisync/courses/MKU004/rubrik?program=RKS")
            self.assertEqual(res.status_code, 200)
            rubrik = res.get_json()["rubrik"]
            self.assertEqual(rubrik["course_code"], "MKU004")
            self.assertEqual(rubrik["cpls"][0]["pi_codes"], ["PI-09.4"])

        # Validate rubric_builder enforces pi_codes even when assessment_rubric is None
        with self.app.app_context():
            norm = normalize_prodisync_rubrik(MOCK_RUBRIK_MKU004[0], requested_program="RKS")
            # Unmapped PI-09.4 should fail
            bad_payload = {
                **norm,
                "categories": {
                    "tugas": [
                        {"name": "Tugas 1", "weight": 100, "cpl_pis": []}
                    ]
                },
            }
            with self.assertRaises(ValueError):
                build_rubric_from_wizard(bad_payload)

            # Mapped PI-09.4 should succeed
            good_payload = {
                **norm,
                "categories": {
                    "tugas": [
                        {
                            "name": "Tugas 1",
                            "weight": 100,
                            "cpl_pis": [{"cpl": "CPL1", "so": "SO9", "pi": "PI-09.4"}],
                        }
                    ]
                },
            }
            built = build_rubric_from_wizard(good_payload)
            self.assertEqual(built["course_code"], "MKU004")

        # Create course via API and verify catalog marks it already_exists
        res_create = self.client.post("/api/courses/create", json=good_payload)
        self.assertEqual(res_create.status_code, 200)

        with patch("modules.prodisync.fetch_matakuliah", return_value=MOCK_MATAKULIAH):
            res_after = self.client.get("/api/prodisync/courses?program=RKS")
            self.assertEqual(res_after.status_code, 200)
            mku = res_after.get_json()["courses"][0]
            self.assertTrue(mku["already_exists"])


if __name__ == "__main__":
    unittest.main()
