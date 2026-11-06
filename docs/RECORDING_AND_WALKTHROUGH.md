# Recording outline

The exact ten-row checklist is **local only**: `local/RECORDING_CHECKLIST.md`.
Its source CSV is `local/assignment_cases.csv`. Both are ignored, as is the
verbatim log at `local/PROMPTS_USED_VERBATIM.md`. The published `PROMPTS_USED.md`
marks its privacy redactions. Fresh clones intentionally contain synthetic test fixtures
only; use your original PDF to recreate a local checklist. Do not add originals,
screenshots, recordings, databases, or baseline snapshots to Git.

1. Open an empty demo database using README commands. Show zero saved records,
   unit assumptions, and read-only Remarks. Keep `.env` and keys off screen.
2. Attempt all ten rows, in printed order, from the local checklist. Do not alter
   invalid fields or insert rows using scripts. Explain the email error in row 2,
   impossible date in row 4, and both errors in row 8. Dotted dates are supported.
3. After each successful prediction, return to Add patient for the next row.
   On prediction failure, show the error and retry the unchanged form. Count only
   successful saves; do not re-submit a form that already redirected successfully.
4. Show seven saved records and their AI Remarks, if all seven valid attempts
   succeed. Show the two duplicate entries with distinct IDs before deletion.
   Run the read-only `seven` verification to capture a local baseline.
5. Edit exactly one saved record's email to `gokul@infocare.com`; leave its other
   inputs unchanged. Refresh, restart the server with the same database, and run
   the `edited` verification. Show the persisted email and unchanged Remarks.
6. Delete a different record by ID. Show confirmation first, submit once, and show
   the refreshed list with six records. Run `six` verification. Keep the edited
   record and both duplicate records so the video can still show them.
7. Walk through the functions below. Distinguish mocked tests from live requests.
   A failure is a demonstrated failure, never a claimed successful prediction.

# Interview walkthrough

| Concern | Exact file / function | Explain or demonstrate |
| --- | --- | --- |
| Start/config | `app/__init__.py:create_app` | dotenv, environment DB override, Gemini adapter, SQLite initialization; no seeding |
| Validation | `app/validation.py:validate_patient` | all errors collected; day-first slash/dot parsing; calendar/future checks; finite positive decimals; no side effects |
| Create/edit | `app/__init__.py:patient_form` | validation before review; review before write; failure returns 503 with input preserved; success redirects 303 |
| Lab-change check | `app/__init__.py:patient_form`, variable `clinical_changed` | compare cleaned numbers in `LAB_FIELDS`; only lab changes regenerate; email/DOB/name changes preserve Remarks |
| Persistence | `app/db.py:get_db`, `init_db`, `save_patient`, `list_patients` | per-request connection, REAL labs, ISO DOB, parameterized SQL, auto-generated ID; no unique email/name constraint |
| Deletion | `app/__init__.py:delete`, `app/db.py:delete_patient` | GET confirms, POST deletes exactly one ID |
| Payload/privacy | `app/provider.py:review_patient`, `GeminiProvider.__call__` | allowlist three labs and units; no name, DOB or email; cautious instructions |
| Request/config | `app/provider.py:GeminiProvider.from_environment`, `__call__` | API key header, configurable model, finite timeout, generateContent JSON; server-side only |
| Response/errors | `app/provider.py:parse_response`, `validate_remarks`, `PredictionError` | completed STOP output, nonempty bounded text; reject malformed/blocked/truncated data; safe HTTP/timeout messages |
| Retry | `app/__init__.py:retry_review`, `patient_form` | retry existing review or failed unsaved form; failure preserves DB |
| Screens | `app/templates/index.html`, `form.html`, `delete.html`; `app/static/style.css` | count, independent ID actions, field errors, escaped read-only remarks, deletion confirmation |
| Tests | `tests/test_patients.py`, `tests/test_provider.py`, `tests/test_demo_verification.py` | synthetic fixtures, temporary DBs, mocked HTTP; no real API claims |
| Live check | `scripts/verify_live_gemini.py:main` | real API via Flask form route, synthetic values, temporary DB |
| Recording verification | `scripts/verify_demo.py:verify_seven`, `verify_changes` | read-only DB checks; baseline captures rows and Remarks; no data insertion or correction |

Keep the explanation simple: form -> validate -> review if labs changed -> save ->
redirect -> list. For a live change, adjust one validation message or lab field
comparison, run the relevant tests, and explain the effect. JSON structure checks
and cautious prompting do not prove medical correctness. The app is a local demo
without authentication or CSRF protection, not a deployed patient system.
