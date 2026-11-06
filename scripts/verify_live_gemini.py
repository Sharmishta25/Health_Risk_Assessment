"""Explicit live API check through Flask routes using a temporary database."""
import tempfile
from pathlib import Path

from app import create_app, db


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = create_app({"DATABASE": str(Path(folder) / "live.sqlite3")})
        client = app.test_client()
        response = client.post("/patients/new", data={
            "full_name": "Synthetic Review", "date_of_birth": "01/01/1990",
            "email": "synthetic@example.com", "glucose": "155",
            "haemoglobin": "12.5", "cholesterol": "265",
        })
        if response.status_code != 303:
            # Show only the controlled error text, never credentials or HTTP bodies.
            from html.parser import HTMLParser

            class ErrorText(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.in_alert = False
                    self.messages = []

                def handle_starttag(self, tag, attrs):
                    if tag == "p" and dict(attrs).get("role") == "alert":
                        self.in_alert = True

                def handle_endtag(self, tag):
                    if tag == "p":
                        self.in_alert = False

                def handle_data(self, data):
                    if self.in_alert:
                        self.messages.append(data)

            parser = ErrorText()
            parser.feed(response.get_data(as_text=True))
            print("LIVE VERIFICATION FAILED:", " ".join(parser.messages))
            return 1
        with app.app_context():
            rows = db.list_patients()
            if len(rows) != 1 or rows[0]["review_status"] != "complete" or not rows[0]["remarks"]:
                print("LIVE VERIFICATION FAILED: saved review not found.")
                return 1
            remarks = rows[0]["remarks"]
        from markupsafe import escape
        if str(escape(remarks)) not in client.get("/").get_data(as_text=True):
            print("LIVE VERIFICATION FAILED: saved remarks did not render.")
            return 1
        print("LIVE SUCCESS: real Gemini request through Flask; remarks saved and rendered.")
        print("Remarks:", remarks)
        print("Temporary verification database removed on exit; normal app database unchanged.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
