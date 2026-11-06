# Implementation checklist

Source: all three pages of `Task 2 - AI Growth Python Skills.pdf`, including
rows 9 and 10 and the edit/delete instructions on page 3.

- [x] Inspect workspace and all PDF pages; create small runnable scaffold.
- [x] Add ignore rules, prompt log, exact assignment cases, and local Git.
- [x] Implement validation and SQLite schema/queries.
- [x] Implement patient list, create/edit form, and delete confirmation (all fields are visible in the list; no separate detail screen).
- [x] Add Gemini REST adapter, safe error display, and retry.
- [ ] Verify a real successful Gemini request after local key configuration.
- [ ] Run requirement tests and enter all ten original rows through the UI.
- [x] Prepare a recording guide and function-level interview walkthrough.

## Requirement to screen/test mapping

| Requirement | Planned screen or verification |
| --- | --- |
| Python backend; simple clean UI | Flask routes, shared Jinja layout, plain CSS; smoke check, keyboard navigation, empty state, readable errors |
| Name, DOB, email, glucose, haemoglobin, cholesterol | Create/edit form; required fields and redisplay submitted values after errors |
| AI-generated remarks | Patient list; escaped read-only remarks, provider status and non-diagnostic notice |
| Create | New-patient form; valid row stored with distinct integer ID |
| Read | List all record fields; test empty and populated list |
| Update | Pre-filled edit form; change one email to `gokul@infocare.com`, verify persistence |
| Delete | Confirmation screen and POST action; delete one ID and show refreshed list |
| Basic validation | Field errors for missing name, invalid email, impossible/future DOB, non-numeric/non-finite/negative blood values; no provider call on invalid submission |
| Persistent storage | sqlite3, parameterized SQL, local `instance/` database; reopen connection/app and verify records survive |
| External AI/health API | Provider adapter receives validated blood values and necessary context; mock success test plus separately configured real API demonstration |
| Possible condition/risk in remarks | Provider response parsed and checked for nonempty bounded text; visible result and status; never claim a definitive diagnosis |
| Exact supplied rows | Enter ignored `local/assignment_cases.csv` rows 1-10 manually without changes; repository tests use synthetic equivalents |
| Video: CRUD, error explanations, API walkthrough | User recording; future demo guide maps actions to routes, validation, SQLite and provider code |
| Understand/customize code; maintainability | Small modules and unittest suite; manual code review and live-change rehearsal |
| GitHub organization and secret removal | Audit proposed files, prompt-log redactions, and history before authorized publication; private originals and databases remain ignored |
| Candidate details, recruiter contact, uploads/submission | User-owned tasks; no personal-data collection, email, remote, push, or sharing automation |

## Decisions and acceptance cases

**Dates:** The prose requires `dd/mm/yyyy`, but every sample uses `dd.mm.yyyy`.
Accept exactly those two day-first formats with four-digit years and consistent
separators. Explain both on the form, display slashes, store ISO `yyyy-mm-dd`.
Preserve the ignored local original CSV unchanged. Parse calendar dates, then compare
against today's date (injectable in tests). Reject impossible dates and future
dates; do not reinterpret them or convert them into nearby valid dates.

**Duplicates:** Allow row 6 as a separate record; uniqueness is the database ID,
not name/email. The specification does not prohibit duplicates. Editing or
deleting one duplicate record must leave the other untouched. Accidental browser
refresh after a successful POST should not resubmit (redirect after POST).

**Provider errors:** Gemini is configured through environment variables and an
ignored local `.env`. Use a finite request timeout and validate HTTP status,
response structure, completion reason, and nonempty text. Complete the prediction
before writing data: any prediction failure returns a safe retryable error and
leaves the database unchanged. Preserve form input for Retry save. Lab edits
regenerate remarks; name/DOB/email-only edits preserve them. Legacy unavailable
or failed rows can retry review with POST. No exception payloads, keys, fabricated
predictions, or mocked output appear in public app remarks. Only the three labs,
their assumed units, and cautious instructions leave the app; no name, DOB,
email, or fasting status is sent. Normal tests mock provider calls.

**Units/context:** PDF gives no units or fasting status. The form documents demo
assumptions: mg/dL for glucose/cholesterol and g/dL for haemoglobin. Fasting
context is unspecified. Do not infer
clinical thresholds or diagnoses from unlabeled numbers.

| Row | Expected validation outcome before provider call |
| --- | --- |
| 1 | Accept; dotted DOB supported |
| 2 | Reject email (missing dotted domain) |
| 3 | Accept |
| 4 | Reject `31.11.2001` (November has 30 days) |
| 5 | Accept |
| 6 | Accept separate duplicate of row 1 |
| 7 | Accept |
| 8 | Reject future DOB and malformed email; display both errors |
| 9 | Accept; page 3 continuation |
| 10 | Accept; page 3 continuation |

With a test date of 2026-11-06, seven rows pass validation, three fail, and
deleting one accepted record leaves six (when all predictions succeed). Provider
outages leave the database unchanged and preserve input for retry. Tests cover slash dates, mixed
separators, leap dates, today's DOB, tomorrow's DOB, SQL parameters, missing IDs,
duplicate isolation, persisted AI status, escaped remarks, and provider failures.

## Scope of this step

CRUD, validation, SQLite persistence, read-only remarks, Gemini integration, safe
errors, and POST retry are implemented. Mocked tests cover all
ten equivalent synthetic cases through Flask's test client. Manual UI entry and live
verification remain pending local key configuration. No fake fallback is used.
Recruiter contact and candidate submission remain user-owned. Source publication
is authorized separately; it excludes original input tables and private data.
