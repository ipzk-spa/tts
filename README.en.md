# Spag Voice Studio (SVS+)

Local app for natural **Ukrainian** text-to-speech: stress marks, number/date
verbalization, multiple speaker engines, and optional re-voicing with your
own RVC model.

**Українською:** see [README.md](README.md)

---

## Quick start (after `git clone`)

Requirements: **Windows 10/11**, **Python 3.10+** (preferably **3.11**),
internet for the first install.

```powershell
git clone https://github.com/<your-account>/<repo>.git
cd <repo>

# 1) Base dependencies (UI + API)
powershell -ExecutionPolicy Bypass -File .\install.ps1

# 2) At least one TTS engine (Robinhad recommended)
powershell -ExecutionPolicy Bypass -File .\tools\setup_robinhad.ps1
# and/or:
# powershell -ExecutionPolicy Bypass -File .\tools\setup_styletts2.ps1
# powershell -ExecutionPolicy Bypass -File .\tools\setup_rvc.ps1

# 3) Run
.\start_voice_studio.bat
```

Browser opens at: `http://127.0.0.1:7900`

> `start_voice_studio.bat` also creates `.venv` and installs base packages,
> so `install.ps1` is optional — useful when you want an explicit
> “install then exit” step.

---

## Features

| Feature | Description |
|--------|-------------|
| Robinhad | 5 studio voices (Tetiana, Mykyta, Lada, Dmytro, Oleksa) |
| StyleTTS2 | 30 styles + speech-rate slider |
| Stress | manual `прив+іт` + dictionary auto-stress |
| Verbalization | numbers, dates, time, abbreviations → words |
| Markup | `[пауза=1.5]`, `[швидко]…[/швидко]`, `[повільно]…[/повільно]` |
| Hybrid RVC | TTS reads → your `.pth`+`.index` supplies timbre |
| Export | WAV and MP3 right after synthesis |

Module map: [voice_studio/README.md](voice_studio/README.md) (Ukrainian).  
Model catalog: [docs/UKRAINIAN_MODELS.md](docs/UKRAINIAN_MODELS.md).

---

## Requirements

- Windows 10/11
- Python 3.10+ (3.11 recommended)
- 8+ GB RAM (16 GB is more comfortable with all engines)
- NVIDIA GPU — optional (CUDA is used automatically; CPU works, just slower)
- Internet — only for the first `install` / `setup_*`

---

## Repository layout

```
├── README.md / README.en.md   ← docs
├── install.ps1                ← first-time setup after clone
├── start_voice_studio.bat     ← daily launch
├── start_voice_studio.ps1
├── logs/                      ← errors.txt (diagnostics)
├── voice_studio/              ← API + web UI + tests
│   ├── api_server.py
│   ├── requirements.txt
│   └── web/
├── tools/                     ← setup_robinhad / styletts2 / rvc
├── models/                    ← weights (downloaded by setup scripts)
└── docs/
```

**Not** in Git: `.venv*`, Hugging Face cache, `.pth` weights, personal RVC
uploads, generated WAV/MP3, `logs/errors.txt`. After clone, recreate them with
`install.ps1` and `tools\setup_*.ps1`.

---

## Error log

On failures (synthesis, startup, MP3 export, etc.) details are appended to:

```
logs\errors.txt
```

Send that file when asking for help — it includes timestamps, context, and
tracebacks. Rotates at ~5 MB → `errors.old.txt`.

---

## Tests

```powershell
powershell -File .\tools\run_tests.ps1
```

or:

```powershell
.\.venv\Scripts\python.exe -m pytest voice_studio\tests\ -v
```

---

## License and third-party models

**Spag Voice Studio** code lives in this repository.  
Engines (Robinhad, StyleTTS2, RVC, torch, etc.) have their own licenses and
are downloaded during `setup_*.ps1` — check their terms before commercial use.
