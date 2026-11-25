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
  - `outputs/t3_verify/t3_ctrl_vendelshtein/` (разрывный диапазон PDF `9–14, 20–30`)
  - `outputs/t3_verify/t3_ctrl_barenblatt/` (Глава 1, PDF `5–19`)
  - `outputs/t3_verify/t3_ctrl_baraboshkin_b/` (Глава 1, §1.1–1.2, PDF `20–43`)

Для публикации/обновления основной сдаваемой сборки в `outputs/` после проверки:

```bash
python3 -m backend.study build-all --output-dir outputs
```

---

## 3. Сборка отдельной главы (включая разрывные диапазоны PDF и закрытые материалы)

Сборка главы с явным указанием разрывного диапазона PDF-страниц (на примере Вендельштейна, PDF 9–14 и 20–30):

```bash
python3 -m backend.study build-course --book ctrl_vendelshtein.md --ranges "9-14,20-30" --output-dir outputs/t3_verify
```

Сборка обучающей главы Кузнецова (PDF 200–222):

```bash
python3 -m backend.study build-course --book train_kuznetsov.md --ranges "200-222" --output-dir outputs/t3_verify
```

---

## 4. Двусторонняя сверка независимого реестра и учебного слоя (Этап 1)

Проверка всех 6 книг по независимому реестру PDF:

```bash
python3 -m backend.study verify-registry --book all
```

---

## 5. Проверка верификатора внешних «закладок» и калибровки (Этап 4)

Запуск калибровочного стенда (контроль 0 ложных тревог на всех 6 книгах и 100% обнаружения 9 типов закладок, включая замену «однозначно нельзя» на «однозначно можно» у Вендельштейна со стр. 20):

```bash
python3 -m backend.study verify-bookmarks
```

---

## 6. Реактивная пересборка шага, заданий, субтитров и ролика от правки одного факта в слое (Этап 3)

Проверка пересборки зависимых артефактов одной штатной командой при изменении подтверждённого факта в слое:

```bash
python3 -m backend.study rebuild-fact --book train_latyshova.md --old "20 Ом·м" --new "25 Ом·м" --output-dir outputs/t3_verify/rebuild_check
```

---

## 7. Проверка обратной совместимости сохранённых курсов и сборка веб-интерфейса

Проверка валидации/миграции сохранённого манифеста курса:

```bash
python3 -m backend.study check-compat --manifest outputs/t3_verify/t3_train_latyshova/t3_course_package.json
```

Проверка production-сборки React веб-интерфейса:

```bash
npm --prefix web_ui run build
```
