# TarGPT3 dependency setup (Windows)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Find-Python {
    foreach ($name in @("py", "python3", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python not found." -ForegroundColor Red
    Write-Host "Install Python 3.11+ from https://www.python.org/downloads/"
    Write-Host "Enable 'Add Python to PATH' during install."
    exit 1
}

Write-Host "Python: $python" -ForegroundColor Cyan

$venv = Join-Path $Root "venv"
if (-not (Test-Path $venv)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    & $python -m venv $venv
}

$venvPython = Join-Path $venv "Scripts\python.exe"
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $Root "requirements.txt")

$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Root ".env.example") $envFile
    Write-Host "Created .env from .env.example - fill in your tokens." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Running checks..." -ForegroundColor Yellow
& $venvPython (Join-Path $Root "scripts\verify_setup.py")
$code = $LASTEXITCODE

Write-Host ""
Write-Host "Activate venv:" -ForegroundColor Green
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "Run bot:" -ForegroundColor Green
Write-Host "  python main.py"

exit $code
