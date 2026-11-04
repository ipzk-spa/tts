# Каталог українських TTS / голосових моделей

> Довідковий каталог: що інтегровано у Spag Voice Studio і що можна розглянути далі.

## ✅ Інтегровано у Voice Studio

| Модель | Тип | Голоси | Hugging Face / Посилання | Де в проєкті |
|--------|-----|--------|--------------------------|--------------|
| **robinhad/ukrainian-tts** (ESPnet Tacotron2+HiFiGAN) | TTS | 5 (Тетяна, Микита, Лада, Дмитро, Олекса) | [robinhad/ukrainian-tts](https://github.com/robinhad/ukrainian-tts) | `engines/robinhad_engine.py`, `tools/setup_robinhad.ps1` |
| **StyleTTS2 Ukrainian** | TTS | 30 дикторських стилів | [patriotyk/styletts2-ukrainian](https://huggingface.co/spaces/patriotyk/styletts2-ukrainian) | `engines/styletts2_engine.py`, `tools/setup_styletts2.ps1` |
| **RVC** (`tts-with-rvc`) | Voice conversion | Ваша `.pth`+`.index` модель | [Atm4x/tts-with-rvc](https://github.com/Atm4x/tts-with-rvc) | `engines/rvc_engine.py`, `tools/setup_rvc.ps1` |

Обидва TTS-рушії підтримують ручний наголос `+` перед голосною (через
`ukrainian-word-stress`) і автоматичний словниковий наголос для решти слів.
Жоден із них не має власного керування емоцією/виразністю — для іншого
тембру голосу використовуйте гібридне переозвучення RVC (див.
`voice_studio/README.md`).

## 💡 Розглядалися, але не інтегровані (можливе майбутнє розширення)

| Модель | Тип | Голоси | Hugging Face / Посилання | Чому не зараз |
|--------|-----|--------|--------------------------|----------------|
| **Fish Speech 1.5 Ukrainian** | TTS | 55 спікерів, voice cloning з референсного аудіо | [skypro1111/fish-speech-1.5-ukrainian](https://huggingface.co/skypro1111/fish-speech-1.5-ukrainian) | Багатоетапний конвеєр (LLaMA text2semantic + VQGAN), потребує потужного GPU, CC-BY-NC-SA 4.0 |
| **tts_uk (RAD-TTS++)** | TTS | Tetiana, Lada, Mykyta | [egorsmkv/tts_uk](https://github.com/egorsmkv/tts_uk) | 44.1 kHz, точне керування — цікавий третій варіант якщо знадобиться ще один "фіксований" голос |
| **RadTTS-UK Vocos** | TTS | Демо на HF | [Yehor/radtts-uk-vocos-demo](https://huggingface.co/spaces/Yehor/radtts-uk-vocos-demo) | Аналогічно tts_uk |
| **MMS-TTS UKR** (Meta) | TTS | 1 голос | `facebook/mms-tts-ukr` | Один генеричний голос, гірше за Robinhad/StyleTTS2; CC-BY-NC 4.0 |
| **SpeechT5 Common Voice UA** | TTS | Seed-based тембр | `tenebrisu/speecht5_tts_common_voice_uk` | Очікує вхід транслітом (латиницею) — незручний UX для української |
| **Silero v5 (uk)** | TTS | Кілька іменованих голосів | [snakers4/silero-models](https://github.com/snakers4/silero-models) | Легший за Robinhad/StyleTTS2, але і якість помітно нижча — вибрано StyleTTS2 замість нього |

## 🎙 RVC-голоси (.pth + .index)

RVC — це **конвертація голосу**, не прямий TTS. У цьому проєкті використовується
як гібридне переозвучення (Robinhad/StyleTTS2 → ваша RVC-модель, розділ
"🎙️ Гібрид" у програмі).

| Джерело | Опис |
|---------|------|
| [RVC WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) | Навчання власного голосу (10–30 хв аудіо) |
| [Voice Models community](https://voice-models.com/) | Готові RVC-моделі (перевіряйте мову/якість) |
| [Hugging Face — RVC](https://huggingface.co/models?search=rvc+ukrainian) | Пошук українських RVC |

## Ліцензії

- robinhad/ukrainian-tts: перевірте LICENSE у репозиторії (модель з відкритим кодом)
- StyleTTS2 (patriotyk): перевірте LICENSE у HF Space
- Fish Speech: CC-BY-NC-SA 4.0 (некомерційна)
- MMS-TTS: CC-BY-NC 4.0 (некомерційна)
- SpeechT5 UA: MIT
