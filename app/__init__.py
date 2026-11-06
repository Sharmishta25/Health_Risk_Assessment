"""Application setup for the blood-test risk review project."""

from datetime import date
from pathlib import Path
import os
from dotenv import load_dotenv

from flask import Flask, abort, redirect, render_template, request, url_for

from . import db
from .provider import GeminiProvider, PredictionError, review_patient
from .validation import FIELDS, LAB_FIELDS, validate_patient


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    load_dotenv(Path(app.root_path).parent / ".env", override=False)
    app.config.from_mapping(
        DATABASE=os.getenv("HEALTH_REVIEW_DATABASE") or str(Path(app.instance_path) / "patients.sqlite3"),
        REVIEW_PROVIDER=GeminiProvider.from_environment(),
        TODAY=date.today,
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.teardown_appcontext(db.close_db)
    with app.app_context():
        db.init_db()

    @app.template_filter("display_dob")
    def display_dob(value):
        return date.fromisoformat(value).strftime("%d/%m/%Y")

    def find_patient(record_id):
        patient = db.get_patient(record_id)
        if patient is None:
            abort(404)
        return patient

    @app.get("/")
    def index():
        return render_template("index.html", patients=db.list_patients())

    @app.route("/patients/new", methods=["GET", "POST"])
    @app.route("/patients/<int:record_id>/edit", methods=["GET", "POST"])
    def patient_form(record_id=None):
        patient = find_patient(record_id) if record_id is not None else None
        values = dict(patient) if patient is not None else dict.fromkeys(FIELDS, "")
        if patient is not None:
            values["date_of_birth"] = display_dob(values["date_of_birth"])
        errors = {}
        prediction_error = None
        if request.method == "POST":
            values = {key: request.form.get(key, "") for key in FIELDS}
            data, errors = validate_patient(values, today=app.config["TODAY"]())
            if not errors:
                clinical_changed = patient is None or any(
                    data[key] != patient[key] for key in LAB_FIELDS
                )
                if clinical_changed:
                    try:
                        remarks, status = review_patient(data)
                    except PredictionError as error:
                        prediction_error = str(error)
                else:
                    remarks, status = patient["remarks"], patient["review_status"]
                if prediction_error is None:
                    db.save_patient(data, remarks, status, record_id)
                    return redirect(url_for("index"), code=303)
        return render_template("form.html", values=values, errors=errors,
                               record_id=record_id, prediction_error=prediction_error), (
                                   422 if errors else 503 if prediction_error else 200)

    @app.route("/patients/<int:record_id>/delete", methods=["GET", "POST"])
    def delete(record_id):
        patient = find_patient(record_id)
        if request.method == "POST":
            db.delete_patient(record_id)
            return redirect(url_for("index"), code=303)
        return render_template("delete.html", patient=patient)

    @app.post("/patients/<int:record_id>/review")
    def retry_review(record_id):
        patient = find_patient(record_id)
        try:
            remarks, status = review_patient(dict(patient))
        except PredictionError as error:
            return render_template("index.html", patients=db.list_patients(),
                                   prediction_error=str(error)), 503
        db.save_patient(dict(patient), remarks, status, record_id)
        return redirect(url_for("index"), code=303)

    return app
