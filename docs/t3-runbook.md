# Инструкция по эксплуатации и проверке пакета Т3 «Глава → курс» (Runbook)

Данная инструкция содержит проверенные штатные команды для сборки, верификации, реактивной пересборки и проверки автономных курсов Т3 в репозитории `LITHOS`.

---

## 1. Запуск автотестов (до и после правок)

Запуск полного набора регрессионных и приёмочных тестов (исходный пайплайн + Этапы 1–4 Т3):

```bash
python3 -m pytest backend/tests/ -v
```

---

## 2. Полная сборка всех 6 курсов Т3, роликов 9:16 / 16:9, ZIP-пакетов и протокола заморозки

Штатная команда сборки проверочного пакета в отдельный каталог `outputs/t3_verify`:

```bash
python3 -m backend.study build-all --output-dir outputs/t3_verify
```

После выполнения в `outputs/t3_verify/` создаются:
- `t3_freeze_report.json` — сводный протокол заморозки, инвентаризация версий, пересчёт метрик аудита и отчёт калибровки верификатора «закладок».
- Каталоги 3 обучающих курсов:
  - `outputs/t3_verify/t3_train_latyshova/` (включая вертикальный шортс `media/shorts_9_16_latyshova.mp4` `1080x1920`, `54.0 с`, `.srt`, `.mp3`, `index.html`, `t3_train_latyshova_offline.zip`)
  - `outputs/t3_verify/t3_train_basniev/` (включая горизонтальный разбор `media/explainer_16_9_basniev.mp4` `1920x1080`, `104.0 с`, `.srt`, `.mp3`, `index.html`, `t3_train_basniev_offline.zip`)
  - `outputs/t3_verify/t3_train_kuznetsov/` (Глава 10 «Природные резервуары рифов», PDF стр. 200–222, кодовые перерисовки и анимации `Рис. 10.1`, `Рис. 10.2`, `Рис. 10.5`, `index.html`, `t3_train_kuznetsov_offline.zip`)
- Каталоги 3 контрольных курсов:
  - `outputs/t3_final/t3_ctrl_vendelshtein/` (разрывный диапазон PDF `9–14, 20–30`)
  - `outputs/t3_final/t3_ctrl_barenblatt/` (Глава II, §1, PDF `38–51`)
  - `outputs/t3_final/t3_ctrl_baraboshkin_b/` (Глава 1, §1.2, PDF `30–44`, печ. `29–43`)

---

## 3. Сборка отдельной главы (включая разрывные диапазоны PDF и закрытые материалы)

```bash
python3 -m backend.study build-course --book ctrl_vendelshtein.md --ranges "9-14,20-30" --output-dir outputs/t3_final
python3 -m backend.study build-course --book train_kuznetsov.md --ranges "200-222" --output-dir outputs/t3_final
```

---

## 4. Двусторонняя сверка независимого реестра и учебного слоя (Этап 1)

```bash
python3 -m backend.study verify-registry --book all
```

---

## 5. Проверка верификатора внешних «закладок» и калибровки (Этап 4)

```bash
python3 -m backend.study verify-bookmarks
python3 -m backend.study verify-bookmarks --input path/to/external_bookmarks.json --book train_latyshova.md
```

---

## 6. Реактивная пересборка из сохранённого `layer.json` (Этап 3)

Правка вносится в уже сохранённый `layer.json` (без повторного импорта книги) и обновляет HTML, голос, кадры MP4, SRT/VTT и ZIP:

```bash
python3 -m backend.study rebuild-fact \
  --book train_latyshova.md \
  --layer-json /tmp/rebuild_check/t3_train_latyshova/layer.json \
  --old "2425" --new "2426" \
  --output-dir /tmp/rebuild_check
```

---

## 7. Локальная проверка распознавания речи (ASR WER) и `ffprobe`

