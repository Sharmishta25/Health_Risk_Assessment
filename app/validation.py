"""Validate all fields together without side effects."""
import math
import re
from datetime import date, datetime

FIELDS = ("full_name", "date_of_birth", "email", "glucose", "haemoglobin", "cholesterol")
LAB_FIELDS = ("glucose", "haemoglobin", "cholesterol")
EMAIL = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+"
)


def validate_patient(values, today=None):
    today = today or date.today()
    data = {key: values.get(key, "").strip() for key in FIELDS}
    errors = {}
    if not data["full_name"]:
        errors["full_name"] = "Enter a full name."
    email = data["email"]
    local = email.partition("@")[0]
    if (len(email) > 254 or not EMAIL.fullmatch(email) or len(local) > 64
            or local.startswith(".") or local.endswith(".") or ".." in local):
        errors["email"] = "Enter a valid email address with a dotted domain."
    raw_date = data["date_of_birth"]
    try:
        if not re.fullmatch(r"\d{2}([/.])\d{2}\1\d{4}", raw_date, flags=re.ASCII):
            raise ValueError
        dob = datetime.strptime(raw_date.replace(".", "/"), "%d/%m/%Y").date()
        if dob > today:
            errors["date_of_birth"] = "Date of birth cannot be in the future."
        else:
            data["date_of_birth"] = dob.isoformat()
    except ValueError:
        errors["date_of_birth"] = "Enter a real date as DD/MM/YYYY or DD.MM.YYYY."
    for key in LAB_FIELDS:
        try:
            value = float(data[key])
            if not math.isfinite(value) or value <= 0:
                raise ValueError
            data[key] = value
        except (ValueError, OverflowError):
            errors[key] = "Enter a finite positive number (decimals allowed)."
    return data, errors
