#Requires -Version 5.1
<#
  Встановлення другого якісного голосу — StyleTTS2 Ukrainian
  (patriotyk/styletts2-ukrainian, той самий рушій, що на
  huggingface.co/spaces/patriotyk/styletts2-ukrainian).

  30 дикторських стилів голосу (значно більше за 5 голосів Robinhad),
  керування темпом мовлення, підтримка ручного наголосу "+".

  Ставиться в ОКРЕМЕ віртуальне середовище .venv-styletts2 (свої версії
  torch/transformers, які інакше конфліктували б з .venv-robinhad), щоб
  НЕ впливати на основну програму чи інші двигуни.

  Займає ~20-35 хвилин, ~5-6 ГБ (CUDA-збірка torch/torchaudio + модель +
  30 файлів стилів). Ставиться CUDA-збірка torch (сумісна з драйверами
  NVIDIA GPU) — вона працює і без GPU (просто CPU), тому крок безпечний
  для всіх. Потрібен інтернет. Запускати один раз.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== Встановлення другого якісного голосу StyleTTS2 (окреме середовище .venv-styletts2) ===" -ForegroundColor Cyan

if (-not (Test-Path ".venv-styletts2")) {
    py -3.11 -m venv .venv-styletts2
}

$Python = ".\.venv-styletts2\Scripts\python.exe"

& $Python -m pip install --upgrade pip
Write-Host "-- torch/torchaudio (CUDA-збірка; звичайний 'pip install torch' на PyPI за замовчуванням дає CPU-only, тому індекс вказуємо явно) --" -ForegroundColor Cyan
& $Python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
Write-Host "-- transformers/ctranslate2/аудіо-утиліти --" -ForegroundColor Cyan
& $Python -m pip install "transformers>=5.0.0" ctranslate2 sentencepiece accelerate "numpy<2" soundfile librosa scipy einops einops_exts munch pyyaml huggingface_hub
Write-Host "-- ukrainian-word-stress / ipa-uk (наголос і IPA-транскрипція) --" -ForegroundColor Cyan
& $Python -m pip install "git+https://github.com/patriotyk/ukrainian-word-stress.git"
& $Python -m pip install "git+https://github.com/patriotyk/ipa-uk.git"
Write-Host "-- styletts2-inference (сам рушій синтезу) --" -ForegroundColor Cyan
& $Python -m pip install "git+https://github.com/patriotyk/styletts2-inference@209352700cf703a05ff94501290095dd9072fd5f"

Write-Host ""
Write-Host "-- Завантаження 30 файлів стилів голосу (voices/*.pt) у models\styletts2\voices --" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "models\styletts2\voices" | Out-Null
& $Python "$PSScriptRoot\_download_styletts2_voices.py"

Write-Host ""
Write-Host "-- Прогрів: завантаження мультиспікерної моделі у кеш HuggingFace --" -ForegroundColor Cyan
& $Python -c "import torch; from styletts2_inference.models import StyleTTS2; d='cuda' if torch.cuda.is_available() else 'cpu'; print('Device:', d); StyleTTS2(hf_path='patriotyk/styletts2_ukrainian_multispeaker', device=d); print('OK')"

Write-Host ""
Write-Host "StyleTTS2 готовий. Перезапустіть Spag Voice Studio — 30 стилів з'являться в UI." -ForegroundColor Green
