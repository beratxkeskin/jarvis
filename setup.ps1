Write-Host "====================================="
Write-Host "      J.A.R.V.I.S Windows Setup"
Write-Host "====================================="

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python bulunamadi. Python 3.11+ kurup tekrar deneyin."
    exit 1
}

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\pip.exe" install -r requirements.txt

if (-not (Test-Path "config\api_keys.json") -and (Test-Path "config\api_keys.example.json")) {
    Copy-Item "config\api_keys.example.json" "config\api_keys.json"
}

Write-Host ""
Write-Host "Kurulum tamamlandi. Baslatmak icin:"
Write-Host ".\.venv\Scripts\python.exe main.py"