```bash
python3 -m backend.study asr-check --course-dir outputs/t3_final/t3_train_latyshova
python3 -m backend.study asr-check --course-dir outputs/t3_final/t3_train_basniev
ffprobe -v error -show_entries format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate -of json outputs/t3_final/t3_train_latyshova/media/shorts_9_16_latyshova.mp4
```

---

## 8. Версии инструментов, модели, промпты и порядок замены

- **Среда и версии:** `Python 3.12.16`, `FFmpeg` (EBU R128 `loudnorm` / `ebur128`, `libx264`, `aac`), `edge-tts 7.3.1`, `espeak-ng 1.51`, `faster-whisper 1.2.1` (`ctranslate2 4.9.1`), `jiwer`, `playwright 1.65.2`, `pypdf 7.1.1`.
- **Синтез речи (`backend/t3/voice.py`):** по умолчанию `LITHOS_TTS_ENGINE=auto` (`edge-tts`, голос `ru-RU-DmitryNeural`, `rate=-6%` → локальный fallback `espeak-ng -v ru -s 150`; при `none` или отказе — явная ошибка `silence_fallback_error`, `audio_ready=False`). Для полностью локальной генерации без сети: `LITHOS_TTS_ENGINE=espeak`.
- **Локальный ASR (`backend/t3/asr_check.py`):** `faster-whisper` модель `small` (`int8`, CPU, `beam_size=5`, `language="ru"`). Для замены модели задайте `LITHOS_ASR_MODEL=medium` или `base`.
- **Заменяемый предметный пакет (`data/domain_packages/oil_gas_ru.json`):** содержит глоссарий, правила маршрутизации, единую легенду и словарь произношений. Для смены предметной области создайте новый JSON-файл по той же схеме и укажите путь через `LITHOS_DOMAIN_PACKAGE_PATH`.
- **Промпты и OpenAI-подсказки (`backend/t3/tasks_engine.py`):** используются **только при явном `OPENAI_API_KEY`**, получают **строго обезличенные метаданные** (`ALLOWED_HINT_METADATA_KEYS`: `task_type`, `difficulty_code`, `misconception_tag`, `attempt_number`, `learner_error_category`) — без текста главы и PDF. Модель задаётся `LITHOS_HINT_MODEL` (по умолчанию `gpt-4o-mini`).
- **Legacy-обогащение сцен (`backend/agents/parser_agent.py`):** по умолчанию отключено (`LITHOS_ALLOW_EXTERNAL_CHAPTER_LLM=0`).

## 9. Сетевые операции и передаваемые данные

| Операция | Когда вызывается | Какие данные уходят во внешнюю сеть | Как отключить (100% локально) |
|---|---|---|---|
| `edge-tts` (`speech.platform.bing.com`) | При синтезе дикторской озвучки роликов (`LITHOS_TTS_ENGINE=auto` / `edge`) | Только короткий текст закадра ролика (~100–250 слов), **без текста главы и PDF** | `LITHOS_TTS_ENGINE=espeak` |
| OpenAI hints (`tasks_engine.py`) | Только если задан `OPENAI_API_KEY` и вызвана генерация подсказки | Только обезличенные метаданные ошибки (`ALLOWED_HINT_METADATA_KEYS`) | Не задавать `OPENAI_API_KEY` |
| HuggingFace Hub (`faster-whisper`) | Только при первом скачивании весов модели `small` в кэш | Имя публичной модели (`Systran/faster-whisper-small`) | После кэширования работает без сети (`HF_HUB_OFFLINE=1`) |

## 10. Проверка обратной совместимости и веб-сборки

```bash
python3 -m backend.study check-compat --manifest outputs/t3_final/t3_train_latyshova/t3_course_package.json
```

## 11. Шаблон фиксации заморозки и трудозатрат (заполняется командой)

- **Тег / коммит заморозки:** `<branch>@<sha>`
- **Обучающие главы (ручная редактура / проверка):** `<часы, замечания>`
- **Контрольные главы (прогон без ручной подгонки):** `<часы, замечания>`
- **Испытание новичком (`docs/t3-novice-protocol.md`):** `<дата, время прохождения, балл>`

