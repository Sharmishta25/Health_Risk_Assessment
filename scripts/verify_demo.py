"""Read-only demo DB verification; original inputs and snapshots stay local."""
import argparse
import csv
import json
import sqlite3
from pathlib import Path

from app.validation import FIELDS, validate_patient


def verify_seven(rows, cases):
    if len(rows) != 7:
        raise ValueError(f"Expected seven saved records; found {len(rows)}.")
    if len(cases) != 10:
        raise ValueError("Expected the complete ten-row local source table.")
    accepted = []
    for number, raw in enumerate(cases, 1):
        data, errors = validate_patient(raw)
        if bool(errors) != (number in (2, 4, 8)):
            raise ValueError(f"Unexpected validation outcome for source row {number}.")
        if not errors:
            accepted.append(data)
    for row, expected in zip(rows, accepted):
        if any(row[key] != expected[key] for key in FIELDS):
            raise ValueError(f"Record #{row['id']} differs from the ordered source table.")
        if row["review_status"] != "complete" or not row["remarks"] or not row["remarks"].strip():
            raise ValueError(f"Record #{row['id']} has no completed review.")
    # Accepted positions 0 and 3 correspond to original attempts 1 and 6.
    if rows[0]["id"] == rows[3]["id"] or any(
            rows[0][key] != rows[3][key] for key in FIELDS):
        raise ValueError("The two duplicate entries must have identical inputs and distinct IDs.")
    return rows[0]["id"], rows[3]["id"]


def verify_changes(rows, baseline, edited_id, deleted_id=None):
    if len(baseline) != 7 or len({row["id"] for row in baseline}) != 7:
        raise ValueError("Invalid seven-record baseline.")
    ids = {row["id"] for row in baseline}
    if edited_id not in ids or deleted_id is not None and (
            deleted_id not in ids or deleted_id == edited_id):
        raise ValueError("Choose existing IDs; delete a different record from the edited one.")
    expected = []
    for row in baseline:
        copy = dict(row)
        if row["id"] == edited_id:
            copy["email"] = "gokul@infocare.com"
            if row["email"] == copy["email"]:
                raise ValueError("Baseline already contains the requested email edit.")
        if row["id"] != deleted_id:
            expected.append(copy)
    if rows != expected:
        raise ValueError("Database differs from exactly one email edit and the requested deletion.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["seven", "edited", "six"])
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path("local/assignment_cases.csv"))
    parser.add_argument("--edited-id", type=int)
    parser.add_argument("--deleted-id", type=int)
    args = parser.parse_args()
    snapshot = Path(str(args.database) + ".baseline.json")
    try:
        with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = [dict(row) for row in connection.execute("SELECT * FROM patients ORDER BY id")]
        if args.stage == "seven":
            with args.source.open(newline="", encoding="utf-8") as source:
                duplicates = verify_seven(rows, list(csv.DictReader(source)))
            if snapshot.exists():
                raise ValueError("Baseline already exists. Use a fresh demo database for a new recording.")
            snapshot.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(f"PASS: seven persisted reviews; duplicate IDs {duplicates[0]} and {duplicates[1]} are distinct.")
        else:
            if args.edited_id is None or args.stage == "six" and args.deleted_id is None:
                raise ValueError("Supply --edited-id and, for six, --deleted-id.")
            baseline = json.loads(snapshot.read_text(encoding="utf-8"))
            verify_changes(rows, baseline, args.edited_id,
                           args.deleted_id if args.stage == "six" else None)
            print(f"PASS: {len(rows)} persisted rows; exact email edit verified; other retained fields/remarks unchanged.")
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print("Verification failed:", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
