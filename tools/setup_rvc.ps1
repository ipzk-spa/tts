#Requires -Version 5.1
<#
  Опційне встановлення підтримки RVC (власний голос: .pth + .index).

  Ставиться в ОКРЕМЕ віртуальне середовище .venv-rvc, щоб важкі та іноді
  крихкі на Windows пакети (torch, fairseq, faiss) НЕ впливали на основну
  основну програму Spag Voice Studio, навіть якщо цей крок пропущено.

  Займає ~10-20 хвилин, ~3-4 ГБ (CUDA-збірка torch + tts-with-rvc). Ставиться
  CUDA-збірка torch (сумісна з драйверами NVIDIA GPU) — вона працює і без
  GPU (просто CPU), тому крок безпечний для всіх. Потрібен інтернет.
  Запускати один раз.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Встановлення RVC (окреме середовище .venv-rvc) ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv-rvc")) {
    python -m venv .venv-rvc
}

$Python = ".\.venv-rvc\Scripts\python.exe"

& $Python -m pip install --upgrade pip
& $Python -m pip install "setuptools<81"
Write-Host "-- torch (CUDA-збірка; звичайний 'pip install torch' на PyPI за замовчуванням дає CPU-only, тому індекс вказуємо явно) --" -ForegroundColor Cyan
& $Python -m pip install torch --index-url https://download.pytorch.org/whl/cu124
& $Python -m pip install tts-with-rvc edge-tts soundfile imageio-ffmpeg

Write-Host ""
Write-Host "RVC готовий. Перезапустіть Spag Voice Studio — гібрид стане доступним у UI." -ForegroundColor Green
