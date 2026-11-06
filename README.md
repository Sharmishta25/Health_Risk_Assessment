# blood-test-risk-review

Task 2 take-home project using Flask, Jinja, plain CSS, and Python's built-in
`sqlite3`. Patient CRUD, server validation, persistent storage, and an injectable
Gemini REST integration are implemented. Configure your own local API key before
creating records. Failed predictions leave the database unchanged.

## Setup (Windows PowerShell)

After cloning your repository, open PowerShell in its root directory (the folder
containing `requirements.txt`). These commands work regardless of clone location:

Use Python 3.10 or newer.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad.exe .env
```

In the local editor, set `GEMINI_API_KEY` to your key from
[Google AI Studio](https://aistudio.google.com/apikey). Keep it out of chat and
screenshots. Save and close the editor, then run:

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app run
```

Open http://127.0.0.1:5000. Using the environment's Python directly avoids needing
to change PowerShell execution policy or activate a script.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

## Small project layout

- `app/__init__.py`: `create_app`, patient list, create/edit, delete confirmation,
  and POST review retry routes. Successful writes redirect to the list.
- `app/db.py`: `get_db`, `init_db`, `save_patient`, `delete_patient`; parameterized
  sqlite3 queries, auto-generated IDs, and request-scoped connections.
- `app/validation.py`: `validate_patient` returns cleaned values and all field
  errors without side effects. DOB is ISO in storage and DD/MM/YYYY on screen.
- `app/provider.py`: `GeminiProvider` sends lab values and units to Gemini;
  `parse_response` validates output; `review_patient` provides the injectable boundary.
- `app/templates/`, `app/static/`: Jinja screens and plain CSS.
- `instance/`: local database, excluded from Git.
- `tests/`: unittest checks; all provider responses and HTTP calls are mocked.
- `docs/IMPLEMENTATION_CHECKLIST.md`: requirement mapping and design decisions.
- `tests/fixtures/validation_cases.csv`: ten equivalent synthetic validation cases.
- `local/`: ignored original table and recording checklist on this machine only.
- `PROMPTS_USED.md`: published prompt log in order, with explicitly marked privacy
  redactions; exact original prompts remain ignored in `local/PROMPTS_USED_VERBATIM.md`.
- `docs/RECORDING_AND_WALKTHROUGH.md`: recording outline and exact functions to read.

The local database is created automatically at `instance/patients.sqlite3`.
Invalid submissions return HTTP 422 with all field errors and submitted values;
they neither write data nor call the provider. Identical entries are allowed and
managed by ID. Delete GET shows confirmation; only POST deletes.

Tests use synthetic data; the recording uses the unchanged original table from
your local PDF/checklist. Original names and emails are excluded from repository
source. The brief omits lab units:
the explicit demo assumptions are mg/dL for glucose/cholesterol and g/dL for
haemoglobin. Fasting status is unspecified. These assumptions appear on screen
and the units are passed to the provider. No fasting status is inferred or sent.
Remarks are read-only, escaped, and presented with
a non-diagnostic notice.

## Provider boundary

`create_app` loads `.env` without overriding existing environment variables.
`GEMINI_API_KEY` is required for predictions. `GEMINI_MODEL` defaults to
`gemini-flash-latest`; it is a moving alias, so set an available pinned model ID
if reproducibility is needed. `GEMINI_TIMEOUT_SECONDS` defaults to 30 and must be
above 0 and at most 120. Restart Flask after changing configuration.
Only `.env.example` belongs in Git; real `.env` files are ignored. Databases,
journals, original assignment files, recordings, and private local data are ignored.

The server POSTs to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
with the key in the `x-goog-api-key` header, JSON `systemInstruction`, `contents`,
and `generationConfig`. Only glucose, haemoglobin, cholesterol, their units, and
review instructions are sent. Name, DOB, email, and clinical history are excluded.
Instructions request cautious, concise possible patterns without diagnosis,
treatment, or invented context. This prompt cannot guarantee clinical accuracy.

The adapter requires one candidate with `finishReason: STOP` and nonempty text
in `content.parts` (at most 5,000 characters). Thought parts are excluded.
Blocked/truncated output, malformed JSON, timeouts and HTTP errors all fail safely.
No raw provider errors or keys are shown or logged. No fake fallback is used.

Provider success happens **before** INSERT/UPDATE. Failure returns HTTP 503 and
preserves the entered form values; use **Retry save**. Existing records and old
remarks remain unchanged after failed edits/reviews. Lab changes regenerate
remarks; name/DOB/email-only changes retain them. Legacy unavailable/failed rows
can use POST Retry review. Invalid input returns 422 before any provider call.

Tests inject `REVIEW_PROVIDER`, a callable taking a lab dictionary with units and
returning text. The public app always uses the real Gemini adapter.

