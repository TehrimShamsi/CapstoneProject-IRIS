# Run the backend server without activating the virtual environment
# Usage: From backend folder, run in PowerShell:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\run_server.ps1

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-Output "Using venv python: $venvPython"
    & $venvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
} else {
    Write-Output ".venv python not found. Falling back to system python."
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}
