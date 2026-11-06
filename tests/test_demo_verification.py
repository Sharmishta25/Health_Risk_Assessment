"""Recording workflow with synthetic fixtures and a mocked provider only."""
import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from app import create_app, db
from scripts.verify_demo import verify_changes, verify_seven


class RecordingVerificationTests(unittest.TestCase):
    def test_seven_edit_restart_delete_six(self):
        with tempfile.TemporaryDirectory() as folder:
            config = {"TESTING": True, "DATABASE": str(Path(folder) / "demo.sqlite3"),
                      "REVIEW_PROVIDER": Mock(return_value="Test-only review"),
                      "TODAY": lambda: date(2026, 11, 6)}
            app = create_app(config)
            client = app.test_client()
            with (Path(__file__).parent / "fixtures/validation_cases.csv").open(newline="") as source:
                cases = list(csv.DictReader(source))
            with app.app_context():
                self.assertEqual(db.list_patients(), [])
            for number, case in enumerate(cases, 1):
                response = client.post("/patients/new", data=case)
                self.assertEqual(response.status_code, 422 if number in (2, 4, 8) else 303)
            with app.app_context():
                baseline = [dict(row) for row in db.list_patients()]
            first, duplicate = verify_seven(baseline, cases)
            self.assertNotEqual(first, duplicate)
            with self.assertRaises(ValueError):
                verify_seven(baseline[:-1], cases)
            self.assertIn(b"7 saved records", client.get("/").data)
            config["REVIEW_PROVIDER"].reset_mock()
            edited = dict(cases[0], email="gokul@infocare.com")
            client.post(f"/patients/{first}/edit", data=edited)
            config["REVIEW_PROVIDER"].assert_not_called()
            reopened = create_app(config)
            with reopened.app_context():
                rows = [dict(row) for row in db.list_patients()]
            verify_changes(rows, baseline, first)
            self.assertEqual(rows[3], baseline[3])
            changed = [dict(row) for row in rows]
            changed[1]["email"] = "extra-change@example.com"
            with self.assertRaises(ValueError):
                verify_changes(changed, baseline, first)
            deleted = rows[-1]["id"]
            reopened.test_client().post(f"/patients/{deleted}/delete")
            with reopened.app_context():
                final = [dict(row) for row in db.list_patients()]
            verify_changes(final, baseline, first, deleted)
            self.assertIn(b"6 saved records", reopened.test_client().get("/").data)
            self.assertEqual(len(final), 6)
            self.assertIn(first, [row["id"] for row in final])
            self.assertIn(duplicate, [row["id"] for row in final])
            with self.assertRaises(ValueError):
                verify_changes(final, baseline, first, first)
