import json
import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pymupdf
from openpyxl import load_workbook
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as project


class GradePilotTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.database = root / "test.db"
        project.DB = self.database
        project.UPLOAD_DIR = root / "uploads"
        project.UPLOAD_DIR.mkdir()
        self._create_legacy_database()
        project.init_db()
        project.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = project.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_legacy_database(self):
        with closing(sqlite3.connect(self.database)) as con:
            con.execute("""CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student TEXT NOT NULL, college_id TEXT NOT NULL,
                department TEXT NOT NULL, semester TEXT DEFAULT '',
                total REAL NOT NULL, topics TEXT NOT NULL, filename TEXT NOT NULL,
                extracted TEXT, suggested REAL NOT NULL, final REAL NOT NULL,
                feedback TEXT, created TEXT NOT NULL
            )""")
            con.execute("""INSERT INTO submissions
                (student,college_id,department,semester,total,topics,filename,
                 extracted,suggested,final,feedback,created)
                VALUES ('Legacy Student','OLD-01','CSE','1st',10,'Loops',
                        'legacy.png','text',5,5,'review','01 Jan 2024')""")
            con.commit()

    def _csrf(self):
        with self.client.session_transaction() as state:
            state.setdefault("_csrf_token", "test-token")
            return state["_csrf_token"]

    def _post(self, path, data=None, **kwargs):
        values = dict(data or {})
        values["_csrf_token"] = self._csrf()
        return self.client.post(path, data=values, **kwargs)

    def _create_teacher_and_login(self):
        response = self._post("/setup", {
            "full_name": "Teacher One",
            "login_id": "teacher",
            "password": "teacher-password",
        })
        self.assertEqual(response.status_code, 302)
        response = self._post("/login", {
            "login_id": "teacher",
            "password": "teacher-password",
        })
        self.assertEqual(response.status_code, 302)

    @staticmethod
    def _fake_grading(*_):
        return {"score": 7.5, "feedback": "Test feedback"}

    def test_setup_migration_teacher_edits_and_both_exports(self):
        self.assertEqual(self.client.get("/").location, "/setup")
        self._create_teacher_and_login()

        with patch.object(project, "extract_text", return_value=("assignment text", "")), \
                patch.object(project, "evaluate_answer", side_effect=self._fake_grading):
            response = self._post("/evaluate", {
                "student": "Riya Student",
                "college_id": "C-100",
                "kid": "K-100",
                "department": "CSE",
                "semester": "2nd",
                "topics": "Python",
                "total": "10",
                "assignment": (io.BytesIO(b"image"), "answer.png"),
            }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)

        with project.connect() as con:
            con.row_factory = sqlite3.Row
            rows = con.execute("SELECT * FROM submissions ORDER BY id").fetchall()
            self.assertEqual(rows[0]["student"], "Legacy Student")
            self.assertEqual(rows[1]["kid"], "K-100")
            self.assertEqual(rows[1]["suggested"], 7.5)
            submission_id = rows[1]["id"]

        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self._post(f"/edit/{submission_id}", {"final": "8"}).status_code, 302)
        with project.connect() as con:
            self.assertEqual(con.execute(
                "SELECT final FROM submissions WHERE id=?", (submission_id,)
            ).fetchone()[0], 8)

        csv_response = self.client.get("/export?q=K-100")
        self.assertIn(b"text/csv", csv_response.content_type.encode())
        self.assertIn(b"K-100", csv_response.data)
        excel_response = self.client.get("/export?format=xlsx")
        workbook = load_workbook(io.BytesIO(excel_response.data), read_only=True)
        self.assertEqual(workbook.active["A2"].value, "Legacy Student")
        self.assertIn("application/vnd.openxmlformats", excel_response.content_type)

    def test_selectable_pdf_submission_uses_real_extraction_and_grading(self):
        self._create_teacher_and_login()
        document = pymupdf.open()
        page = document.new_page()
        page.insert_text((72, 72), "Python variables and loops " * 40)
        pdf_data = document.tobytes()
        document.close()

        response = self._post("/evaluate", {
            "student": "PDF Student",
            "college_id": "PDF-01",
            "kid": "PDF-KID",
            "department": "CSE",
            "semester": "1st",
            "topics": "Python, Variables",
            "total": "10",
            "assignment": (io.BytesIO(pdf_data), "assignment.pdf"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        with project.connect() as con:
            row = con.execute(
                "SELECT extracted,suggested,final FROM submissions WHERE college_id='PDF-01'"
            ).fetchone()
        self.assertIn("Python", row["extracted"])
        self.assertGreater(row["suggested"], 0)
        self.assertEqual(row["final"], row["suggested"])

    def test_student_submission_history_and_role_boundaries(self):
        response = self._post("/register", {
            "full_name": "Student One",
            "college_id": "C-200",
            "kid": "K-200",
            "department": "AIML",
            "semester": "4th",
            "password": "student-password",
        })
        self.assertEqual(response.status_code, 302)
        self._post("/login", {"login_id": "C-200", "password": "student-password"})

        with patch.object(project, "extract_text", return_value=("answer", "")), \
                patch.object(project, "evaluate_answer", side_effect=self._fake_grading):
            response = self._post("/student/submit", {
                "student": "Spoofed Name",
                "college_id": "SPOOFED",
                "topics": "Networks",
                "total": "10",
                "assignment": (io.BytesIO(b"image"), "work.png"),
            }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/student/dashboard").status_code, 200)
        self.assertEqual(self.client.get("/student/OLD-01").status_code, 403)
        self.assertEqual(self.client.get("/export").status_code, 403)
        self.assertEqual(self._post("/edit/1", {"final": "9"}).status_code, 403)

        with project.connect() as con:
            row = con.execute(
                "SELECT student,college_id,kid,department,semester FROM submissions WHERE account_id IS NOT NULL"
            ).fetchone()
        self.assertEqual(tuple(row), ("Student One", "C-200", "K-200", "AIML", "4th"))

    def test_csrf_required_and_pwa_assets_available(self):
        self.assertEqual(self.client.post("/login", data={"login_id": "x"}).status_code, 400)
        manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertIn(b'"display": "standalone"', manifest.data)
        worker = self.client.get("/sw.js")
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker.headers["Service-Worker-Allowed"], "/")
        self.assertEqual(self.client.get("/offline").status_code, 200)
        manifest_data = json.loads(manifest.data)
        self.assertIn("192x192", [icon["sizes"] for icon in manifest_data["icons"]])
        for size in (192, 512):
            with Image.open(project.ROOT / "static" / f"icon-{size}.png") as icon:
                self.assertEqual(icon.size, (size, size))
        manifest.close()
        worker.close()

    def test_spreadsheet_exports_escape_formula_values(self):
        self._create_teacher_and_login()
        with project.connect() as con:
            con.execute("""INSERT INTO submissions
                (student,college_id,department,semester,total,topics,filename,
                 suggested,final,created)
                VALUES ('=2+2','FORMULA-01','CSE','1st',10,'Loops',
                        'formula.png',5,5,'01 Jan 2024')""")
        csv_response = self.client.get("/export")
        self.assertIn(b"'=2+2", csv_response.data)
        excel_response = self.client.get("/export?format=xlsx")
        workbook = load_workbook(io.BytesIO(excel_response.data), read_only=True)
        self.assertEqual(workbook.active["A2"].value, "'=2+2")

    def test_frozen_app_uses_per_user_data_directory(self):
        local_app_data = Path(self.temp_dir.name) / "LocalAppData"
        with patch.object(project.sys, "frozen", True, create=True), \
                patch.dict(project.os.environ, {"LOCALAPPDATA": str(local_app_data)}):
            self.assertEqual(
                project.resolve_app_data_dir(),
                local_app_data / "GradePilot",
            )


if __name__ == "__main__":
    unittest.main()
