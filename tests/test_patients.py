import csv
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock

from app import create_app, db
from app.validation import validate_patient


VALID = dict(full_name="Demo Alpha", date_of_birth="27.02.1962",
             email="alpha@example.com", glucose="232", haemoglobin="13.5",
             cholesterol="180")


class PatientTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.provider = Mock(return_value="Provider-supplied review")
        self.config = dict(TESTING=True, DATABASE=str(Path(self.folder.name) / "test.db"),
                           REVIEW_PROVIDER=self.provider, TODAY=lambda: date(2026, 11, 6))
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def rows(self):
        with self.app.app_context():
            return [dict(row) for row in db.list_patients()]

    def create(self, **changes):
        return self.client.post("/patients/new", data=VALID | changes)

    def test_create_list_and_persistence(self):
        self.assertEqual(self.create().status_code, 303)
        row = self.rows()[0]
        self.assertEqual(row["date_of_birth"], "1962-02-27")
        self.assertEqual(row["haemoglobin"], 13.5)
        self.assertEqual(row["remarks"], "Provider-supplied review")
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("27/02/1962", page)
        self.assertIn("Provider-supplied review", page)
        reopened = create_app(self.config)
        with reopened.app_context():
            self.assertEqual(dict(db.get_patient(row["id"])), row)
        payload = self.provider.call_args.args[0]
        self.assertNotIn("email", payload)
        self.assertNotIn("full_name", payload)
        self.assertNotIn("date_of_birth", payload)
        self.assertEqual(set(payload), {"glucose", "haemoglobin", "cholesterol", "units"})
        self.assertEqual(payload["units"]["haemoglobin"], "g/dL")

    def test_duplicate_edit_delete_independently(self):
        self.create()
        self.create()
        first, second = self.rows()
        self.assertNotEqual(first["id"], second["id"])
        edit = f"/patients/{first['id']}/edit"
        self.assertIn(b"27/02/1962", self.client.get(edit).data)
        response = self.client.post(edit, data=VALID | {"email": "gokul@infocare.com"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.rows()[0]["email"], "gokul@infocare.com")
        self.assertEqual(self.rows()[1], second)
        self.assertEqual(self.provider.call_count, 2)  # email-only edit preserves review
        delete = f"/patients/{first['id']}/delete"
        self.assertIn(b"Confirm deletion", self.client.get(delete).data)
        self.assertEqual(len(self.rows()), 2)  # GET never deletes
        self.assertEqual(self.client.post(delete).status_code, 303)
        self.assertEqual(self.rows(), [second])

    def test_invalid_create_and_edit_have_no_side_effects(self):
        self.create()
        before = self.rows()
        self.provider.reset_mock()
        invalid = dict(full_name="  ", email="beta@example", date_of_birth="31.11.2002",
                       glucose="nan", haemoglobin="0", cholesterol="-2.5")
        for url in ["/patients/new", f"/patients/{before[0]['id']}/edit"]:
            response = self.client.post(url, data=invalid)
            self.assertEqual(response.status_code, 422)
            page = response.get_data(as_text=True)
            self.assertIn("all 6 highlighted fields", page)
            for key, value in invalid.items():
                self.assertIn(f'value="{value}"', page)
                self.assertIn(f'id="{key}-error"', page)
            self.assertEqual(self.rows(), before)
        self.provider.assert_not_called()

    def test_unconfigured_provider_and_posted_remarks(self):
        self.app.config["REVIEW_PROVIDER"] = None
        response = self.create(remarks="Fabricated diagnosis", review_status="complete")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.rows(), [])
        page = response.get_data(as_text=True)
        self.assertIn("not configured", page)
        self.assertNotIn("Fabricated diagnosis", page)

    def test_failed_provider_retry_and_clinical_edit(self):
        self.create()
        row = self.rows()[0]
        self.provider.side_effect = TimeoutError("secret-provider-detail")
        self.assertEqual(self.create().status_code, 503)
        edit = f"/patients/{row['id']}/edit"
        response = self.client.post(edit, data=VALID | {"glucose": "111.5"})
        self.assertEqual(response.status_code, 503)
        self.assertIn(b'value="111.5"', response.data)
        self.assertIn(b"Retry save", response.data)
        self.assertNotIn(b"secret-provider-detail", response.data)
        self.assertEqual(self.rows(), [row])
        self.assertEqual(self.client.post(f"/patients/{row['id']}/review").status_code, 503)
        self.assertEqual(self.rows(), [row])
        self.provider.side_effect = None
        self.provider.return_value = "Updated review"
        self.assertEqual(self.client.post(edit, data=VALID | {"glucose": "111.5"}).status_code, 303)
        self.assertEqual(self.rows()[0]["remarks"], "Updated review")
        self.assertEqual(self.rows()[0]["glucose"], 111.5)

    def test_dob_only_edit_does_not_call_provider(self):
        self.create()
        row = self.rows()[0]
        self.provider.reset_mock()
        response = self.client.post(f"/patients/{row['id']}/edit",
                                    data=VALID | {"date_of_birth": "01/01/1961"})
        self.assertEqual(response.status_code, 303)
        self.provider.assert_not_called()
        self.assertEqual(self.rows()[0]["remarks"], row["remarks"])

    def test_bad_provider_results(self):
        for result in [None, "", "  ", {}, "x" * 5001]:
            with self.subTest(result=type(result)):
                self.provider.return_value = result
                self.assertEqual(self.create().status_code, 503)
                self.assertEqual(self.rows(), [])

    def test_parameterized_values_and_html_escaping(self):
        name = "Robert'); DROP TABLE patients;-- <script>alert(1)</script>"
        self.provider.return_value = "<script>provider()</script>"
        self.create(full_name=name)
        self.create()
        self.assertEqual(self.rows()[0]["full_name"], name)
        page = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_missing_records_and_write_methods(self):
        for suffix in ["edit", "delete", "review"]:
            self.assertEqual(self.client.post(f"/patients/999/{suffix}", data=VALID).status_code, 404)
        self.assertEqual(self.client.get("/patients/999/edit").status_code, 404)
        self.assertEqual(self.client.get("/patients/999/delete").status_code, 404)
        self.assertEqual(self.client.get("/patients/999/review").status_code, 405)
        self.assertEqual(self.client.put("/patients/new", data=VALID).status_code, 405)

    def test_equivalent_synthetic_rows(self):
        with (Path(__file__).parent / "fixtures/validation_cases.csv").open(newline="") as source:
            for row in csv.DictReader(source):
                number = int(row.pop("test_number"))
                response = self.client.post("/patients/new", data=row)
                self.assertEqual(response.status_code, 422 if number in (2, 4, 8) else 303)
                if number == 8:
                    self.assertIn(b'id="date_of_birth-error"', response.data)
                    self.assertIn(b'id="email-error"', response.data)
        self.assertEqual(len(self.rows()), 7)
        self.assertEqual(self.provider.call_count, 7)