Official references checked for this integration:
[authentication/quickstart](https://ai.google.dev/gemini-api/docs/quickstart),
[generateContent request and response](https://ai.google.dev/api/generate-content),
[model configuration](https://ai.google.dev/gemini-api/docs/models), and
[latest aliases](https://developers.googleblog.com/en/continuing-to-bring-you-our-latest-models-with-an-improved-gemini-2-5-flash-and-flash-lite-release/).

## Verification

`python -m unittest discover -v` currently runs 19 tests covering CRUD, persistence,
independent duplicates, ten equivalent synthetic rows, validation boundaries, submitted
value preservation, missing IDs, escaped output, parameterized values, and review
success, failure atomicity, unavailable configuration, HTTP errors/timeouts,
and empty/malformed/blocked responses. Seven original rows pass validation; rows 2,
4, and 8 fail. Tests use temporary databases, leaving the demo database unseeded.
The original table is not a test fixture and is not seeded into the app.

## Fresh recording database

Stop any server on port 5000 with Ctrl+C. From the project root in PowerShell:

```powershell
$env:HEALTH_REVIEW_DATABASE = Join-Path $PWD ('instance/demo-' + [guid]::NewGuid().ToString('N') + '.sqlite3')
if (Test-Path -LiteralPath $env:HEALTH_REVIEW_DATABASE) { throw 'Choose a new database path.' }
Write-Output $env:HEALTH_REVIEW_DATABASE
.\.venv\Scripts\python.exe -m flask --app app:create_app run
```

This creates an empty schema, never inserts data, and preserves existing databases.
Open http://127.0.0.1:5000 and confirm **0 saved records**. Keep using the same
PowerShell terminal/environment for the whole recording, including restarts.
Do not rerun the GUID command partway through: it selects another empty database.
If using another terminal, set `HEALTH_REVIEW_DATABASE` to the exact printed path.
Unset this override later with `Remove-Item Env:HEALTH_REVIEW_DATABASE` to return
to `instance/patients.sqlite3`; this removes only the environment variable.

Open the ignored `local/RECORDING_CHECKLIST.md` beside the app. Attempt all ten
rows manually in order, unchanged. A fresh clone does not include this private
file: use your original PDF to prepare it locally and keep it under `local/`.
Rows 2, 4, and 8 must be rejected. Retry prediction errors without changing input.
If all seven valid attempts succeed, the list must show **7 saved records**.

Before editing/deleting, stop the server with Ctrl+C and verify persisted data:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_demo seven --database "$env:HEALTH_REVIEW_DATABASE"
.\.venv\Scripts\python.exe -m flask --app app:create_app run
```

The verifier opens SQLite read-only, checks exact source inputs and completed
remarks, verifies separate IDs for attempts 1 and 6, and saves an ignored local
baseline beside the database. It never seeds or fixes records. It fails if the
seven rows are not present. Complete missing successful saves before continuing.

In a fresh ordered run, accepted attempts 1, 3, 5, 6, 7, 9, 10 have IDs 1-7.
Confirm actual IDs on screen and in verifier output. Edit **ID 1 only**, changing
only its email to `gokul@infocare.com`. Save, refresh, and show unchanged Remarks.
Stop the server and verify the email is persisted and all other values unchanged:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_demo edited --database "$env:HEALTH_REVIEW_DATABASE" --edited-id 1
.\.venv\Scripts\python.exe -m flask --app app:create_app run
```

Now delete **ID 7 only** using its Delete link and confirmation button, leaving
the edited record and both duplicate entries present. Show **6 saved records**
after redirect. Stop the server, verify, then restart and show the list again:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_demo six --database "$env:HEALTH_REVIEW_DATABASE" --edited-id 1 --deleted-id 7
.\.venv\Scripts\python.exe -m flask --app app:create_app run
```

If your actual IDs differ, substitute the confirmed IDs consistently; do not
delete extra records to force the count. The checks compare against the baseline,
so extra writes or changes fail verification. See
[the recording outline and interview walkthrough](docs/RECORDING_AND_WALKTHROUGH.md).

## Live verification (separate from mocked tests)

No successful live request has been verified yet. After configuring your key,
run this in a second PowerShell terminal from the project directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_live_gemini
```

This explicitly calls the real API through Flask's create form route with a
synthetic contact and labs 155 mg/dL, 12.5 g/dL, 265 mg/dL. It uses a temporary
SQLite database, checks the saved result and list rendering, and prints live
success only if all checks pass. It neither mocks the provider nor changes the
normal app database. It may consume API quota. On failure it prints a safe error.

For visible browser verification, open http://127.0.0.1:5000/patients/new and enter
`Synthetic Review`, `01/01/1990`, `synthetic@example.com`, `155`, `12.5`, `265`.
Save, confirm Remarks appears in the list, and refresh to confirm persistence.
Only lab values/units and instructions are sent to Google. This browser action
creates a synthetic record in the normal app database. A completed live check
must be reported separately from the mocked test results.

Run this as a local take-home demo. Authentication and CSRF protection have not
been implemented; add them before exposing write routes to other users.

Recruiter correspondence, candidate information, video recording, and submission
are handled by the user. The source repository is
[Sharmishta25/Health_Risk_Assessment](https://github.com/Sharmishta25/Health_Risk_Assessment).
The exact recording table and local recordings are intentionally excluded.
