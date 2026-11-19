param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Push-Location $ProjectRoot
try {
    if (-not (Test-Path -LiteralPath $Python)) {
        & py -m venv .venv
        if ($LASTEXITCODE -ne 0) {
            throw "Could not create .venv. Install Python and retry."
        }
    }

    & $Python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency installation failed."
    }

    & $Python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed; packaging stopped."
    }

    & $Python -m PyInstaller --clean --noconfirm GradePilot.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed."
    }

    $AppExecutable = Join-Path $ProjectRoot "dist\GradePilot\GradePilot.exe"
    if (-not (Test-Path -LiteralPath $AppExecutable)) {
        throw "PyInstaller completed without creating $AppExecutable."
    }
    Write-Host "Application build created: $AppExecutable"

    if ($SkipInstaller) {
        Write-Host "Installer compilation skipped."
        return
    }

    $CompilerCandidates = @(
        $env:INNO_SETUP_COMPILER,
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    ) | Where-Object { $_ }
    $Compiler = $CompilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $Compiler) {
        throw "App EXE built, but Inno Setup ISCC.exe is missing. Install Inno Setup 6, then rerun this script."
    }

    & $Compiler (Join-Path $ProjectRoot "installer\GradePilot.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed."
    }
    Write-Host "Installer created in the release folder."
}
finally {
    Pop-Location
}
