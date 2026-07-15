# TarGPT3 landing launcher (Windows)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Landing = Join-Path $Root "landing"
Set-Location $Landing

$venvPython = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "venv not found. Run setup.ps1 from project root first." -ForegroundColor Red
    exit 1
}

& $venvPython -m pip install -q -r (Join-Path $Landing "requirements.txt")
$env:FLASK_DEBUG = "1"
Write-Host "Landing: http://127.0.0.1:5000" -ForegroundColor Cyan
& $venvPython (Join-Path $Landing "SiteApp.py")
