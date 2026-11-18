import json
import os
import sys
import tempfile
import unittest

# Ensure project root is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Configure isolated SQLite DB before importing app/config
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["RKS_DB_ENGINE"] = "sqlite"
os.environ["RKS_DB_FILE"] = _tmp_db.name

from modules import create_app  # noqa: E402
from modules.auth import ROLE_ADMIN, ROLE_KPS, ROLE_LECTURER, hash_password  # noqa: E402
from modules.helpers import angkatan_from_nim  # noqa: E402
from modules.models import Category, Class, Component, Course, Cpl, Score, So, Student, User, db  # noqa: E402


def _make_course(owner_id, code, name, study_program="RKS", semester="Ganjil 2025/2026"):
    raw = {
        "course_code": code,
        "course_name": name,
        "sks": 3,
        "semester": semester,
        "study_program": study_program,
        "is_pbl": False,
        "target_attainment": 60,
        "cpls": [{"code": "CPL1", "description": "Desc", "proficiency_level": 3, "so_codes": ["SO1"]}],
        "categories": [],
    }
    c = Course(
        owner_id=owner_id,
        course_code=code,
        course_name=name,
        sks=3,
        semester=semester,
        study_program=study_program,
        is_pbl=False,
        raw_json=json.dumps(raw),
    )
    db.session.add(c)
    db.session.flush()
    db.session.add(Cpl(course_id=c.id, code="CPL1", description="Desc", proficiency_level=3, so_codes='["SO1"]', sort_order=0))
    cat = Category(course_id=c.id, key="tugas", label="Tugas", sort_order=0)
    db.session.add(cat)
    db.session.flush()
    comp = Component(
        category_id=cat.id,
        name="Tugas 1",
        cpl_pis=json.dumps([{"cpl": "CPL1", "so": "SO1", "pi": "1a"}]),
        weight=100.0,
        sort_order=0,
    )
    db.session.add(comp)
    db.session.flush()
    return c, comp


class HelperTests(unittest.TestCase):
    def test_angkatan_from_nim(self):
        self.assertEqual(angkatan_from_nim("3312301001"), "2023")
        self.assertEqual(angkatan_from_nim("4312401099"), "2024")
        self.assertEqual(angkatan_from_nim(" 3312101005 "), "2021")
        self.assertEqual(angkatan_from_nim("1234"), "Tidak diketahui")
        self.assertEqual(angkatan_from_nim("ABC2301001"), "Tidak diketahui")
        self.assertEqual(angkatan_from_nim(""), "Tidak diketahui")
        self.assertEqual(angkatan_from_nim(None), "Tidak diketahui")


class RoleAndFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(_tmp_db.name):
            try:
                os.unlink(_tmp_db.name)
            except OSError:
                pass

    def setUp(self):
        with self.app.app_context():
            Score.query.delete()
            Student.query.delete()
            Class.query.delete()
            Component.query.delete()
            Category.query.delete()
            Cpl.query.delete()
            Course.query.delete()
            So.query.delete()
            User.query.delete()
            db.session.commit()

            self.admin = User(name="Admin", email="admin@polibatam.ac.id", password_hash=hash_password("pass123"), role=ROLE_ADMIN, study_program=None)
            self.kps_rks = User(name="KPS RKS", email="rks@polibatam.ac.id", password_hash=hash_password("pass123"), role=ROLE_KPS, study_program="RKS")
            self.kps_ti = User(name="KPS TI", email="ti@polibatam.ac.id", password_hash=hash_password("pass123"), role=ROLE_KPS, study_program="D3-TI")
            self.owner = User(name="Dosen Owner", email="owner@polibatam.ac.id", password_hash=hash_password("pass123"), role=ROLE_LECTURER, study_program="RKS")
            self.assigned = User(name="Dosen Assigned", email="assigned@polibatam.ac.id", password_hash=hash_password("pass123"), role=ROLE_LECTURER, study_program="RKS")
            self.other = User(name="Dosen Other", email="other@polibatam.ac.id", password_hash=hash_password("pass123"), role=ROLE_LECTURER, study_program="RKS")
            db.session.add_all([self.admin, self.kps_rks, self.kps_ti, self.owner, self.assigned, self.other])
            db.session.flush()

            db.session.add(So(study_program="RKS", so_code="SO1", so_description="SO 1", sort_order=0))
            db.session.add(So(study_program="D3-TI", so_code="SO1", so_description="SO 1 TI", sort_order=0))

            c_rks, comp_rks = _make_course(self.owner.id, "RKS101", "Keamanan Jaringan", "RKS")
            c_kps, _ = _make_course(self.kps_rks.id, "RKS102", "Kriptografi", "RKS")
            c_ti, comp_ti = _make_course(self.kps_ti.id, "TI101", "Algoritma", "D3-TI")

            cl_assigned = Class(course_id=c_rks.id, owner_id=self.owner.id, lecturer_id=self.assigned.id, name="Pagi A", lecturer=self.assigned.name, academic_year="2025/2026")
            cl_unassigned = Class(course_id=c_rks.id, owner_id=self.owner.id, lecturer_id=self.owner.id, name="Malam A", lecturer=self.owner.name, academic_year="2024/2025")
            cl_ti = Class(course_id=c_ti.id, owner_id=self.kps_ti.id, lecturer_id=self.kps_ti.id, name="TI A", lecturer=self.kps_ti.name, academic_year="2025/2026")
            db.session.add_all([cl_assigned, cl_unassigned, cl_ti])
            db.session.flush()

            s1 = Student(class_id=cl_assigned.id, row_no=1, nim="3312301001", name="Alice")
            s2 = Student(class_id=cl_unassigned.id, row_no=1, nim="3312401002", name="Bob")
            s3 = Student(class_id=cl_ti.id, row_no=1, nim="3312301003", name="Charlie")
            db.session.add_all([s1, s2, s3])
            db.session.flush()

            db.session.add(Score(student_id=s1.id, component_id=comp_rks.id, score=90.0))
            db.session.add(Score(student_id=s2.id, component_id=comp_rks.id, score=70.0))
            db.session.add(Score(student_id=s3.id, component_id=comp_ti.id, score=80.0))
            db.session.commit()

            self.ids = {
                "admin": self.admin.id,
                "kps_rks": self.kps_rks.id,
                "kps_ti": self.kps_ti.id,
                "owner": self.owner.id,
                "assigned": self.assigned.id,
                "other": self.other.id,
                "c_rks": c_rks.id,
                "c_kps": c_kps.id,
                "c_ti": c_ti.id,
                "cl_assigned": cl_assigned.id,
                "cl_unassigned": cl_unassigned.id,
                "cl_ti": cl_ti.id,
                "s1": s1.id,
                "comp_rks": comp_rks.id,
            }
        self.client = self.app.test_client()

    def _login(self, email):
        self.client.post("/logout")
        return self.client.post("/login", data={"email": email, "password": "pass123"}, follow_redirects=False)

    def test_permissions_matrix_courses_and_classes(self):
        # Assigned lecturer sees c_rks with is_assigned=True, can_edit=False, can_delete=False
        self._login("assigned@polibatam.ac.id")
        res = self.client.get("/api/courses")
        self.assertEqual(res.status_code, 200)
        courses = res.get_json()["courses"]
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0]["id"], self.ids["c_rks"])
        self.assertTrue(courses[0]["is_assigned"])
        self.assertFalse(courses[0]["can_edit"])
        self.assertFalse(courses[0]["can_delete"])

        # Assigned lecturer cannot edit/delete course or view combined portfolio or add class
        self.assertEqual(self.client.put(f"/api/courses/{self.ids['c_rks']}", json={}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/courses/{self.ids['c_rks']}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/courses/{self.ids['c_rks']}/portfolio").status_code, 403)
        self.assertEqual(self.client.get(f"/portfolio/course/{self.ids['c_rks']}").status_code, 403)
        self.assertEqual(self.client.post(f"/api/courses/{self.ids['c_rks']}/classes", json={"name": "Baru"}).status_code, 403)

        # Assigned lecturer only sees cl_assigned in classes list, cannot delete it, cannot access cl_unassigned
        res_cls = self.client.get(f"/api/courses/{self.ids['c_rks']}/classes")
        self.assertEqual(res_cls.status_code, 200)
        cls_list = res_cls.get_json()["classes"]
        self.assertEqual([c["id"] for c in cls_list], [self.ids["cl_assigned"]])
        self.assertTrue(cls_list[0]["can_edit"])
        self.assertFalse(cls_list[0]["can_delete"])

        self.assertEqual(self.client.delete(f"/api/classes/{self.ids['cl_assigned']}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/classes/{self.ids['cl_unassigned']}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/classes/{self.ids['cl_assigned']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/classes/{self.ids['cl_assigned']}/portfolio").status_code, 200)
        self.assertEqual(
            self.client.put(
                f"/api/classes/{self.ids['cl_assigned']}",
                json={"name": "Pagi A", "lecturer_id": self.ids["assigned"], "academic_year": "2025/2026"},
            ).status_code,
            200,
        )

        # Unrelated lecturer gets 403 everywhere on c_rks / cl_assigned
        self._login("other@polibatam.ac.id")
        self.assertEqual(self.client.get(f"/api/courses/{self.ids['c_rks']}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/classes/{self.ids['cl_assigned']}").status_code, 403)

        # KPS RKS can view/edit c_rks, cannot delete c_rks (owned by owner), CAN delete c_kps (owned by self), cannot access c_ti
        self._login("rks@polibatam.ac.id")
        self.assertEqual(self.client.get(f"/api/courses/{self.ids['c_rks']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/courses/{self.ids['c_rks']}").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/classes/{self.ids['cl_assigned']}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/courses/{self.ids['c_ti']}").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/courses/{self.ids['c_kps']}").status_code, 200)

        # Admin can access & delete any course/class
        self._login("admin@polibatam.ac.id")
        self.assertEqual(self.client.get(f"/api/courses/{self.ids['c_ti']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/classes/{self.ids['cl_unassigned']}").status_code, 200)

    def test_users_and_kps_restrictions(self):
        self._login("rks@polibatam.ac.id")
        # KPS cannot create admin
        res = self.client.post(
            "/users/api/users",
            json={"name": "New Admin", "email": "newadmin@polibatam.ac.id", "role": "admin", "password": "password123"},
        )
        self.assertEqual(res.status_code, 403)

        # KPS cannot edit or delete existing admin
        res = self.client.put(
            f"/users/api/users/{self.ids['admin']}",
            json={"name": "Hacked", "email": "admin@polibatam.ac.id", "role": "lecturer"},
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self.client.delete(f"/users/api/users/{self.ids['admin']}").status_code, 403)

        # KPS cannot promote lecturer to admin
        res = self.client.put(
            f"/users/api/users/{self.ids['other']}",
            json={"name": "Other", "email": "other@polibatam.ac.id", "role": "admin"},
        )
        self.assertEqual(res.status_code, 403)

        # KPS requires study_program
        res = self.client.post(
            "/users/api/users",
            json={"name": "KPS No Prodi", "email": "kpsnp@polibatam.ac.id", "role": "kps", "password": "password123"},
        )
        self.assertEqual(res.status_code, 400)

        # Lecturers endpoint returns all accounts
        res_lect = self.client.get("/api/users/lecturers")
        self.assertEqual(res_lect.status_code, 200)
        roles = {u["role"] for u in res_lect.get_json()}
        self.assertEqual(roles, {"admin", "kps", "lecturer"})

    def test_assessment_links(self):
        self._login("assigned@polibatam.ac.id")
        # Invalid URL rejected
        res = self.client.put(
            f"/api/classes/{self.ids['cl_assigned']}/assessment-links",
            json={"soal_ats_teori": "ftp://invalid.com/file"},
        )
        self.assertEqual(res.status_code, 400)

        # Valid URLs saved
        res = self.client.put(
            f"/api/classes/{self.ids['cl_assigned']}/assessment-links",
            json={
                "soal_ats_teori": "https://drive.google.com/file/d/abc",
                "soal_aas_praktikum": "https://drive.google.com/file/d/xyz",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["assessment_links_count"], 2)
        self.assertEqual(data["soal_ats_teori"], "https://drive.google.com/file/d/abc")

        # Clear one link
        res = self.client.put(
            f"/api/classes/{self.ids['cl_assigned']}/assessment-links",
            json={"soal_ats_teori": "", "soal_aas_praktikum": "https://drive.google.com/file/d/xyz"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["assessment_links_count"], 1)

        # Unassigned lecturer gets 403
        self._login("other@polibatam.ac.id")
        self.assertEqual(self.client.get(f"/api/classes/{self.ids['cl_assigned']}/assessment-links").status_code, 403)

    def test_statistics_angkatan_tahun_ajaran_and_scoping(self):
        # Lecturer cannot access statistics
        self._login("owner@polibatam.ac.id")
        self.assertEqual(self.client.get("/sopi/api/statistics").status_code, 403)

        # KPS RKS is forced to RKS even if requesting D3-TI
        self._login("rks@polibatam.ac.id")
        res = self.client.get("/sopi/api/statistics?mode=angkatan&value=2023&study_program=D3-TI")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["study_program"], "RKS")
        self.assertEqual(data["total_students"], 1)
        self.assertEqual(data["grade_distribution"]["A"], 1)
        self.assertEqual(len(data["comparison"]), 2)  # 2023 and 2024 in RKS

        # Admin can query all prodi or specific prodi, and filter by tahun_ajaran
        self._login("admin@polibatam.ac.id")
        res_all = self.client.get("/sopi/api/statistics?mode=tahun_ajaran&value=2025/2026&study_program=all")
        self.assertEqual(res_all.status_code, 200)
        d_all = res_all.get_json()
        self.assertEqual(d_all["study_program"], "all")
        self.assertEqual(d_all["total_students"], 2)  # s1 (RKS) + s3 (D3-TI)

    def test_dashboard_scoping(self):
        self._login("assigned@polibatam.ac.id")
        res = self.client.get("/api/dashboard")
        self.assertEqual(res.status_code, 200)
        d = res.get_json()
        self.assertEqual(d["course_count"], 1)
        self.assertEqual(d["class_count"], 1)  # Only cl_assigned, NOT cl_unassigned!
        self.assertEqual(d["student_count"], 1)

    def test_rubric_finalization_validation(self):
        from modules.models import Pi
        from modules.rubric_builder import build_rubric_from_wizard

        with self.app.app_context():
            so1 = So.query.filter_by(study_program="RKS", so_code="SO1").first()
            db.session.add(Pi(so_id=so1.id, pi_code="PI-01.1", pi_description="PI 1", sort_order=0))
            db.session.add(Pi(so_id=so1.id, pi_code="PI-01.2", pi_description="PI 2", sort_order=1))
            db.session.commit()

            base_payload = {
                "course_code": "RKS-999",
                "course_name": "Test Validation",
                "study_program": "RKS",
                "sks": 3,
                "semester": "2025/2026 Ganjil",
                "cpls": [
                    {
                        "code": "CPL1",
                        "description": "CPL 1",
                        "proficiency_level": 3,
                        "so_codes": ["SO1"],
                        "assessment_rubric": {"PI-01.1": {"1": "a"}, "PI-01.2": {"1": "b"}},
                    },
                    {
                        "code": "CPL2",
                        "description": "CPL 2",
                        "proficiency_level": 3,
                        "so_codes": ["SO1"],
                    },
                ],
                "categories": {
                    "tugas": [
                        {"name": "Tugas 1", "weight": 50, "cpl_pis": [{"cpl": "CPL1", "so": "SO1", "pi": "PI-01.1"}]},
                        {"name": "Tugas 2", "weight": 50, "cpl_pis": []},
                    ]
                },
            }

            # 1. Weighted component without CPL-PI mapping fails
            with self.assertRaises(ValueError):
                build_rubric_from_wizard(base_payload)

            # 2. All weighted components mapped, but CPL2 unmapped fails
            base_payload["categories"]["tugas"][1]["cpl_pis"] = [{"cpl": "CPL1", "so": "SO1", "pi": "PI-01.2"}]
            with self.assertRaises(ValueError):
                build_rubric_from_wizard(base_payload)

            # 3. CPL2 mapped, but PI-01.2 from assessment_rubric unmapped fails
            base_payload["categories"]["tugas"][1]["cpl_pis"] = [{"cpl": "CPL2", "so": "SO1", "pi": "PI-01.1"}]
            with self.assertRaises(ValueError):
                build_rubric_from_wizard(base_payload)

            # 4. All CPLs and all PIs mapped succeeds
            base_payload["categories"]["tugas"][1]["cpl_pis"] = [
                {"cpl": "CPL1", "so": "SO1", "pi": "PI-01.2"},
                {"cpl": "CPL2", "so": "SO1", "pi": "PI-01.1"},
            ]
            out = build_rubric_from_wizard(base_payload)
            self.assertEqual(out["course_code"], "RKS-999")


if __name__ == "__main__":
    unittest.main()
