#Requires -Version 5.1
<#
  Первинне встановлення після git clone.
  Створює .venv і ставить базові залежності UI/API.
  Двигуни TTS (Robinhad / StyleTTS2 / RVC) — окремо, див. кінець скрипта.
#>
$ErrorActionPreference = "Stop"
$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

$Root = $PSScriptRoot
Set-Location $Root

Write-Host "=== Spag Voice Studio (SVS+) — встановлення ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue) -and -not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Python не знайдено. Встановіть Python 3.10+ (краще 3.11) з python.org" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "Створення .venv ..." -ForegroundColor Cyan
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 -m venv .venv
        if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
            python -m venv .venv
        }
    } else {
        python -m venv .venv
    }
}

$Python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "Не вдалося створити .venv" -ForegroundColor Red
    exit 1
}

Write-Host "Встановлення базових пакетів (FastAPI, numpy, ...)" -ForegroundColor Cyan
& $Python -m pip install --upgrade pip
& $Python -m pip install -r voice_studio\requirements.txt

New-Item -ItemType Directory -Force -Path "logs" | Out-Null
New-Item -ItemType Directory -Force -Path "models\robinhad" | Out-Null
New-Item -ItemType Directory -Force -Path "models\styletts2\voices" | Out-Null
New-Item -ItemType Directory -Force -Path "models\uploads\rvc" | Out-Null
New-Item -ItemType Directory -Force -Path "voice_studio\outputs" | Out-Null
New-Item -ItemType Directory -Force -Path "temp" | Out-Null

Write-Host ""
Write-Host "Базове середовище готове (Spag Voice Studio / SVS+)." -ForegroundColor Green
Write-Host ""
Write-Host "Далі (один раз, потрібен інтернет) встановіть хоча б один TTS-двигун:" -ForegroundColor Yellow
Write-Host "  powershell -File tools\setup_robinhad.ps1     # 5 дикторських голосів"
Write-Host "  powershell -File tools\setup_styletts2.ps1    # 30 стилів"
Write-Host "  powershell -File tools\setup_rvc.ps1          # опційно: свій голос RVC"
Write-Host ""
Write-Host "Запуск: start_voice_studio.bat"
Write-Host ""
