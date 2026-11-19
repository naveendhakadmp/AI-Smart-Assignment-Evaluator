# GradePilot — College Assignment System

GradePilot is a local Flask application for assignment submissions, teacher-reviewed marks, and student grade history. It uses SQLite for records and an offline, rule-based grading suggestion; assignment files are not sent to an AI service.

The project is Python-based. There is no `package.json` or Node.js build step. The current Hindi readme is named `README_HINDI.md` (not `README_HI.md`).

## Run from source on Windows

1. Open this folder in VS Code.
2. In PowerShell, install the Python dependencies:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   If `.venv` does not exist, create it first with `py -m venv .venv`.
3. Start the development server:
   ```powershell
   python app.py
   ```
4. Visit `http://127.0.0.1:5000`. On first use, create the teacher account. Students can register from the sign-in page using their College ID, KID, department, semester, and password.

Do not use VS Code Live Server.

## Build the Windows application and installer

The packaging workflow uses PyInstaller to build a bundled, windowed application folder, and Inno Setup 6 to create a per-user Windows installer. Runtime records are stored in `%LOCALAPPDATA%\GradePilot` when running the installed executable, rather than in the read-only installation directory.

1. Install Python 3.10 or later. This project has been tested with Python 3.14.
2. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php).
3. From this project folder, run (the process-scoped bypass avoids changing your PowerShell execution policy):
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1
   ```
   The script installs dependencies from `requirements-build.txt`, runs the test suite, creates `dist\GradePilot\GradePilot.exe`, and compiles the installer.
4. The installer is written to `release\GradePilot-Setup.exe`. The default install location is the current user's LocalAppData Programs directory; administrator rights are not required.

To build only the application folder without compiling the installer:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1 -SkipInstaller
```

`GradePilot.spec` includes the Flask templates, static files, PyMuPDF resources, and application icon. `installer\GradePilot.iss` defines shortcuts and the per-user installer. The installer deliberately does not package `assignments.db` or `uploads`, so private student data is not embedded in a distributable. Source-mode data remains untouched. Back up the database and uploads before manually migrating them into `%LOCALAPPDATA%\GradePilot`; do not overwrite an existing installed database.

## Features

- Separate teacher and student sign-in with password hashing and role-based access.
- Student profiles with name, College ID, KID, department, and semester.
- Assignment PDF and image uploads (PDF, PNG, JPG, WEBP; up to 20 MB).
- Rule-based suggested marks; teachers can change and save final marks.
- Search/filter, per-student submission history, and protected assignment details.
- CSV and Excel (`.xlsx`) marksheet downloads.
- Installable PWA manifest, app icon, service worker, and an offline notice. Private records are not cached for offline browsing.
- Existing source SQLite records are retained when the app initializes or migrates its schema.

## Optional OCR

Selectable-text PDFs can be evaluated without additional system software. Scanned PDFs and assignment photos require the Tesseract OCR engine with English and Hindi language data. `pytesseract` is a Python wrapper and does not install the Tesseract executable. Tesseract was not found on the inspected machine, so OCR for scanned files/photos is unavailable until it is installed. OCR is not bundled by the current installer; if unavailable, the application reports that text could not be extracted.

The grading helper is a free, offline heuristic based on topic word matches, answer length, and basic structure. It is not a trained semantic AI model and cannot reliably assess meaning, factual correctness, handwriting, or plagiarism. A teacher must review all suggested marks.

## Storage and security notes

- Source-mode `assignments.db` and `uploads/` remain in this project folder. Installed-mode data and `gradepilot.log` are stored in `%LOCALAPPDATA%\GradePilot`.
- The initial teacher account is created during first-run setup. Student self-registration does not verify identity with a college service.
- Set a private, persistent `GRADEPILOT_SECRET_KEY` environment variable before hosting the app beyond a local demo.
- This local app is not hardened for public internet hosting. It does not provide email verification, password recovery, centralized account administration, or multi-device deployment controls. Use only approved student data and back up the database and uploads securely.

## Tests

Run the application tests from this folder:
```powershell
python -m unittest discover -s tests -v
```
