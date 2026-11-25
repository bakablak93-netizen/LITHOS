# LITHOS: Глава → Курс (KMG Digital Hackathon 2026)

Автоматическая платформа превращения глав нефтегазовых учебников (`.md` + JSON-паспорт) в **100% детерминированные учебные видеокурсы** (1920×1080, 30 fps) и **интерактивные 3D-лаборатории**.

## Ключевые принципы
1. **Запрет AI-видео для классов A и B:** вся научная графика, формулы LaTeX, профили давления и кривые каротажа генерируются детерминированным кодом (`NumPy/SciPy` + `Manim CE` + `Three.js / R3F` + `Remotion` + `FFmpeg`).
2. **Domain QA Verifier:** проверяет сценарий по `quantitative_safety_warning`, `school_warning` и `reservoir_type_warning` из JSON-паспорта учебника, блокирует выдуманные числовые отсчёты с неоцифрованных палеток (например, палеток БЭЗ).
3. **Терминологический мост СНГ ↔ Запад:** формулы выводятся в нотации учебника ($K_п$, $\rho_п$, $P_п$, $\alpha_{СП}$, $\kappa$) с плашками западных эквивалентов ($\phi$, $R_t$, $F$, $SSP/SSP_{\max}$, $\eta$).
4. **Два эталонных модуля + универсальный режим (`ctrl_*`):**
   - **Модуль 1:** Латышова М.Г. (1991) — синтетический каротаж КС/МБК/СП, уравнение Арчи–Дахнова, ВНК и 3D *Probe Lab*.
   - **Модуль 2:** Басниев К.С. и др. (2005) — закон Дарси, формула Дюпюи, воронка депрессии, пьезопроводность $\kappa$ и метод ПССС Чарного + 3D *Hydro Lab*.
   - **Универсальный парсер:** работает на любой `.md` главе + `.md`/`.json` паспорте.

## Быстрый старт (Docker — 1 команда)
1. Скопируйте `.env.example` в `.env` (или заполните `LLM_API_KEY` в `.env`):
   ```bash
   cp .env.example .env
   ```
2. Запустите сборку и сервис:
   ```bash
   docker compose up --build
   ```
3. Откройте интерфейс: `http://localhost:8000`

## Проверка тестами (внутри контейнера или локально с Python 3.12+)
```bash
python3 -m pytest backend/tests/ -v
```

## Конвейер Т3 «Глава → Курс» (Этапы 1–4)
Штатная точка входа — `python3 -m backend.study`:

```bash
# 1. Сборка всех 6 курсов (3 обучающих + 3 контрольных) с полным рендером MP4, субтитрами VTT/SRT, ASR и автономными ZIP
python3 -m backend.study build-all --output-dir outputs/t3_final

# 2. Сборка одной главы (в том числе с разрывным диапазоном PDF)
python3 -m backend.study build-course --book ctrl_vendelshtein.md --ranges "9-14,20-30" --output-dir outputs/t3_final

# 3. Независимая двусторонняя сверка реестр ↔ учебный слой по PDF
python3 -m backend.study verify-registry --book all

# 4. Проверка внешнего пакета «закладок» и внутренняя калибровка
python3 -m backend.study verify-bookmarks
python3 -m backend.study verify-bookmarks --input path/to/bookmarks.json --book train_latyshova.md

# 5. Реактивная пересборка из уже сохранённого layer.json (HTML + голос + MP4 + SRT/VTT + ZIP)
python3 -m backend.study rebuild-fact --book train_latyshova.md --layer-json outputs/t3_final/t3_train_latyshova/layer.json --old 2425 --new 2426

# 6. Локальная проверка распознавания речи (faster-whisper)
python3 -m backend.study asr-check --course-dir outputs/t3_final/t3_train_latyshova
```

## Предметный пакет и приватность
- Предметный глоссарий, правила маршрутизации, легенда и словарь произношений вынесены из ядра в заменяемый файл [oil_gas_ru.json](file:///home/antigravity/bakablak93-netizen/LITHOS/data/domain_packages/oil_gas_ru.json).
- По умолчанию конвейер работает **строго локально**; текст глав и PDF не отправляется во внешние LLM (даже при наличии `LLM_API_KEY` в legacy `parser_agent.py` требуется явный флаг `LITHOS_ALLOW_EXTERNAL_CHAPTER_LLM=1`; OpenAI-подсказки получают только обезличенные метаданные).
- Подробная инструкция воспроизведения, версии инструментов, промпты, модели и шаблон журнала заморозки: [docs/t3-runbook.md](file:///home/antigravity/bakablak93-netizen/LITHOS/docs/t3-runbook.md).

