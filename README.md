# Spag Voice Studio (SVS+)

Локальна програма для озвучення **українського** тексту природним голосом:
наголос, вербалізація чисел/дат, кілька дикторських рушіїв і опційне
переозвучення власною RVC-моделлю.

**English:** see [README.en.md](README.en.md)

---

## Швидкий старт (після `git clone`)

Потрібно: **Windows 10/11**, **Python 3.10+** (краще **3.11**), інтернет для
першого встановлення.

```powershell
git clone https://github.com/ipzk-spa/tts.git
cd tts

# 1) Базові залежності (UI + API)
powershell -ExecutionPolicy Bypass -File .\install.ps1

# 2) Хоча б один TTS-двигун (рекомендовано Robinhad)
powershell -ExecutionPolicy Bypass -File .\tools\setup_robinhad.ps1
# або / додатково:
# powershell -ExecutionPolicy Bypass -File .\tools\setup_styletts2.ps1
# powershell -ExecutionPolicy Bypass -File .\tools\setup_rvc.ps1

# 3) Запуск
.\start_voice_studio.bat
```

Відкриється браузер: `http://127.0.0.1:7900`

> `start_voice_studio.bat` сам перевіряє/ставить базові пакети в `.venv`,
> тож крок `install.ps1` можна пропустити — він зручний для явного
> «встановити й вийти».

---

## Що вміє

| Функція | Опис |
|--------|------|
| Robinhad | 5 дикторських голосів (Тетяна, Микита, Лада, Дмитро, Олекса) |
| StyleTTS2 | 30 стилів + слайдер темпу |
| Наголос | ручний `прив+іт` + словниковий автомат |
| Вербалізація | числа, дати, час, скорочення → слова |
| Розмітка | `[пауза=1.5]`, `[швидко]…[/швидко]`, `[повільно]…[/повільно]` |
| Гібрид RVC | TTS читає → ваша `.pth`+`.index` дає тембр |
| Експорт | WAV і MP3 одразу після синтезу |

Опис модулів: [voice_studio/README.md](voice_studio/README.md).  
Каталог моделей: [docs/UKRAINIAN_MODELS.md](docs/UKRAINIAN_MODELS.md).

---

## Вимоги

- Windows 10/11
- Python 3.10+ (рекомендовано 3.11)
- 8+ ГБ RAM (16 ГБ комфортніше з усіма двигунами)
- GPU NVIDIA — опційно (CUDA підхоплюється автоматично; без GPU все працює, але повільніше)
- Інтернет — лише для першого `install` / `setup_*`

---

## Структура репозиторію

```
├── README.md / README.en.md   ← документація
├── install.ps1                ← перше встановлення після clone
├── start_voice_studio.bat     ← щоденний запуск
├── start_voice_studio.ps1
├── logs/                      ← errors.txt (помилки для діагностики)
├── voice_studio/              ← API + веб-UI + тести
│   ├── api_server.py
│   ├── requirements.txt
│   └── web/
├── tools/                     ← setup_robinhad / styletts2 / rvc
├── models/                    ← ваги (завантажуються setup-скриптами)
└── docs/
```

У Git **не** потрапляють: `.venv*`, кеш Hugging Face, `.pth` моделі,
особисті RVC-завантаження, згенеровані WAV/MP3, `logs/errors.txt`.
Після clone їх знову створюють `install.ps1` і `tools\setup_*.ps1`.

---

## Лог помилок

Якщо щось пішло не так (синтез, запуск, експорт MP3 тощо), деталі
записуються сюди:

```
logs\errors.txt
```

Можна просто скинути цей файл — у ньому час, контекст і traceback.
Файл ротується (~5 МБ → `errors.old.txt`).

---

## Тести

```powershell
powershell -File .\tools\run_tests.ps1
```

або:

```powershell
.\.venv\Scripts\python.exe -m pytest voice_studio\tests\ -v
```

---

## Ліцензія та сторонні моделі

Код **Spag Voice Studio** у цьому репозиторії.  
Двигуни (Robinhad, StyleTTS2, RVC, torch тощо) мають власні ліцензії й
завантажуються під час `setup_*.ps1` — перевіряйте їхні умови перед
комерційним використанням.
