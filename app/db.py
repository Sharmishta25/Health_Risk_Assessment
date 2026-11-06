"""One SQLite connection per request; values always use SQL parameters."""
import sqlite3

from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(error=None):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    get_db().execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            email TEXT NOT NULL,
            glucose REAL NOT NULL CHECK(glucose > 0),
            haemoglobin REAL NOT NULL CHECK(haemoglobin > 0),
            cholesterol REAL NOT NULL CHECK(cholesterol > 0),
            remarks TEXT,
            review_status TEXT NOT NULL
                CHECK(review_status IN ('unavailable', 'complete', 'failed'))
        )
    """)
    get_db().commit()


def list_patients():
    return get_db().execute("SELECT * FROM patients ORDER BY id").fetchall()


def get_patient(record_id):
    return get_db().execute("SELECT * FROM patients WHERE id = ?", (record_id,)).fetchone()


def save_patient(data, remarks, status, record_id=None):
    values = tuple(data[key] for key in (
        "full_name", "date_of_birth", "email", "glucose", "haemoglobin", "cholesterol"
    )) + (remarks, status)
    connection = get_db()
    with connection:
        if record_id is None:
            cursor = connection.execute("""
                INSERT INTO patients
                (full_name, date_of_birth, email, glucose, haemoglobin, cholesterol,
                 remarks, review_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, values)
            return cursor.lastrowid
        connection.execute("""
            UPDATE patients SET full_name=?, date_of_birth=?, email=?, glucose=?,
                haemoglobin=?, cholesterol=?, remarks=?, review_status=? WHERE id=?
        """, values + (record_id,))
    return record_id


def delete_patient(record_id):
    with get_db() as connection:
        connection.execute("DELETE FROM patients WHERE id = ?", (record_id,))
