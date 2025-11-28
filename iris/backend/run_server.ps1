# Run the backend server without activating the virtual environment
# Usage: From backend folder, run in PowerShell:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\run_server.ps1

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
# Load .env file into process environment so the backend sees GOOGLE_API_KEY, GOOGLE_MODEL, etc.
$envFile = Join-Path $PSScriptRoot ".env"
if (Test-Path $envFile) {
    Write-Output "Loading environment variables from $envFile"
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not [string]::IsNullOrWhiteSpace($line) -and -not $line.StartsWith('#')) {
            $parts = $line -split '=', 2
            if ($parts.Count -eq 2) {
                $name = $parts[0].Trim()
                $value = $parts[1].Trim().Trim('"')
                Write-Output "Setting env: $name"
                $env:$name = $value
            }
        }
    }
}
if (Test-Path $venvPython) {
    Write-Output "Using venv python: $venvPython"
    & $venvPython -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
} else {
    Write-Output ".venv python not found. Falling back to system python."
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}
