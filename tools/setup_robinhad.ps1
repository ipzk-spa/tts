#Requires -Version 5.1
<#
  Встановлення найякіснішого голосу — robinhad/ukrainian-tts (ESPNet VITS +
  HiFiGAN, той самий рушій, що на huggingface.co/spaces/robinhad/ukrainian-tts).

  Навчений спеціально на якісних дикторських записах
  (Тетяна/Микита/Лада/Дмитро/Олекса).

  Ставиться в ОКРЕМЕ віртуальне середовище .venv-robinhad (torch + espnet —
  важкі пакети), щоб НЕ впливати на основну програму.

  Займає ~10-25 хвилин, ~3-5 ГБ (CUDA-збірка torch + espnet + модель ~430 МБ).
  Ставиться CUDA-збірка torch (сумісна з драйверами NVIDIA GPU) — вона працює
  і без GPU (просто використовується CPU), тому цей крок безпечний для всіх.
  Потрібен інтернет. Запускати один раз.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Встановлення найякіснішого голосу (окреме середовище .venv-robinhad) ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv-robinhad")) {
    py -3.11 -m venv .venv-robinhad
}

$Python = ".\.venv-robinhad\Scripts\python.exe"

& $Python -m pip install --upgrade pip
Write-Host "-- torch (CUDA-збірка; звичайний 'pip install torch' на PyPI за замовчуванням дає CPU-only, тому індекс вказуємо явно) --" -ForegroundColor Cyan
& $Python -m pip install torch --index-url https://download.pytorch.org/whl/cu124
Write-Host "-- допоміжні пакети --" -ForegroundColor Cyan
& $Python -m pip install "typeguard<3" "scipy<1.12.0" "ukrainian-word-stress==1.1.0"
& $Python -m pip install "git+https://github.com/savoirfairelinux/num2words.git@3e39091d052829fc9e65c18176ce7b7ff6169772"
& $Python -m pip install "git+https://github.com/egorsmkv/ukrainian-accentor.git@5b7971c4e135e3ff3283336962e63fc0b1c80f4c"
Write-Host "-- espnet (найважчий пакет, потерпіть) --" -ForegroundColor Cyan
& $Python -m pip install "espnet==202301"
Write-Host "-- ukrainian-tts (robinhad) --" -ForegroundColor Cyan
& $Python -m pip install "git+https://github.com/robinhad/ukrainian-tts.git"

Write-Host ""
Write-Host "-- Завантаження моделі (~430 МБ) у models\robinhad, прогрів --" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "models\robinhad" | Out-Null
& $Python -c "import torch; from ukrainian_tts.tts import TTS; d='cuda' if torch.cuda.is_available() else 'cpu'; print('Device:', d); TTS(cache_folder='models/robinhad', device=d); print('OK')"

Write-Host ""
Write-Host "Robinhad готовий. Перезапустіть Spag Voice Studio — двигун з'явиться в UI." -ForegroundColor Green
