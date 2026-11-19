# GradePilot — AI Smart Assignment Evaluator

GradePilot is a local Flask application for managing college assignment submissions. It extracts text from submitted PDFs or images, provides an **offline, rule-based suggested score**, and lets teachers review and save final marks. It also includes student accounts, submission history, and downloadable marksheets.

> **Important:** The score is a basic heuristic, not a trained AI model. It cannot reliably judge meaning, factual accuracy, or plagiarism. A teacher should review every suggested score.

## Features

- Separate teacher and student accounts with hashed passwords and role-based access.
- Assignment uploads in PDF, PNG, JPG/JPEG, and WEBP formats (up to 20 MB).
- Offline text extraction and rule-based suggested marks.
- Teacher review, final marks, student submission history, and protected assignment files.
- CSV and Excel (`.xlsx`) marksheet exports.
- Installable PWA assets and an offline notice.
- Optional OCR for scanned PDFs and photos when Tesseract is installed.
- Windows packaging scripts for a desktop application and installer.

## Requirements

- Python 3.10 or later.
- Dependencies listed in `requirements.txt`.
- For OCR of scanned documents or images: the Tesseract OCR application with English and Hindi language data. Tesseract is optional and is not installed by the Python package.

## Run from source on Windows

Open PowerShell in this project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000> in your browser. On first launch, create the teacher account. Students can register from the sign-in page.

The application binds to the local computer and is intended for local use or demonstration. Do not expose it directly to the public internet.

## Run the tests

```powershell
python -m unittest discover -s tests -v
```

## Build the Windows application

Install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then run this from PowerShell in the project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1
```

To build the application without compiling the installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_windows.ps1 -SkipInstaller
```

The script installs build dependencies, runs the tests, and creates the packaged application under `dist\GradePilot`. With Inno Setup installed, it also creates an installer under `release`.

## Local data and security

- Source-mode records are stored in `assignments.db`; uploaded assignments are stored in `uploads/`. These are local runtime data and are intentionally excluded from Git.
- The packaged application stores its data under `%LOCALAPPDATA%\GradePilot`.
- Before any deployment beyond local use, set a private, persistent `GRADEPILOT_SECRET_KEY` environment variable. Never commit passwords, API keys, `.env` files, student records, or uploaded assignments.
- This project is not hardened for public hosting and does not provide identity verification, password recovery, or centralized account administration. Use only approved student data and protect backups.

## Project layout

```text
app.py                  Flask application and routes
grader.py               Text extraction and offline grading heuristic
launcher.py             Packaged-app launcher
templates/              HTML templates
static/                 CSS, JavaScript, icons, and PWA assets
tests/                  Application tests
installer/              Inno Setup installer definition
GradePilot.spec         PyInstaller build configuration
```
