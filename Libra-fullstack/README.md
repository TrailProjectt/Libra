# Legal Workspace v4 — working local app

## Run on Windows
1. Install Python 3.10 or newer if needed. Select "Add Python to PATH" in the installer.
2. Right-click the ZIP > Extract All. Do not run from inside the ZIP.
3. Open `libra-fullstack` and double-click `START_WINDOWS.bat`.
4. Keep the terminal open. The app opens at http://127.0.0.1:8000.
5. Click Create account, enter your name/email, and choose a password of at least 10 characters.
6. Sign out and use Sign in to reopen your records.

No pip, npm, Node.js, API keys or separate database installation required.
Do not double-click static/index.html: this version runs through its server.
If Python is already installed, open a terminal in this folder and run `py -3 app.py` on Windows or `python3 app.py` on macOS/Linux.
If the browser does not open, enter http://127.0.0.1:8000 manually.
If port 8000 is occupied, close your previous app/server instance.

## Try the complete case workflow
1. Clients > New client > Save to database.
2. Cases > New case. Choose the client, enter the matter, case number, court, date, stage and notes. Save.
3. Click Open beside the case.
4. Click New evidence. Enter its title, type, date and description. Choose an existing attachment or upload a new file up to 1 MB. Save.
5. Reopen the case to inspect its evidence. Download the attached file.
6. Click Record hearing. Enter the hearing date, stage, notes and next date. Save.
7. The hearing appears in case history, and the next date changes in Cases, Hearings and Calendar.
8. Edit the case or evidence from their detail screens.
9. Close the server, start it again, sign in, and verify your records are still present.

## Other working workflows
- Signup for multiple local accounts; each account has separate records.
- Sign in/out and change your password from Settings.
- Add/edit clients; renaming a client updates linked case names.
- Search and filter active/closed matters; export filtered records as CSV.
- Add/edit/delete tasks and mark completed/reopened.
- Add/edit/delete appointments with date, time and location.
- View hearings, appointments and task deadlines in the monthly calendar.
- Upload, download and delete database-stored documents.
- Add/edit/delete fee records; mark paid/unpaid; download a text fee record.
- View calculated practice reports and export report JSON.
- View current/past hearing and task reminders inside the app.
- Download an .ics hearing calendar event.
- Export and restore JSON workspace backups.
- Add fictional sample data from Settings without replacing existing records.

## Save behaviour and record relationships
The interface reports success only after the server confirms a committed database save.
A failed save leaves the previously saved workspace unchanged and shows an error.
A second tab cannot silently overwrite a newer revision: reload after exporting any needed backup.
Evidence must link to an existing case. Uploaded attachments and evidence are saved together.
Deleting a case also deletes its evidence records; attachments remain in Document Vault.
Deleting an attachment removes its link from evidence records.
A client with linked cases cannot be deleted until its cases are reassigned or deleted.
Client names must be unique within an account.

## Database / updating from v2
The database is created at `data/workspace.sqlite3` on first launch.
Cases, clients, evidence, uploaded file bytes, hearings, tasks, appointments and fees are stored there.
Stop the server and copy the entire data folder for a full account/database backup.
Settings > Export backup contains workspace records and documents, not login credentials.
Keep your password securely: there is no email password-reset service.

To keep your v2 records: stop the old server, copy its data folder into this extracted libra-fullstack folder, then start the new version. Do not overwrite your database with an empty folder.
The existing account remains valid. Missing client-directory entries from older cases are created as placeholders; edit their contact details in Clients.
New accounts start with 31 fictional sample records: 5 clients, 6 cases with hearing history, 4 evidence records, 4 downloadable sample documents, 5 tasks, 3 appointments and 4 invoices. Hearing and task dates are relative to the date you sign up. Existing accounts: Settings > Add sample data. Adding again does not duplicate existing sample records.

## Included source files
- sample_data.py: fictional sample record generator.
- app.py: Python server, SQLite persistence, account/session handling and validation.
- static/index.html: application shell.
- static/app.js: screens, real form submissions, record relationships, calendar and exports.
- static/style.css: responsive layout, redesigned authentication and dark navigation.
- START_WINDOWS.bat: launcher.
- tests/test_app.py: isolated backend regression tests.

## Verification
Passed backend checks: signup/login/logout, two-account data isolation, duplicate signup rejection, request-origin/CSRF checks, all record collections, evidence links and attachments, hearing history, failed-data rejection, conflicting edits, password changes, static assets and persistence after restart.
Passed scripted interface checks: all 14 screens; actual form handlers for client/case/evidence creation and file attachment; case editing; hearing updates; task completion; payment status; save failure rollback; deletion cleanup; login/signup rendering.
Visual browser testing was not available in the build environment.
To rerun backend tests, stop the app first and run `python tests/test_app.py`. Tests use a temporary database and leave your data untouched.

## Scope
Independent Libra-inspired application, with working local database workflows rather than an exact reproduction of private Libra screens.
Single-machine app with separate local accounts; no team sharing or hosted multi-user deployment.
Passwords use salted PBKDF2. Sessions expire after 8 hours and reset on server restart.
The server listens on 127.0.0.1 only. Database file contents are not encrypted at rest.
Files have a 1 MB limit each; saves/imports have a 20 MB total request limit.

External integrations are not included: live eCourts feeds, live court room/item board, WhatsApp/email/push delivery, licensed judgments, AI legal research, payment collection, bar council management and automatic Google/Apple sync.
The UI links to official research websites; it does not claim a built-in legal database.
Fee downloads are text records, not compliant tax invoices.
Exact Libra screen matching needs your screenshots or a screen recording.

References: https://libra.lawyer/products/libra and https://play.google.com/store/apps/details?id=com.vakilsearch.libra
