# Spag Voice Studio — модуль програми

Веб-інтерфейс + Python API для локального українського TTS.

## Запуск

З кореня репозиторію:

```
start_voice_studio.bat
```

або `powershell -File start_voice_studio.ps1`.

Після `git clone` спочатку:

```
powershell -File install.ps1
powershell -File tools\setup_robinhad.ps1
```

UI: `http://127.0.0.1:7900`  
Лог: `logs\errors.txt`

## Двигуни

| Двигун | Голосів | Встановлення |
|--------|---------|--------------|
| Robinhad | 5 | `tools\setup_robinhad.ps1` |
| StyleTTS2 | 30 | `tools\setup_styletts2.ps1` |
| RVC (гібрид) | ваша `.pth`+`.index` | `tools\setup_rvc.ps1` |

Потрібен хоча б один із Robinhad / StyleTTS2.

## Модулі

- `api_server.py` — HTTP API + роздача `web/`
- `web/` — HTML / CSS / JS
- `pipeline.py` — розмітка → вербалізація → chunking → TTS → опційний RVC
- `engines/` — Robinhad / StyleTTS2 / RVC (окремі `.venv-*`)
- `text/` — verbalizer, stress, markup, chunking
- `audio/` — WAV/MP3 експорт
- `models_manager.py` — збереження RVC з дедупом по SHA-256
- `error_log.py` — консоль + помилки → `logs/errors.txt`

## Розмітка тексту

| Потреба | Приклад |
|---------|---------|
| Наголос | `прив+іт` |
| Пауза | `[пауза=0.8]` |
| Темп | `[повільно]…[/повільно]`, `[швидко]…[/швидко]` |

Довгий текст автоматично б’ється на речення перед синтезом.

## Тести

```
powershell -File tools\run_tests.ps1
```
