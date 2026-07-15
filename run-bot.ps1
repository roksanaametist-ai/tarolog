# TarGPT3 bot launcher (Windows)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

if (-not (Test-Path (Join-Path $Root "venv\Scripts\python.exe"))) {
    Write-Host "venv not found. Running setup.ps1 first..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File (Join-Path $Root "setup.ps1")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Starting bot..." -ForegroundColor Cyan
& (Join-Path $Root "venv\Scripts\python.exe") (Join-Path $Root "main.py")