class ValidationTests(unittest.TestCase):
    def validate(self, **changes):
        return validate_patient(VALID | changes, today=date(2026, 11, 6))

    def test_dates(self):
        for value, expected in [("28/01/1960", "1960-01-28"),
                                ("29.02.2024", "2024-02-29"),
                                ("06/11/2026", "2026-11-06")]:
            data, errors = self.validate(date_of_birth=value)
            self.assertFalse(errors)
            self.assertEqual(data["date_of_birth"], expected)
        for value in ["29/02/2025", "07/11/2026", "31.11.2001", "01/02.2000",
                      "1/02/2000", "2000-02-01", "", "01/01/0000"]:
            with self.subTest(value=value):
                self.assertIn("date_of_birth", self.validate(date_of_birth=value)[1])

    def test_email_and_numbers(self):
        for email in ["beta@example", "Eta.example.com", "a..b@test.com", "a@-test.com", ""]:
            self.assertIn("email", self.validate(email=email)[1])
        self.assertFalse(self.validate(email="Theta@example.org")[1])
        for key in ["glucose", "haemoglobin", "cholesterol"]:
            for value in ["0", "-1", "nan", "inf", "-inf", "1e999", "abc", ""]:
                with self.subTest(key=key, value=value):
                    self.assertIn(key, self.validate(**{key: value})[1])
            self.assertEqual(self.validate(**{key: "12.75"})[0][key], 12.75)
