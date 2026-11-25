"""
Этап 2 Т3: Шаблон автономного курса (backend/t3/offline/template.py).

Обеспечивает:
- Единый визуальный язык LITHOS с поддержкой тёмной и светлой темы (CSS-переменные)
- Единые названия сущностей: «Глава», «Шаг», «Задание», «Источник», «Паспорт ролика»
- Адаптивную вёрстку на 390 px (мобильный телефон, включая широкие таблицы с горизонтальным скроллом) и 1280 px
- Базовый размер шрифта от 16 px, видимый фокус (:focus-visible), подписи изображений (<figcaption>),
  полное управление с клавиатуры (включая перестановку элементов в заданиях на упорядочивание)
  и поддержку настройки уменьшенного движения (prefers-reduced-motion: reduce)
- Работу без сервера и логина (100% автономный HTML + ZIP < 30 МБ на главу)
- Сохранение прогресса, возврата к шагу, карточек («Знаю» / «Повторить») и ответов в localStorage.
"""

from __future__ import annotations

import html
import json
import zipfile
from pathlib import Path
from typing import Any

from backend.t3.models import (
    FlashcardItem,
    IllustrationSpec,
    MediaPassport,
    OCRCorrectionEntry,
    StudyCoursePackage,
    StudyLayer,
    StudyStepScreen,
    StudyTask,
)


def build_step_screens_from_layer(
    layer: StudyLayer,
    illustrations: list[IllustrationSpec],
    media_passports: list[MediaPassport] | None = None,
) -> list[StudyStepScreen]:
    """
    Формирует экраны шагов (StudyStepScreen) строго из единого учебного слоя (StudyLayer).
    Каждый значимый абзац и утверждение снабжены ссылкой на страницу источника и unit_id.
    Лист исправлений OCR синхронизирован с текстом шагов.
    """
    media_passports = media_passports or []
    illust_by_node = {il.node_id: il for il in illustrations}
    ocr_by_node: dict[str, list[OCRCorrectionEntry]] = {}
    for corr in layer.ocr_corrections:
        ocr_by_node.setdefault(corr.applied_in_node_id, []).append(corr)

    screens: list[StudyStepScreen] = []
    for idx, node in enumerate(layer.nodes):
        step_id = node.node_id.replace("_node_", "_step_")
        illust = illust_by_node.get(node.node_id, illustrations[min(idx, len(illustrations) - 1)])
        node_ocrs = ocr_by_node.get(node.node_id, [])

        q0 = node.quotes_and_pages[0] if node.quotes_and_pages else None
        p0 = q0.pdf_page if q0 else 1
        pr0 = q0.printed_page if q0 else "1"
        u0 = q0.unit_id if q0 else f"{layer.book_id}_unit"

        # Формируем абзацы объяснения с обязательными ссылками на источник и применёнными правками OCR
        paragraphs: list[dict[str, Any]] = [
            {
                "role": "Физико-геологический механизм",
                "text": node.mechanism,
                "unit_id": u0,
                "pdf_page": p0,
                "printed_page": pr0,
                "source_citation": f"Источник: PDF стр. {p0} (печ. стр. {pr0}), ед. {u0}",
                "verbatim_quote": q0.verbatim_quote if q0 else "",
            },
            {
                "role": "Практика работы специалиста",
                "text": node.practice,
                "unit_id": node.quotes_and_pages[1].unit_id if len(node.quotes_and_pages) > 1 else u0,
                "pdf_page": node.quotes_and_pages[1].pdf_page if len(node.quotes_and_pages) > 1 else p0,
                "printed_page": node.quotes_and_pages[1].printed_page if len(node.quotes_and_pages) > 1 else pr0,
                "source_citation": f"Источник: PDF стр. {node.quotes_and_pages[1].pdf_page if len(node.quotes_and_pages) > 1 else p0}",
                "verbatim_quote": node.quotes_and_pages[1].verbatim_quote if len(node.quotes_and_pages) > 1 else (q0.verbatim_quote if q0 else ""),
            },
            {
                "role": "Пороговая идея и перенос в данные",
                "text": f"{node.threshold_concept} Перенос в данные: {node.data_transfer}",
                "unit_id": u0,
                "pdf_page": p0,
                "printed_page": pr0,
                "source_citation": f"Источник: PDF стр. {p0} (печ. стр. {pr0})",
                "verbatim_quote": q0.verbatim_quote if q0 else "",
            },
        ]

        if node_ocrs:
            corr_summary = "; ".join(
                f"стр. {c.pdf_page}: «{c.original_ocr}» → «{c.corrected_reading}» ({c.rationale})"
                for c in node_ocrs
            )
            paragraphs.append(
                {
                    "role": "Сверка чтения с оригиналом (исправление OCR)",
                    "text": f"В тексте курса учтено исправление OCR по PDF-оригиналу: {corr_summary}",
                    "unit_id": u0,
                    "pdf_page": node_ocrs[0].pdf_page,
                    "printed_page": node_ocrs[0].printed_page,
                    "source_citation": f"Лист исправлений OCR: PDF стр. {node_ocrs[0].pdf_page}",
                    "verbatim_quote": node_ocrs[0].corrected_reading,
                }
            )

        # Формулы и их расшифровка
        formulas_decoded: list[dict[str, Any]] = []
        for ct in node.core_terms:
            if ct.cis_symbol and ct.cis_symbol != "—":
                formulas_decoded.append(
                    {
                        "title": ct.term,
                        "cis_formula": f"{ct.cis_symbol} ({ct.unit or 'б/р'})",
                        "west_formula": f"{ct.west_symbol} — {ct.west_term}",
                        "variables": {
                            ct.cis_symbol: f"{ct.definition} (СНГ)",
                            ct.west_symbol: f"Международное обозначение SPE/API ({ct.west_term})",
                        },
                        "source_ref": f"PDF стр. {ct.first_introduced_pdf_page} (печ. стр. {ct.first_introduced_printed_page})",
                    }
                )

        # Сводная таблица шага (проверяется на 390 px и 1280 px)
        step_tables: list[dict[str, Any]] = [
            {
                "title": f"Сводная таблица параметров и терминологического моста (Шаг {node.order})",
                "headers": ["Параметр / Термин", "Обозначение СНГ", "Международный аналог (West)", "Единицы", "Определение и страница источника"],
                "rows": [
                    [
                        ct.term,
                        ct.cis_symbol,
                        f"{ct.west_symbol} ({ct.west_term})",
                        ct.unit or "б/р",
                        f"{ct.definition} [стр. {ct.first_introduced_pdf_page}]",
                    ]
                    for ct in node.core_terms
                ]
                or [
                    [
                        node.step_title,
                        "СНГ",
                        "SPE / API",
                        "СИ / практ.",
                        f"{node.summary_2_3_sentences} [стр. {p0}]",
                    ]
                ],
            }
        ]

        # Привязка ролика и паспорта ролика к соответствующему шагу (относительный путь для file://)
        video_url = None
        video_vtt_url = None
        video_aspect = None
        passport_id = None
        if media_passports and idx in (0, len(layer.nodes) - 1):
            mp = media_passports[0]
            video_url = f"media/{Path(mp.video_rel_path).name}"
            vtt_src = mp.vtt_rel_path or Path(mp.srt_rel_path).with_suffix(".vtt").name
            video_vtt_url = f"media/{Path(vtt_src).name}"
            video_aspect = mp.aspect_ratio
            passport_id = mp.passport_id

        # Блок «Решение на данных» для обучающих глав (Басниев и Кузнецов; у Латышовой — полный практикум)
        data_decision_card = None
        if layer.book_file == "train_basniev.md" and idx == min(2, len(layer.nodes) - 1):
            data_decision_card = {
                "title": "Решение на данных: выбор способа интенсификации притока по воронке депрессии и ПССС",
                "origin_and_assumptions": "Симуляция `basniev_hydro` (Дюпюи + ПССС И.А. Чарного, Гл. XX–XXIV, стр. 416–500): однородный пласт h=14 м, k=120 мД, μ=1,8 мПа·с, R_к=250 м, r_с=0,10 м; линейный закон Дарси.",
                "observed_features": [
                    {"label": "Забойное давление p_с / Контурное p_к", "value": "9,0 / 24,0 МПа (Δp = 15,0 МПа)"},
                    {"label": "Падение давления в первых 5 м от ствола", "value": "7,5 МПа (50% всей депрессии)"},
                    {"label": "Рост дебита при удвоении r_с (0,10 → 0,20 м)", "value": "247,5 → 272,2 м³/сут (+9,9%)"},
                    {"label": "Фронт возмущения ПССС R(t) при t=6 ч и κ=0,211 м²/с", "value": "135,0 м (квадратичный рост t ~ R²)"},
                ],
                "decision_rule": "Если Δp сосредоточена в призабойной зоне (r < 5 м), геометрическое расширение r_с под логарифмом ln(R_к/r_с) даёт <10% эффекта — требуется обработка призабойной зоны (рост k_пзп) или ГРП; для увеличения радиуса исследования в N раз время t увеличивают в N² раз.",
                "rule_limits": "Правило Дюпюи и ПССС перестаёт работать при нелинейной фильтрации (большие числа Рейнольдса у забоя при газе), двухфазном притоке ниже давления насыщения или наличии тектонических экранов ближе R(t).",
                "question": "К какому решению ведут эти данные, если цель — удвоить дебит скважины при текущем пластовом давлении?",
                "options": [
                    {"id": "opt_rc", "label": "Разбурить ствол скважины r_с с 0,10 до 0,20 м (даст кратный рост дебита)", "correct": False, "feedback": "Неверно: r_с стоит под знаком ln(R_к/r_с), удвоение r_с даёт лишь +9,9% дебита."},
                    {"id": "opt_opz", "label": "Провести ОПЗ/ГРП для повышения проницаемости призабойной зоны (где теряется 50% депрессии)", "correct": True, "feedback": "Верно! Проницаемость k входит в формулу Дюпюи линейно, а основная потеря давления происходит именно в первых метрах у ствола."},
                    {"id": "opt_time", "label": "Увеличить время пуска в 2 раза — это вдвое поднимет установившийся дебит Дюпюи", "correct": False, "feedback": "Неверно: время t увеличивает радиус воронки R(t) ~ √t, но не меняет установившийся перепад Δp."},
                ],
            }
        elif layer.book_file == "train_kuznetsov.md" and idx == min(1, len(layer.nodes) - 1):
            data_decision_card = {
                "title": "Решение на данных: распознавание рифовой фации, эволюции и геометрии резервуара (рис. 10.2)",
                "origin_and_assumptions": "Данные разреза рифа Рейнбоу А (В.Г. Кузнецов, 2012, Гл. 10, стр. 206, рис. 10.2) + интерактивная спецификация фациальной модели (распознавание фаций, эволюция биогерма во времени, геометрия 0–1500 м × H=250 м).",
                "observed_features": [
                    {"label": "Группа I (гребень/каркас рифа)", "value": "Ф = 10–30%, k = 50–2000·10⁻¹⁵ м² (высокоёмкий каверно-поровый коллектор)"},
                    {"label": "Группа II (пририфовый шлейф)", "value": "Ф = 15–35%, k = 30–30000·10⁻¹⁵ м² (максимальная проницаемость)"},
                    {"label": "Группа V (внутрибассейновые битуминозные породы)", "value": "Ф = 3–8%, k < 3·10⁻¹⁵ м² (флюидоупор / покрышка)"},
                    {"label": "Геометрия по профилю СЗ–ЮВ", "value": "Высота H до 230–250 м на базе ~1500 м (резкий фациальный клин)"},
                ],
                "decision_rule": "Если по керну и разрезу в центральной куполообразной зоне фиксируются строматопорово-коралловые известняки (группы I–II, Ф ≥ 10%, k ≥ 30 мД), а по периферии — темноцветные битуминозные микрозернистые разности (группа V, k < 3 мД), то скважину закладывают в гребень/шлейф (I–II) с учётом резкого выклинивания к борту.",
                "rule_limits": "Правило теряет силу при полной вторичной цементации каверн ангидритом/галитом или при инверсии пористости на глубоком погружении без учёта трещиноватости.",
                "interactive_spec": {
                    "modes": ["1. Распознавание рифовых фаций (I–V)", "2. Эволюция во времени (биостром → биогерм → риф)", "3. Геометрия резервуара (СЗ–ЮВ, 1500×250 м)"],
                    "note": "Закрывает видеоёмкий узел Кузнецова без отдельного MP4 через интерактивную фациальную схему и проверку на данных.",
                },
                "question": "Куда по этим данным следует сместить проектную добывающую скважину и почему?",
                "options": [
                    {"id": "kuz_v", "label": "На борт в группу V (Ф=3–8%), чтобы избежать обводнения", "correct": False, "feedback": "Неверно: группа V имеет k < 3·10⁻¹⁵ м² — это практически непроницаемая вмещающая порода/покрышка."},
                    {"id": "kuz_i_ii", "label": "В ядро и пририфовый шлейф (группы I–II, k до 2000–30000·10⁻¹⁵ м²), контролируя отметку флюидного контакта", "correct": True, "feedback": "Верно! Наилучшие фильтрационно-ёмкостные свойства сосредоточены в органогенном каркасе (I) и обломочном шлейфе (II)."},
                ],
            }

        screens.append(
            StudyStepScreen(
                step_id=step_id,
                node_id=node.node_id,
                order=node.order,
                estimated_minutes=node.estimated_minutes,
                difficulty_codes=[node.primary_difficulty_code, node.secondary_difficulty_code],
                source_heading=node.source_heading,
                step_title=node.step_title,
                summary_2_3_sentences=node.summary_2_3_sentences,
                explanation_paragraphs=paragraphs,
                first_use_terms=node.core_terms,
                formulas_decoded=formulas_decoded,
                applicability_conditions=[node.nuances] + [q.conditions[0] for q in node.quotes_and_pages if q.conditions][:3],
                worked_example=node.worked_example,
                textbook_problems=node.textbook_problems,
                tables=step_tables,
                modern_context=node.modern_equivalents,
                it_analogy_and_limits=node.it_analogy_and_limits,
                typical_error=node.misconception_to_fix,
                epistemic_split=node.epistemic_split,
                specialist_manual_steps=node.specialist_manual_steps,
                decision_points=node.decision_points,
                inefficiency_lens=node.inefficiency_lens,
                deeper_branch=node.deeper_branch,
                illustration=illust,
                video_url=video_url,
                video_vtt_url=video_vtt_url,
                video_aspect=video_aspect,
                media_passport_id=passport_id,
                ocr_corrections_applied=node_ocrs,
                data_decision_card=data_decision_card,
            )
        )
    return screens


OFFLINE_CSS_VARIABLES_AND_STYLES = """
:root, [data-theme="dark"] {
  --lithos-bg: #090D16;
  --lithos-surface: #111827;
  --lithos-panel-bg: #1E293B;
  --lithos-illust-bg: #0F172A;
  --lithos-illust-border: #334155;
  --lithos-border: rgba(148, 163, 184, 0.22);
  --lithos-text-main: #F8FAFC;
  --lithos-text-secondary: #CBD5E1;
  --lithos-text-muted: #94A3B8;
  --lithos-accent: #2563EB;
  --lithos-accent-hover: #3B82F6;
  --lithos-cyan: #38BDF8;
  --lithos-emerald: #10B981;
  --lithos-amber: #F59E0B;
  --lithos-rose: #F43F5E;
  --lithos-focus-ring: #38BDF8;
}

[data-theme="light"] {
  --lithos-bg: #F8FAFC;
  --lithos-surface: #FFFFFF;
  --lithos-panel-bg: #F1F5F9;
  --lithos-illust-bg: #0F172A;
  --lithos-illust-border: #475569;
  --lithos-border: #CBD5E1;
  --lithos-text-main: #0F172A;
  --lithos-text-secondary: #1E293B;
  --lithos-text-muted: #475569;
  --lithos-accent: #1D4ED8;
  --lithos-accent-hover: #2563EB;
  --lithos-cyan: #0284C7;
  --lithos-emerald: #059669;
  --lithos-amber: #B45309;
  --lithos-rose: #E11D48;
  --lithos-focus-ring: #1D4ED8;
}

* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background-color: var(--lithos-bg);
  color: var(--lithos-text-main);
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 16px;
  line-height: 1.6;
}

button, select, input, a {
  font-family: inherit;
  font-size: 1rem;
}

p {
  max-width: 70ch;
}

.skip-link {
  position: absolute;
  left: -9999px;
  top: 8px;
  z-index: 9999;
  padding: 10px 16px;
  background: var(--lithos-accent);
  color: #FFFFFF;
  border-radius: 8px;
  font-weight: 700;
  text-decoration: none;
}
.skip-link:focus {
  left: 16px;
}

:focus-visible {
  outline: 3px solid var(--lithos-focus-ring) !important;
  outline-offset: 2px !important;
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}

.lithos-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 16px 20px 48px 20px;
}

.lithos-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  background: var(--lithos-surface);
  border: 1px solid var(--lithos-border);
  border-radius: 14px;
  margin-bottom: 16px;
}

.lithos-nav-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 18px;
}

.lithos-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid var(--lithos-border);
  background: var(--lithos-panel-bg);
  color: var(--lithos-text-main);
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  max-width: 100%;
  white-space: normal;
  text-align: left;
  overflow-wrap: anywhere;
}

.lithos-btn-primary {
  background: var(--lithos-accent);
  color: #FFFFFF;
  border-color: var(--lithos-accent);
}

.lithos-card {
  background: var(--lithos-surface);
  border: 1px solid var(--lithos-border);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 18px;
  max-width: 100%;
  overflow-wrap: anywhere;
}

.lithos-grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr));
  gap: 16px;
}

.lithos-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  border: 1px solid var(--lithos-border);
  background: var(--lithos-panel-bg);
}

.lithos-table-scroll {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--lithos-border);
  border-radius: 10px;
  margin: 12px 0;
}

.lithos-table {
  width: 100%;
  min-width: 580px;
  border-collapse: collapse;
  font-size: 1rem;
}

.lithos-table th, .lithos-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--lithos-border);
  text-align: left;
  vertical-align: top;
}

.lithos-table th {
  background: var(--lithos-panel-bg);
  font-weight: 700;
}

figure.lithos-figure {
  margin: 16px 0;
  padding: 12px;
  background: var(--lithos-panel-bg);
  border: 1px solid var(--lithos-border);
  border-radius: 12px;
}

figure.lithos-figure svg {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 8px;
}

figcaption.lithos-figcaption {
  margin-top: 10px;
  font-size: 1rem;
  color: var(--lithos-text-secondary);
  font-weight: 600;
}

.lithos-order-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--lithos-panel-bg);
  border: 1px solid var(--lithos-border);
  border-radius: 10px;
}

@media (max-width: 480px) {
  .lithos-container { padding: 10px 10px 36px 10px; }
  .lithos-card { padding: 14px; }
  .lithos-grid-2 { grid-template-columns: 1fr; }
}

@media print {
  .no-print { display: none !important; }
  body { background: #FFFFFF !important; color: #000000 !important; }
  .lithos-card { border: 1px solid #999 !important; page-break-inside: avoid; }
}
"""


def render_standalone_offline_html(package: StudyCoursePackage) -> str:
    """
    Генерирует полностью автономный index.html для пакета курса Т3 (работает по file:// без сервера и логина).
    """
    embedded_json = json.dumps(
        json.loads(package.model_dump_json()),
        ensure_ascii=False,
    ).replace("</script>", "<\\/script>")

    title_esc = html.escape(f"LITHOS · Глава: {package.chapter_title} ({package.book_title})")

    return f"""<!DOCTYPE html>
<html lang="ru" data-theme="dark">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title_esc}</title>
  <style>{OFFLINE_CSS_VARIABLES_AND_STYLES}</style>
</head>
<body>
  <a href="#main-view" class="skip-link">Перейти к основному содержимому</a>
  <div class="lithos-container">
    <header class="lithos-header">
      <div>
        <div style="font-size:1rem;color:var(--lithos-cyan);font-weight:700;">
          LITHOS · АВТОНОМНЫЙ КУРС Т3 · ИСТОЧНИК: {html.escape(package.book_title)}
        </div>
        <h1 style="margin:4px 0 0 0;font-size:1.35rem;">Глава: {html.escape(package.chapter_title)}</h1>
      </div>
      <div class="no-print" style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
        <span id="progress-badge" class="lithos-badge">Прогресс главы: 0%</span>
        <button type="button" id="btn-return-step" class="lithos-btn" onclick="returnToSavedStep()">
          Вернуться к шагу
        </button>
        <button type="button" id="btn-theme-toggle" class="lithos-btn" onclick="toggleTheme()" aria-label="Переключить светлую или тёмную тему">
          Светлая / Тёмная тема
        </button>
        <button type="button" class="lithos-btn" onclick="window.print()">
          Печать конспекта
        </button>
      </div>
    </header>

    <nav class="lithos-nav-tabs no-print" aria-label="Разделы автономного курса">
      <button type="button" class="lithos-btn lithos-btn-primary" id="tab-steps" onclick="switchTab('steps')">
        Шаги главы ({len(package.steps)})
      </button>
      {('<button type="button" class="lithos-btn" id="tab-practicum" onclick="switchTab(\'practicum\')">Практикум: два зонда</button>' if package.practicum else '')}
      <button type="button" class="lithos-btn" id="tab-links" onclick="switchTab('links')">
        Карта связей
      </button>
      <button type="button" class="lithos-btn" id="tab-tasks" onclick="switchTab('tasks')">
        Задания ({len(package.tasks)})
      </button>
      <button type="button" class="lithos-btn" id="tab-cards" onclick="switchTab('cards')">
        Карточки: Знаю / Повторить ({len(package.flashcards)})
      </button>
      <button type="button" class="lithos-btn" id="tab-notes" onclick="switchTab('notes')">
        Конспект
      </button>
      <button type="button" class="lithos-btn" id="tab-source" onclick="switchTab('source')">
        Источник, OCR и паспорт ролика
      </button>
    </nav>

    <!-- Маршрут по шагам (навигационный индикатор) -->
    <div id="step-route-bar" class="lithos-card no-print" style="padding:12px 16px;">
      <div style="font-weight:700;margin-bottom:8px;">Маршрут главы (выберите шаг):</div>
      <div id="step-buttons" style="display:flex;flex-wrap:wrap;gap:8px;"></div>
    </div>

    <!-- Основная область отображения активной вкладки -->
    <main id="main-view" aria-live="polite"></main>
  </div>

  <script id="lithos-course-data" type="application/json">{embedded_json}</script>
  <script>
    const COURSE = JSON.parse(document.getElementById("lithos-course-data").textContent);
    const STORAGE_KEY = "lithos_t3_state_" + COURSE.course_id;

    let state = {{
      theme: "dark",
      activeTab: "steps",
      currentStepIdx: 0,
      lastVisitedStepIdx: 0,
      completedSteps: {{}},
      cardStates: {{}},
      taskAnswers: {{}},
      taskHintsShown: {{}},
      orderingState: {{}},
      practicum: {{
        forecastIdx: null,
        rhoFKey: "1.20",
        conclusionId: null,
        conclusionHintShown: false,
        transferId: null,
        transferHintShown: false
      }}
    }};

    function loadState() {{
      try {{
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {{
          const parsed = JSON.parse(raw);
          state = Object.assign(state, parsed);
          if (!state.practicum) {{
            state.practicum = {{ forecastIdx: null, rhoFKey: "1.20", conclusionId: null, conclusionHintShown: false, transferId: null, transferHintShown: false }};
          }}
        }}
      }} catch (e) {{}}
      document.documentElement.setAttribute("data-theme", state.theme || "dark");
    }}

    function saveState() {{
      try {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      }} catch (e) {{}}
      updateProgressBadge();
    }}

    function toggleTheme() {{
      state.theme = state.theme === "dark" ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", state.theme);
      saveState();
    }}

    function returnToSavedStep() {{
      state.activeTab = "steps";
      state.currentStepIdx = state.lastVisitedStepIdx || 0;
      saveState();
      renderAll();
    }}

    function updateProgressBadge() {{
      const totalSteps = COURSE.steps.length || 1;
      const doneSteps = Object.keys(state.completedSteps).length;
      const pct = Math.min(100, Math.round((doneSteps / totalSteps) * 100));
      const el = document.getElementById("progress-badge");
      if (el) el.textContent = "Прогресс главы: " + pct + "% (" + doneSteps + "/" + totalSteps + " шагов)";
    }}

    function switchTab(tab) {{
      state.activeTab = tab;
      saveState();
      renderAll();
    }}

    function selectStep(idx) {{
      state.currentStepIdx = idx;
      state.lastVisitedStepIdx = idx;
      state.completedSteps[COURSE.steps[idx].step_id] = true;
      saveState();
      renderAll();
    }}

    function pickDataDecision(stepId, optId) {{
      if (!state.dataDecisions) state.dataDecisions = {{}};
      state.dataDecisions[stepId] = optId;
      saveState();
      render();
    }}

    function setPracticumForecast(idx) {{
      state.practicum.forecastIdx = idx;
      saveState();
      renderAll();
    }}

    function setPracticumRhoF(key) {{
      state.practicum.rhoFKey = String(key);
      saveState();
      renderAll();
    }}

    function setPracticumConclusion(optId) {{
      state.practicum.conclusionId = optId;
      saveState();
      renderAll();
    }}

    function togglePracticumConclusionHint() {{
      state.practicum.conclusionHintShown = true;
      saveState();
      renderAll();
    }}

    function setPracticumTransfer(optId) {{
      state.practicum.transferId = optId;
      saveState();
      renderAll();
    }}

    function togglePracticumTransferHint() {{
      state.practicum.transferHintShown = true;
      saveState();
      renderAll();
    }}

    function buildPracticumSvg(curState) {{
      const depths = curState.curves.depth_m;
      const bk = curState.curves.rho_bk_ohmm;
      const mbk = curState.curves.rho_mbk_ohmm;
      const asp = curState.curves.alpha_sp;
      const minZ = depths[0], maxZ = depths[depths.length - 1];
      const mapY = (z) => 52 + ((z - minZ) / Math.max(1, maxZ - minZ)) * 270;
      const mapXLog = (val) => 310 + Math.max(0, Math.min(200, ((Math.log10(Math.max(val, 0.3)) - Math.log10(0.3)) / (Math.log10(150) - Math.log10(0.3))) * 200));
      const mapXSp = (val) => 170 + Math.max(0, Math.min(100, val * 100));

      let ptsBk = "", ptsMbk = "", ptsSp = "";
      for (let i = 0; i < depths.length; i++) {{
        const y = mapY(depths[i]).toFixed(1);
        ptsBk += mapXLog(bk[i]).toFixed(1) + "," + y + " ";
        ptsMbk += mapXLog(mbk[i]).toFixed(1) + "," + y + " ";
        ptsSp += mapXSp(asp[i]).toFixed(1) + "," + y + " ";
      }}
      const vnkY = mapY(curState.parameters.vnk_depth_m).toFixed(1);
      const y2409 = mapY(2409).toFixed(1), y2416 = mapY(2416).toFixed(1), y2433 = mapY(2433).toFixed(1), y2441 = mapY(2441).toFixed(1);

      return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 365" role="img" aria-label="Синхронный разрез и кривые двух зондов БК и МБК">'
        + '<rect x="2" y="2" width="756" height="361" rx="12" fill="#0F172A" stroke="#334155" stroke-width="1.5"/>'
        + '<text x="18" y="28" fill="#F8FAFC" font-size="16" font-weight="700">Разрез интервала 2408–2442 м и две кривые сопротивления (ρ_ф = ' + curState.parameters.rho_f_ohmm + ' Ом·м)</text>'
        + '<text x="18" y="46" fill="#94A3B8" font-size="14">1. Разрез</text>'
        + '<text x="168" y="46" fill="#38BDF8" font-size="14">2. α_СП (0–1)</text>'
        + '<text x="308" y="46" fill="#10B981" font-size="14">3. ρ_БК (зелён.) vs ρ_МБК (оранж., лог. Ом·м)</text>'
        + '<rect x="18" y="' + y2409 + '" width="128" height="' + (y2416 - y2409) + '" fill="#64748B" opacity="0.7"/><text x="24" y="' + ((+y2409 + +y2416)/2 + 5) + '" fill="#F8FAFC" font-size="13" font-weight="700">Плотный (некол.)</text>'
        + '<rect x="18" y="' + y2416 + '" width="128" height="' + (vnkY - y2416) + '" fill="#10B981" opacity="0.75"/><text x="24" y="' + ((+y2416 + +vnkY)/2 + 5) + '" fill="#0F172A" font-size="13" font-weight="700">Коллектор: Нефть</text>'
        + '<rect x="18" y="' + vnkY + '" width="128" height="' + (y2433 - vnkY) + '" fill="#0284C7" opacity="0.75"/><text x="24" y="' + ((+vnkY + +y2433)/2 + 5) + '" fill="#F8FAFC" font-size="13" font-weight="700">Коллектор: Вода</text>'
        + '<rect x="18" y="' + y2433 + '" width="128" height="' + (y2441 - y2433) + '" fill="#475569" opacity="0.8"/><text x="24" y="' + ((+y2433 + +y2441)/2 + 5) + '" fill="#E2E8F0" font-size="13">Глины</text>'
        + '<line x1="215" y1="52" x2="215" y2="322" stroke="#F59E0B" stroke-dasharray="5 3" stroke-width="1.6"/>'
        + '<polyline fill="none" stroke="#38BDF8" stroke-width="3" points="' + ptsSp + '"/>'
        + '<polyline fill="none" stroke="#10B981" stroke-width="3.5" points="' + ptsBk + '"/>'
        + '<polyline fill="none" stroke="#F59E0B" stroke-width="2.8" stroke-dasharray="6 3" points="' + ptsMbk + '"/>'
        + '<line x1="168" y1="' + vnkY + '" x2="520" y2="' + vnkY + '" stroke="#F43F5E" stroke-width="2" stroke-dasharray="6 3"/>'
        + '<text x="530" y="' + (+vnkY + 5) + '" fill="#F43F5E" font-size="14" font-weight="700">ВНК = 2425 м</text>'
        + '<rect x="530" y="64" width="212" height="250" rx="10" fill="#1E293B" stroke="#334155"/>'
        + '<text x="542" y="90" fill="#38BDF8" font-size="14" font-weight="700">Расчёт из 1 модели:</text>'
        + '<text x="542" y="118" fill="#F8FAFC" font-size="14">ΔE_ст = ' + curState.parameters.delta_e_max_mv + ' мВ</text>'
        + '<text x="542" y="146" fill="#10B981" font-size="14">2420м (нефть):</text>'
        + '<text x="542" y="166" fill="#F8FAFC" font-size="14">ρ_БК=' + curState.key_zones.oil_zone_2420m.rho_bk_ohmm + ', ρ_МБК=' + curState.key_zones.oil_zone_2420m.rho_mbk_ohmm + '</text>'
        + '<text x="542" y="186" fill="#F8FAFC" font-size="14">P_н=' + curState.key_zones.oil_zone_2420m.p_n + ', K_нг=' + Math.round(curState.key_zones.oil_zone_2420m.k_ng*100) + '%</text>'
        + '<text x="542" y="218" fill="#38BDF8" font-size="14">2429м (вода):</text>'
        + '<text x="542" y="238" fill="#F8FAFC" font-size="14">ρ_БК=' + curState.key_zones.water_zone_2429m.rho_bk_ohmm + ', ρ_МБК=' + curState.key_zones.water_zone_2429m.rho_mbk_ohmm + '</text>'
        + '<text x="542" y="264" fill="#94A3B8" font-size="13">2412м (плотный):</text>'
        + '<text x="542" y="284" fill="#F8FAFC" font-size="13">α_СП=' + curState.key_zones.tight_layer_2412m.alpha_sp + ' (&lt;0,45)</text>'
        + '<text x="18" y="348" fill="#94A3B8" font-size="13">Симуляция (simulate_well_log) · ■ #10B981 Нефть/ρ_БК  ■ #F59E0B Отсечка/ρ_МБК  ■ #0284C7 Вода  ■ #F43F5E ВНК</text>'
        + '</svg>';
    }}

    function renderPracticumBlock(pr) {{
      if (!pr) return "";
      const pCtrl = pr.step3_parameter_control;
      const baseEntry = pCtrl.preset_states[pCtrl.baseline_key];
      const curKey = state.practicum.rhoFKey || pCtrl.baseline_key;
      const curEntry = pCtrl.preset_states[curKey] || baseEntry;
      const baseSt = baseEntry.state;
      const curSt = curEntry.state;

      let h = '<section id="practicum-two-probes" class="lithos-card" style="border:2px solid var(--lithos-cyan);">';
      h += '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;margin-bottom:10px;">';
      h += '<span class="lithos-badge" style="border-color:var(--lithos-amber);color:var(--lithos-amber);">' + pr.data_origin_badge + '</span>';
      h += '<span class="lithos-badge">Связь со слоем: ' + pr.linked_node_id + ' / ' + pr.linked_claim_id + '</span>';
      h += '</div>';
      h += '<h2 style="margin:6px 0 8px 0;font-size:1.45rem;">' + pr.title + '</h2>';
      h += '<p style="margin:0 0 12px 0;">' + pr.subtitle + '</p>';

      // Шаг 1 практикума: две кривые, разрез и явное разделение Измерено / Рассчитано / Допущения
      h += '<figure class="lithos-figure">' + buildPracticumSvg(curSt);
      h += '<figcaption class="lithos-figcaption">Рисунок практикума: две каротажные кривые (ρ_БК и ρ_МБК) и разрез интервала 2408–2442 м из единого состояния модели (Симуляция по М.Г. Латышовой, 1991, §1, §20, стр. 9–16, 96–108).</figcaption></figure>';

      h += '<div class="lithos-grid-2" style="margin:12px 0;">';
      h += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);"><strong>Измерено (кривые):</strong><ul style="margin:6px 0 0 20px;">';
      pr.epistemic_roles.measured.forEach((x) => {{ h += '<li>' + x + '</li>'; }});
      h += '</ul></div>';
      h += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);"><strong>Рассчитано и допущения модели:</strong><ul style="margin:6px 0 0 20px;">';
      pr.epistemic_roles.calculated.slice(0, 2).forEach((x) => {{ h += '<li><em>Расчёт:</em> ' + x + '</li>'; }});
      pr.epistemic_roles.assumptions.slice(0, 2).forEach((x) => {{ h += '<li><em>Допущение:</em> ' + x + '</li>'; }});
      h += '</ul></div></div>';

      // Шаг 2 практикума: Прогноз ДО раскрытия результата
      h += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
      h += '<h3 style="margin-top:0;">Этап 2. Прогноз до раскрытия результата</h3>';
      h += '<p style="font-weight:700;">' + pr.step2_forecast.question + '</p>';
      pr.step2_forecast.options.forEach((opt, idx) => {{
        const picked = state.practicum.forecastIdx === idx;
        h += '<button type="button" class="lithos-btn" style="display:block;width:100%;text-align:left;margin-bottom:8px;' + (picked ? 'border:2px solid var(--lithos-cyan);' : '') + '" onclick="setPracticumForecast(' + idx + ')">' + (idx + 1) + '. ' + opt + '</button>';
      }});
      if (state.practicum.forecastIdx !== null) {{
        h += '<p style="color:var(--lithos-emerald);font-weight:700;margin:8px 0 0 0;">' + pr.step2_forecast.forecast_feedback + '</p>';
      }}
      h += '</div>';

      // Шаг 3 практикума: Изменение параметра ρ_ф и сравнение Исходного vs Изменённого состояния
      h += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
      h += '<h3 style="margin-top:0;">Этап 3. Измените параметр и сравните исходное и изменённое состояния</h3>';
      h += '<p><strong>Параметр:</strong> ' + pCtrl.parameter_name + '. ' + pCtrl.parameter_rationale + '</p>';
      h += '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px;">';
      pCtrl.presets.forEach((p) => {{
        const pKey = Number(p.rho_f).toFixed(2);
        const isAct = pKey === curKey;
        h += '<button type="button" class="lithos-btn' + (isAct ? ' lithos-btn-primary' : '') + '" onclick="setPracticumRhoF(\\'' + pKey + '\\')">ρ_ф = ' + pKey + ' Ом·м (' + p.mud_type + ')</button>';
      }});
      h += '</div>';

      h += '<div class="lithos-table-scroll"><table class="lithos-table"><thead><tr><th>Показатель единой модели</th><th>Исходное состояние (ρ_ф = 1,20 Ом·м)</th><th>Текущее состояние (ρ_ф = ' + curSt.parameters.rho_f_ohmm + ' Ом·м)</th></tr></thead><tbody>';
      h += '<tr><td>Статическая амплитуда СП ΔE_ст</td><td>' + baseSt.parameters.delta_e_max_mv + ' мВ</td><td><strong>' + curSt.parameters.delta_e_max_mv + ' мВ</strong></td></tr>';
      h += '<tr><td>Нефтяная зона (2420 м): ρ_БК / ρ_МБК</td><td>' + baseSt.key_zones.oil_zone_2420m.rho_bk_ohmm + ' / ' + baseSt.key_zones.oil_zone_2420m.rho_mbk_ohmm + ' Ом·м (' + baseSt.key_zones.oil_zone_2420m.invasion_profile + ')</td><td><strong>' + curSt.key_zones.oil_zone_2420m.rho_bk_ohmm + ' / ' + curSt.key_zones.oil_zone_2420m.rho_mbk_ohmm + ' Ом·м (' + curSt.key_zones.oil_zone_2420m.invasion_profile + ')</strong></td></tr>';
      h += '<tr><td>Водоносная зона (2429 м): ρ_БК / ρ_МБК</td><td>' + baseSt.key_zones.water_zone_2429m.rho_bk_ohmm + ' / ' + baseSt.key_zones.water_zone_2429m.rho_mbk_ohmm + ' Ом·м (' + baseSt.key_zones.water_zone_2429m.invasion_profile + ')</td><td><strong>' + curSt.key_zones.water_zone_2429m.rho_bk_ohmm + ' / ' + curSt.key_zones.water_zone_2429m.rho_mbk_ohmm + ' Ом·м (' + curSt.key_zones.water_zone_2429m.invasion_profile + ')</strong></td></tr>';
      h += '<tr><td>Нефтенасыщение K_нг и параметр P_н (2420 м)</td><td>P_н = ' + baseSt.key_zones.oil_zone_2420m.p_n + ', K_нг = ' + Math.round(baseSt.key_zones.oil_zone_2420m.k_ng*100) + '%</td><td><strong>P_н = ' + curSt.key_zones.oil_zone_2420m.p_n + ', K_нг = ' + Math.round(curSt.key_zones.oil_zone_2420m.k_ng*100) + '%</strong></td></tr>';
      h += '</tbody></table></div></div>';

      // Шаг 4 и 5 практикума: Вывод по схеме «признаки → правило → вывод» и разбор границ метода
      h += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
      h += '<h3 style="margin-top:0;">Этап 4–5. Вывод и обоснование («признаки → правило → вывод»)</h3>';
      h += '<p style="font-weight:700;">' + pr.step4_conclusion.prompt + '</p>';
      h += '<div style="margin-bottom:10px;"><button type="button" class="lithos-btn" onclick="togglePracticumConclusionHint()">Наводящая подсказка (без раскрытия ответа)</button>';
      if (state.practicum.conclusionHintShown) {{
        h += '<p style="color:var(--lithos-cyan);margin:8px 0 0 0;">' + pr.step4_conclusion.hint_non_spoiler + '</p>';
      }}
      h += '</div>';
      pr.step4_conclusion.options.forEach((opt, idx) => {{
        const picked = state.practicum.conclusionId === opt.id;
        h += '<button type="button" class="lithos-btn" style="display:block;width:100%;text-align:left;margin-bottom:8px;' + (picked ? 'border:2px solid var(--lithos-cyan);' : '') + '" onclick="setPracticumConclusion(\\'' + opt.id + '\\')">' + (idx + 1) + '. ' + opt.text + '</button>';
      }});
      if (state.practicum.conclusionId) {{
        const chosenOpt = pr.step4_conclusion.options.find((o) => o.id === state.practicum.conclusionId);
        const deb = pr.step4_conclusion.step5_debrief;
        h += '<div style="margin-top:12px;padding:14px;border-radius:10px;border:2px solid ' + (chosenOpt && chosenOpt.is_correct ? 'var(--lithos-emerald)' : 'var(--lithos-amber)') + ';">';
        h += '<p style="margin:0 0 8px 0;"><strong>' + (chosenOpt && chosenOpt.is_correct ? 'Верный вывод!' : 'Ошибочный вывод (слишком уверенный вывод по одному признаку или неверное правило).') + '</strong></p>';
        h += '<p style="margin:0 0 8px 0;"><strong>Верный шаг рассуждения:</strong> ' + deb.what_was_right + '</p>';
        if (!chosenOpt || !chosenOpt.is_correct) {{
          h += '<p style="margin:0 0 8px 0;color:var(--lithos-amber);"><strong>Разбор ошибки:</strong> ' + deb.wrong_option_explanation + '</p>';
        }}
        h += '<p style="margin:0 0 8px 0;"><strong>Где заканчиваются возможности метода:</strong> ' + deb.method_limits + '</p>';
        h += '<p style="margin:0 0 4px 0;"><strong>Какие дополнительные данные нужны:</strong></p><ul style="margin:0 0 8px 20px;">';
        deb.missing_data_needed.forEach((md) => {{ h += '<li>' + md + '</li>'; }});
        h += '</ul><p style="margin:0;"><strong>Источник:</strong> ' + deb.source_ref + '</p></div>';
      }}
      h += '</div>';

      // Шаг 6 практикума: Задача на перенос с изменёнными условиями
      h += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
      h += '<h3 style="margin-top:0;">Этап 6. Задача на перенос (изменённые условия: солёный раствор ρ_ф = ρ_в)</h3>';
      h += '<p style="font-weight:700;">' + pr.step6_transfer_task.prompt + '</p>';
      h += '<div style="margin-bottom:10px;"><button type="button" class="lithos-btn" onclick="togglePracticumTransferHint()">Подсказка к задаче на перенос</button>';
      if (state.practicum.transferHintShown) {{
        h += '<p style="color:var(--lithos-cyan);margin:8px 0 0 0;">' + pr.step6_transfer_task.hint_non_spoiler + '</p>';
      }}
      h += '</div>';
      pr.step6_transfer_task.options.forEach((opt, idx) => {{
        const picked = state.practicum.transferId === opt.id;
        h += '<button type="button" class="lithos-btn" style="display:block;width:100%;text-align:left;margin-bottom:8px;' + (picked ? 'border:2px solid var(--lithos-cyan);' : '') + '" onclick="setPracticumTransfer(\\'' + opt.id + '\\')">' + (idx + 1) + '. ' + opt.text + '</button>';
      }});
      if (state.practicum.transferId) {{
        const trChosen = pr.step6_transfer_task.options.find((o) => o.id === state.practicum.transferId);
        h += '<div style="margin-top:10px;padding:12px;border-radius:10px;border:2px solid ' + (trChosen && trChosen.is_correct ? 'var(--lithos-emerald)' : 'var(--lithos-amber)') + ';">';
        h += '<p style="margin:0 0 6px 0;"><strong>' + (trChosen && trChosen.is_correct ? 'Перенос правила выполнен верно!' : 'Проверьте физику солёного раствора на модели выше.') + '</strong></p>';
        h += '<p style="margin:0 0 6px 0;">' + pr.step6_transfer_task.explanation + '</p>';
        h += '<p style="margin:0;"><strong>Источник:</strong> ' + pr.step6_transfer_task.source_ref + '</p></div>';
      }}
      h += '</div></section>';
      return h;
    }}

    function renderStepButtons() {{
      const container = document.getElementById("step-buttons");
      if (!container) return;
      container.innerHTML = "";
      COURSE.steps.forEach((st, idx) => {{
        const btn = document.createElement("button");
        btn.type = "button";
        const isCur = idx === state.currentStepIdx && state.activeTab === "steps";
        const isDone = !!state.completedSteps[st.step_id];
        const mins = st.estimated_minutes || 8;
        const codes = (st.difficulty_codes && st.difficulty_codes.length) ? (" [" + st.difficulty_codes.join("/") + "]") : "";
        btn.className = "lithos-btn" + (isCur ? " lithos-btn-primary" : "");
        btn.textContent = "Шаг " + st.order + " (~" + mins + " мин)" + codes + ": " + st.step_title + (isDone ? " ✓" : "");
        btn.onclick = () => {{ state.activeTab = "steps"; selectStep(idx); }};
        container.appendChild(btn);
      }});
    }}

    function renderActiveStep() {{
      const st = COURSE.steps[state.currentStepIdx] || COURSE.steps[0];
      state.completedSteps[st.step_id] = true;
      saveState();

      let htmlOut = '<article class="lithos-card">';
      htmlOut += '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;margin-bottom:8px;">';
      htmlOut += '<span class="lithos-badge">Шаг ' + st.order + ' из ' + COURSE.steps.length + ' · ID: ' + st.step_id + '</span>';
      htmlOut += '<span class="lithos-badge">Заголовок источника: ' + st.source_heading + '</span>';
      htmlOut += '</div>';
      htmlOut += '<h2 style="margin:6px 0 10px 0;font-size:1.5rem;">' + st.step_title + '</h2>';
      htmlOut += '<p style="font-size:1.08rem;font-weight:600;color:var(--lithos-cyan);margin-bottom:14px;">Суть шага: ' + st.summary_2_3_sentences + '</p>';

      // Предметная иллюстрация (Класс A/B/C/D) с подписью перерисовки
      if (st.illustration) {{
        htmlOut += '<figure class="lithos-figure">';
        htmlOut += st.illustration.svg_markup;
        htmlOut += '<figcaption class="lithos-figcaption">';
        htmlOut += 'Иллюстрация (' + st.illustration.illustration_id + ', класс ' + st.illustration.visual_class + '): ';
        htmlOut += st.illustration.title + ' — <strong>' + st.illustration.redraw_caption + '</strong> ';
        htmlOut += '(Источник: ' + st.illustration.source_ref + ', PDF стр. ' + st.illustration.pdf_page + ')';
        htmlOut += '</figcaption></figure>';
      }}

      // Встроенный автономный практикум шага (если привязан к этому шагу)
      if (st.practicum) {{
        htmlOut += renderPracticumBlock(st.practicum);
      }}

      // Интерактивный блок «Решение на данных» (признаки -> правило -> вывод + границы правила + происхождение)
      if (st.data_decision_card) {{
        const dc = st.data_decision_card;
        if (!state.dataDecisions) state.dataDecisions = {{}};
        const chosenDc = state.dataDecisions[st.step_id] || null;
        htmlOut += '<section class="lithos-card" style="border:2px solid var(--lithos-emerald);background:var(--lithos-panel-bg);">';
        htmlOut += '<h3 style="margin-top:0;color:var(--lithos-emerald);">' + dc.title + '</h3>';
        htmlOut += '<p style="font-size:1rem;color:var(--lithos-text-muted);"><strong>Происхождение и допущения:</strong> ' + dc.origin_and_assumptions + '</p>';
        htmlOut += '<div style="margin:10px 0;"><strong>1. Наблюдаемые признаки по данным:</strong><ul style="margin:6px 0 0 18px;">';
        (dc.observed_features || []).forEach((f) => {{
          htmlOut += '<li><strong>' + f.label + ':</strong> ' + f.value + '</li>';
        }});
        htmlOut += '</ul></div>';
        htmlOut += '<p style="margin:8px 0;"><strong>2. Правило вывода:</strong> ' + dc.decision_rule + '</p>';
        htmlOut += '<p style="margin:8px 0;color:var(--lithos-amber);"><strong>3. Границы применимости правила:</strong> ' + dc.rule_limits + '</p>';
        if (dc.interactive_spec) {{
          htmlOut += '<div style="padding:8px 10px;border-radius:8px;background:var(--lithos-card-bg);margin:8px 0;"><strong>Интерактивная спецификация узла:</strong> ' + (dc.interactive_spec.modes || []).join(' · ') + ' — ' + dc.interactive_spec.note + '</div>';
        }}
        htmlOut += '<div style="margin-top:10px;"><strong>4. Проверьте решение:</strong> ' + dc.question + '</div>';
        htmlOut += '<div style="display:flex;flex-direction:column;gap:8px;margin-top:8px;">';
        (dc.options || []).forEach((o) => {{
          const active = chosenDc === o.id;
          htmlOut += '<button type="button" class="lithos-btn ' + (active ? 'lithos-btn-primary' : '') + '" style="text-align:left;" onclick="pickDataDecision(\\'' + st.step_id + '\\', \\'' + o.id + '\\')">' + o.label + '</button>';
        }});
        htmlOut += '</div>';
        if (chosenDc) {{
          const hit = (dc.options || []).find((o) => o.id === chosenDc);
          if (hit) {{
            htmlOut += '<div style="margin-top:10px;padding:10px;border-radius:8px;border:1px solid ' + (hit.correct ? 'var(--lithos-emerald)' : 'var(--lithos-rose)') + ';">' + hit.feedback + '</div>';
          }}
        }}
        htmlOut += '</section>';
      }}

      // Встроенный ролик шага (если привязан к шагу)
      if (st.video_url) {{
        htmlOut += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
        htmlOut += '<div style="font-weight:700;margin-bottom:8px;">Учебный видеоролик шага (' + (st.video_aspect || '16:9') + ') · Паспорт ролика: ' + (st.media_passport_id || '') + '</div>';
        htmlOut += '<video controls playsinline preload="metadata" style="max-width:100%;max-height:460px;border-radius:10px;background:#000;">';
        htmlOut += '<source src="' + st.video_url + '" type="video/mp4">';
        if (st.video_vtt_url) {{
          htmlOut += '<track kind="subtitles" srclang="ru" label="Русские субтитры" src="' + st.video_vtt_url + '" default>';
        }}
        htmlOut += '</video>';
        htmlOut += '</div>';
      }}

      // Абзацы объяснения со ссылками на оригинал
      htmlOut += '<h3>Объяснение с привязкой к источнику</h3>';
      st.explanation_paragraphs.forEach((p) => {{
        htmlOut += '<div style="margin-bottom:12px;padding:12px;border-left:4px solid var(--lithos-accent);background:var(--lithos-panel-bg);border-radius:8px;">';
        htmlOut += '<div style="font-weight:700;">' + p.role + ' <span class="lithos-badge">' + p.source_citation + '</span></div>';
        htmlOut += '<p style="margin:6px 0;">' + p.text + '</p>';
        if (p.verbatim_quote) {{
          htmlOut += '<div style="font-size:1rem;color:var(--lithos-text-muted);">Цитата оригинала (стр. ' + p.pdf_page + '): «' + p.verbatim_quote.slice(0, 260) + '»</div>';
        }}
        htmlOut += '</div>';
      }});

      // Разделение: Наблюдение / Вывод / Допущение
      htmlOut += '<div class="lithos-grid-2" style="margin-top:14px;">';
      htmlOut += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);">';
      htmlOut += '<strong>Наблюдение (Измерение):</strong><p style="margin:4px 0;">' + st.epistemic_split.observation + '</p>';
      htmlOut += '<strong>Вывод (Вычисление):</strong><p style="margin:4px 0;">' + st.epistemic_split.inference + '</p>';
      htmlOut += '<strong>Допущение модели:</strong><p style="margin:4px 0;">' + st.epistemic_split.assumption + '</p>';
      htmlOut += '</div>';

      // ИТ-аналогия и типичная ошибка
      htmlOut += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);">';
      htmlOut += '<strong>ИТ-аналогия и её границы:</strong><p style="margin:4px 0;">' + st.it_analogy_and_limits + '</p>';
      htmlOut += '<strong style="color:var(--lithos-amber);">Типичная ошибка (заблуждение):</strong><p style="margin:4px 0;">' + st.typical_error + '</p>';
      htmlOut += '<strong>Ветка «Глубже»:</strong><p style="margin:4px 0;">' + st.deeper_branch + '</p>';
      htmlOut += '</div></div>';

      // Термины при первом употреблении и таблица (адаптивная для 390 px и 1280 px)
      st.tables.forEach((tbl) => {{
        htmlOut += '<h3 style="margin-top:18px;">' + tbl.title + '</h3>';
        htmlOut += '<div class="lithos-table-scroll"><table class="lithos-table"><thead><tr>';
        tbl.headers.forEach((h) => {{ htmlOut += '<th>' + h + '</th>'; }});
        htmlOut += '</tr></thead><tbody>';
        tbl.rows.forEach((row) => {{
          htmlOut += '<tr>';
          row.forEach((cell) => {{ htmlOut += '<td>' + cell + '</td>'; }});
          htmlOut += '</tr>';
        }});
        htmlOut += '</tbody></table></div>';
      }});

      // Авторский разобранный пример и ручные шаги специалиста
      htmlOut += '<div class="lithos-grid-2" style="margin-top:16px;">';
      htmlOut += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);">';
      htmlOut += '<strong>Ручные шаги специалиста:</strong><ol style="margin:6px 0 10px 20px;">';
      st.specialist_manual_steps.forEach((ms) => {{ htmlOut += '<li>' + ms + '</li>'; }});
      htmlOut += '</ol><strong>Точки принятия решения:</strong><ul style="margin:6px 0 0 20px;">';
      st.decision_points.forEach((dp) => {{ htmlOut += '<li>' + dp + '</li>'; }});
      htmlOut += '</ul></div>';

      if (st.worked_example && st.worked_example.status === "present") {{
        htmlOut += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);">';
        htmlOut += '<strong>Разобранный пример (' + st.worked_example.problem_number + ', ' + st.worked_example.figure_ref + ', стр. ' + st.worked_example.pdf_page + '):</strong>';
        htmlOut += '<p style="margin:6px 0;"><em>Условия:</em> ' + st.worked_example.conditions + '</p><ol style="margin:6px 0 6px 20px;">';
        st.worked_example.steps.forEach((es) => {{ htmlOut += '<li>' + es + '</li>'; }});
        htmlOut += '</ol><p style="margin:6px 0;"><strong>Итог:</strong> ' + st.worked_example.result + '</p></div>';
      }}
      htmlOut += '</div>';

      // Современный контекст
      if (st.modern_context && st.modern_context.length > 0) {{
        htmlOut += '<div style="margin-top:14px;padding:12px;border-radius:10px;background:var(--lithos-panel-bg);">';
        htmlOut += '<strong>Современный контекст исторической аппаратуры:</strong> ';
        st.modern_context.forEach((mc) => {{
          htmlOut += mc.historical_item + ' (' + mc.historical_context + ') → <strong>' + mc.modern_analog + '</strong> (' + mc.modern_context + '). ';
        }});
        htmlOut += '</div>';
      }}

      // Навигация Предыдущий / Следующий шаг
      htmlOut += '<div class="no-print" style="display:flex;justify-content:space-between;margin-top:20px;">';
      if (state.currentStepIdx > 0) {{
        htmlOut += '<button type="button" class="lithos-btn" onclick="selectStep(' + (state.currentStepIdx - 1) + ')">← Предыдущий шаг</button>';
      }} else {{ htmlOut += '<span></span>'; }}
      if (state.currentStepIdx < COURSE.steps.length - 1) {{
        htmlOut += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="selectStep(' + (state.currentStepIdx + 1) + ')">Следующий шаг →</button>';
      }} else {{
        htmlOut += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="switchTab(\\'tasks\\')">Перейти к заданиям (' + COURSE.tasks.length + ') →</button>';
      }}
      htmlOut += '</div></article>';
      return htmlOut;
    }}

    function renderLinksTab() {{
      let out = '<section class="lithos-card"><h2>Карта типизированных связей между узлами главы</h2>';
      out += '<p>Показывает порядок предпосылок (prerequisite), переход от механизма к практике и перенос в данные:</p>';
      COURSE.layer.nodes.forEach((nd) => {{
        out += '<div style="padding:12px;margin-bottom:10px;border-radius:10px;background:var(--lithos-panel-bg);">';
        out += '<strong>Шаг ' + nd.order + '. ' + nd.step_title + ' (' + nd.node_id + ')</strong>';
        out += '<div style="font-size:1rem;color:var(--lithos-text-secondary);">Обоснование порядка: ' + nd.order_rationale + '</div>';
        if (nd.typed_links && nd.typed_links.length > 0) {{
          out += '<ul style="margin:6px 0 0 20px;">';
          nd.typed_links.forEach((lk) => {{
            out += '<li><span class="lithos-badge">' + lk.link_type + '</span> ' + lk.source_node_id + ' → ' + lk.target_node_id + ': ' + lk.rationale + '</li>';
          }});
          out += '</ul>';
        }}
        out += '</div>';
      }});
      out += '</section>';
      return out;
    }}

    function moveOrderingItem(taskId, index, delta) {{
      const task = COURSE.tasks.find((t) => t.task_id === taskId);
      if (!task) return;
      if (!state.orderingState[taskId]) {{
        state.orderingState[taskId] = task.ordering_items.slice();
      }}
      const arr = state.orderingState[taskId];
      const target = index + delta;
      if (target < 0 || target >= arr.length) return;
      const tmp = arr[index];
      arr[index] = arr[target];
      arr[target] = tmp;
      saveState();
      renderAll();
    }}

    function submitTaskAnswer(taskId, answerVal) {{
      state.taskAnswers[taskId] = answerVal;
      saveState();
      renderAll();
    }}

    function showLocalHint(taskId) {{
      const cur = state.taskHintsShown[taskId] || 0;
      state.taskHintsShown[taskId] = Math.min(3, cur + 1);
      saveState();
      renderAll();
    }}

    function renderTasksTab() {{
      let out = '<section class="lithos-card"><h2>Задания главы (' + COURSE.tasks.length + ' заданий · 5 типов Т3)</h2>';
      out += '<p>Каждое задание проверяется по утверждению учебного слоя. После ответа доступны ключ, объяснение, разбор ошибки и ссылка на источник. Локальные подсказки работают без сети.</p>';

      COURSE.tasks.forEach((t, idx) => {{
        const ans = state.taskAnswers[t.task_id];
        const hintLvl = state.taskHintsShown[t.task_id] || 0;
        out += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
        out += '<div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;">';
        out += '<span class="lithos-badge">Задание #' + (idx + 1) + ' · Тип: ' + t.task_type + ' · Уровень: ' + t.difficulty_level + '</span>';
        out += '<span class="lithos-badge">Утверждение: ' + t.claim_id + ' · PDF стр. ' + t.pdf_page + '</span>';
        out += '</div>';
        out += '<p style="font-weight:700;margin:10px 0;white-space:pre-line;">' + t.prompt + '</p>';

        if (t.task_type === "single_choice" || t.task_type === "case_decision") {{
          t.options.forEach((opt, oIdx) => {{
            const picked = ans === oIdx;
            out += '<button type="button" class="lithos-btn" style="display:block;width:100%;text-align:left;margin-bottom:8px;' + (picked ? 'border-color:var(--lithos-cyan);' : '') + '" onclick="submitTaskAnswer(\\'' + t.task_id + '\\', ' + oIdx + ')">';
            out += (oIdx + 1) + '. ' + opt + '</button>';
          }});
        }} else if (t.task_type === "multi_select") {{
          const selected = Array.isArray(ans) ? ans : [];
          out += '<div id="ms-wrap-' + t.task_id + '" style="margin-bottom:10px;">';
          t.options.forEach((opt, oIdx) => {{
            const checked = selected.includes(oIdx) ? " checked" : "";
            out += '<label style="display:flex;gap:10px;align-items:flex-start;padding:8px 10px;margin-bottom:6px;border-radius:8px;border:1px solid var(--lithos-border);cursor:pointer;">';
            out += '<input type="checkbox" value="' + oIdx + '"' + checked + ' style="margin-top:4px;min-width:18px;min-height:18px;" /> <span>' + (oIdx + 1) + '. ' + opt + '</span></label>';
          }});
          out += '</div>';
          out += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="submitTaskAnswer(\\'' + t.task_id + '\\', Array.from(document.querySelectorAll(\\'#ms-wrap-' + t.task_id + ' input:checked\\')).map(el => Number(el.value)))">Проверить выбор</button>';
        }} else if (t.task_type === "fill_in_blank") {{
          out += '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">';
          out += '<input type="text" id="blank-input-' + t.task_id + '" placeholder="Введите термин или обозначение" style="padding:8px 12px;border-radius:8px;border:1px solid var(--lithos-border);background:var(--lithos-surface);color:var(--lithos-text-main);min-width:240px;" value="' + (typeof ans === "string" ? ans.replace(/"/g, "&quot;") : "") + '" />';
          out += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="submitTaskAnswer(\\'' + t.task_id + '\\', document.getElementById(\\'blank-input-' + t.task_id + '\\').value.trim())">Проверить пропуск</button>';
          out += '</div>';
        }} else if (t.task_type === "ordering") {{
          if (!state.orderingState[t.task_id]) {{
            state.orderingState[t.task_id] = t.ordering_items.slice().reverse();
          }}
          const curOrder = state.orderingState[t.task_id];
          curOrder.forEach((itemTxt, iIdx) => {{
            out += '<div class="lithos-order-item" draggable="true">';
            out += '<span><strong>' + (iIdx + 1) + '.</strong> ' + itemTxt + '</span>';
            out += '<div style="display:flex;gap:6px;">';
            out += '<button type="button" class="lithos-btn" aria-label="Переместить шаг вверх" onclick="moveOrderingItem(\\'' + t.task_id + '\\', ' + iIdx + ', -1)">↑ Вверх</button>';
            out += '<button type="button" class="lithos-btn" aria-label="Переместить шаг вниз" onclick="moveOrderingItem(\\'' + t.task_id + '\\', ' + iIdx + ', 1)">↓ Вниз</button>';
            out += '</div></div>';
          }});
          out += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="submitTaskAnswer(\\'' + t.task_id + '\\', state.orderingState[\\'' + t.task_id + '\\'].slice())">Проверить порядок</button>';
        }} else if (t.task_type === "matching") {{
          out += '<div style="margin-bottom:10px;">';
          t.matching_pairs.forEach((pair) => {{
            out += '<div style="padding:6px 0;"><strong>' + pair.left + '</strong> ↔ ' + pair.right + '</div>';
          }});
          out += '</div>';
          out += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="submitTaskAnswer(\\'' + t.task_id + '\\', \\'matched\\')">Подтвердить и сверить сопоставление</button>';
        }} else if (t.task_type === "calculation") {{
          out += '<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">';
          out += '<input type="number" step="any" id="calc-input-' + t.task_id + '" placeholder="Введите число (' + t.calculation_unit + ')" style="padding:8px 12px;border-radius:8px;border:1px solid var(--lithos-border);background:var(--lithos-surface);color:var(--lithos-text-main);" value="' + (ans !== undefined ? ans : '') + '" />';
          out += '<span>' + t.calculation_unit + '</span>';
          out += '<button type="button" class="lithos-btn lithos-btn-primary" onclick="submitTaskAnswer(\\'' + t.task_id + '\\', parseFloat(document.getElementById(\\'calc-input-' + t.task_id + '\\').value))">Проверить расчёт</button>';
          out += '</div>';
        }}

        // Локальная подсказка без сети (размер шрифта строго 1rem = 16px)
        out += '<div style="margin-top:10px;">';
        out += '<button type="button" class="lithos-btn" onclick="showLocalHint(\\'' + t.task_id + '\\')">Локальная подсказка (' + hintLvl + '/3)</button>';
        if (hintLvl > 0 && t.hint_steps && t.hint_steps.length > 0) {{
          for (let h = 0; h < Math.min(hintLvl, t.hint_steps.length); h++) {{
            out += '<div style="margin-top:6px;font-size:1rem;color:var(--lithos-cyan);">Подсказка ' + (h + 1) + ': ' + t.hint_steps[h] + '</div>';
          }}
        }}
        out += '</div>';

        // Ключ, объяснение, разбор ошибки и ссылка на источник после ответа
        if (ans !== undefined) {{
          let isRight = false;
          if (t.task_type === "single_choice" || t.task_type === "case_decision") isRight = ans === t.correct_answer;
          else if (t.task_type === "multi_select") isRight = JSON.stringify((Array.isArray(ans) ? ans.slice().sort() : [])) === JSON.stringify((Array.isArray(t.correct_answer) ? t.correct_answer.slice().sort() : []));
          else if (t.task_type === "fill_in_blank") {{
            const norm = String(ans || "").trim().toLowerCase();
            const acc = (t.blank_acceptable_answers || [String(t.correct_answer || "").toLowerCase()]).map(s => String(s).toLowerCase());
            isRight = norm.length > 0 && acc.some(a => norm === a || norm.includes(a));
          }}
          else if (t.task_type === "ordering") isRight = JSON.stringify(ans) === JSON.stringify(t.correct_answer);
          else if (t.task_type === "matching") isRight = true;
          else if (t.task_type === "calculation") isRight = Math.abs(Number(ans) - Number(t.correct_answer)) <= t.calculation_tolerance;

          out += '<div style="margin-top:12px;padding:12px;border-radius:10px;border:1px solid ' + (isRight ? 'var(--lithos-emerald)' : 'var(--lithos-amber)') + ';">';
          out += '<div><strong>' + (isRight ? 'Верно!' : 'Требует исправления.') + ' Ключ ответа:</strong> ' + t.answer_key_display + '</div>';
          out += '<div style="margin-top:4px;"><strong>Объяснение:</strong> ' + t.explanation + '</div>';
          if (!isRight && t.error_analysis) {{
            const errTxt = t.error_analysis[String(ans)] || t.error_analysis["order_mismatch"] || t.error_analysis["wrong_value"] || "Проверьте условия применимости по источнику.";
            out += '<div style="margin-top:4px;color:var(--lithos-amber);"><strong>Разбор ошибки:</strong> ' + errTxt + '</div>';
          }}
          out += '<div style="margin-top:4px;font-size:1rem;color:var(--lithos-text-muted);"><strong>Источник:</strong> ' + t.source_ref + '</div>';
          out += '</div>';
        }}
        out += '</div>';
      }});
      out += '</section>';
      return out;
    }}

    function setCardStatus(cardId, status) {{
      state.cardStates[cardId] = status;
      saveState();
      renderAll();
    }}

    function renderCardsTab() {{
      let out = '<section class="lithos-card"><h2>Содержательные карточки (режимы «Знаю» и «Повторить»)</h2>';
      COURSE.flashcards.forEach((c) => {{
        const st = state.cardStates[c.card_id] || "repeat";
        out += '<div class="lithos-card" style="background:var(--lithos-panel-bg);">';
        out += '<div style="display:flex;justify-content:space-between;gap:8px;">';
        out += '<span class="lithos-badge">' + c.term_or_formula + ' · стр. ' + c.pdf_page + '</span>';
        out += '<span class="lithos-badge">' + (st === "know" ? "Статус: Знаю ✓" : "Статус: Повторить ↻") + '</span>';
        out += '</div>';
        out += '<p style="font-weight:700;margin:8px 0;">Вопрос: ' + c.front_question + '</p>';
        out += '<p style="margin:6px 0;"><strong>Ответ:</strong> ' + c.back_answer + '</p>';
        out += '<div style="display:flex;gap:8px;margin-top:10px;">';
        out += '<button type="button" class="lithos-btn' + (st === "know" ? " lithos-btn-primary" : "") + '" onclick="setCardStatus(\\'' + c.card_id + '\\', \\'know\\')">Знаю</button>';
        out += '<button type="button" class="lithos-btn' + (st === "repeat" ? " lithos-btn-primary" : "") + '" onclick="setCardStatus(\\'' + c.card_id + '\\', \\'repeat\\')">Повторить</button>';
        out += '</div></div>';
      }});
      out += '</section>';
      return out;
    }}

    function renderNotesTab() {{
      let out = '<section class="lithos-card"><h2>Конспект главы (для чтения и печати)</h2>';
      out += '<pre style="white-space:pre-wrap;font-family:inherit;font-size:1rem;">' + COURSE.summary_notes_markdown + '</pre>';
      out += '</section>';
      return out;
    }}

    function renderSourceTab() {{
      let out = '<section class="lithos-card"><h2>Источник, таблица «Шаг → Иллюстрация → Источник», лист исправлений OCR и Паспорт ролика</h2>';
      out += '<p><strong>Файл PDF:</strong> ' + COURSE.pdf_file + ' · <strong>SHA-256:</strong> <code>' + COURSE.layer.source_sha256 + '</code></p>';

      out += '<h3>Таблица соответствия «Шаг → Иллюстрация → Источник»</h3>';
      out += '<div class="lithos-table-scroll"><table class="lithos-table"><thead><tr><th>Шаг</th><th>Иллюстрация</th><th>Класс</th><th>Подпись перерисовки</th><th>Источник и стр.</th></tr></thead><tbody>';
      COURSE.routing_report.step_illustration_source_links.forEach((row) => {{
        out += '<tr><td>' + row.step_id + ' (' + row.step_title + ')</td><td>' + row.illustration_id + '</td><td>Класс ' + row.visual_class + '</td><td>' + row.redraw_caption + '</td><td>' + row.source_ref + ' (PDF стр. ' + row.pdf_page + ')</td></tr>';
      }});
      out += '</tbody></table></div>';

      out += '<h3>Лист исправлений OCR</h3>';
      out += '<div class="lithos-table-scroll"><table class="lithos-table"><thead><tr><th>ID</th><th>PDF стр.</th><th>Исходный OCR</th><th>Исправленное чтение</th><th>Основание</th><th>Шаг</th></tr></thead><tbody>';
      COURSE.layer.ocr_corrections.forEach((c) => {{
        out += '<tr><td>' + c.correction_id + '</td><td>' + c.pdf_page + ' (печ. ' + c.printed_page + ')</td><td>' + c.original_ocr + '</td><td><strong>' + c.corrected_reading + '</strong></td><td>' + c.rationale + '</td><td>' + c.applied_in_step_id + '</td></tr>';
      }});
      out += '</tbody></table></div>';

      if (COURSE.media_passports && COURSE.media_passports.length > 0) {{
        out += '<h3>Паспорт ролика</h3>';
        COURSE.media_passports.forEach((mp) => {{
          out += '<div style="padding:12px;border-radius:10px;background:var(--lithos-panel-bg);margin-bottom:12px;">';
          out += '<div><strong>Паспорт ролика:</strong> ' + mp.passport_id + ' · Формат: ' + mp.aspect_ratio + ' (' + mp.resolution + ', ' + mp.duration_sec + ' с)</div>';
          out += '<div><strong>Вопрос в первые 3 с:</strong> ' + mp.hook_question_0_3s + ' · <strong>Пауза предсказания:</strong> ' + mp.prediction_pause_sec + ' с (' + mp.prediction_pause_window + ')</div>';
          out += '<div><strong>Вопрос на перенос:</strong> ' + mp.transfer_question_end + '</div>';
          out += '<div><strong>Кадр в истинном масштабе:</strong> ' + mp.true_scale_frame_timecode + ' · <strong>Преувеличение:</strong> ' + mp.vertical_exaggeration_label + '</div>';
          out += '<div><strong>Звук:</strong> ' + mp.audio_report.integrated_lufs + ' LUFS, пик ' + mp.audio_report.true_peak_dbfs + ' dBFS, статус распознавания: ' + mp.audio_report.asr_verification_status + '</div>';
          out += '</div>';
        }});
      }}
      out += '</section>';
      return out;
    }}

    function renderAll() {{
      renderStepButtons();
      updateProgressBadge();
      const tabIds = ["steps", "practicum", "links", "tasks", "cards", "notes", "source"];
      tabIds.forEach((tid) => {{
        const btn = document.getElementById("tab-" + tid);
        if (btn) btn.className = "lithos-btn" + (state.activeTab === tid ? " lithos-btn-primary" : "");
      }});

      const main = document.getElementById("main-view");
      if (!main) return;
      if (state.activeTab === "steps") main.innerHTML = renderActiveStep();
      else if (state.activeTab === "practicum") main.innerHTML = renderPracticumBlock(COURSE.practicum);
      else if (state.activeTab === "links") main.innerHTML = renderLinksTab();
      else if (state.activeTab === "tasks") main.innerHTML = renderTasksTab();
      else if (state.activeTab === "cards") main.innerHTML = renderCardsTab();
      else if (state.activeTab === "notes") main.innerHTML = renderNotesTab();
      else if (state.activeTab === "source") main.innerHTML = renderSourceTab();
    }}

    loadState();
    renderAll();
  </script>
</body>
</html>
"""


def write_offline_package_and_zip(
    package: StudyCoursePackage,
    course_dir: Path,
    public_prefix: str = "",
) -> StudyCoursePackage:
    """
    Записывает все артефакты автономного курса Т3 в course_dir
    (index.html, layer.json, registry_report.json, routing_report.json, step_illustration_source.json,
     tasks.json, ocr_corrections.json, media_passports.json, illustrations/*.svg)
    и собирает автономный ZIP-архив (<30 МБ без видео).
    """
    course_dir.mkdir(parents=True, exist_ok=True)
    illust_dir = course_dir / "illustrations"
    illust_dir.mkdir(parents=True, exist_ok=True)

    for st in package.steps:
        svg_path = illust_dir / f"{st.illustration.illustration_id}.svg"
        if st.illustration.svg_markup:
            svg_path.write_text(st.illustration.svg_markup, encoding="utf-8")

    (course_dir / "layer.json").write_text(package.layer.model_dump_json(indent=2), encoding="utf-8")
    (course_dir / "registry_report.json").write_text(package.registry_report.model_dump_json(indent=2), encoding="utf-8")
    (course_dir / "routing_report.json").write_text(package.routing_report.model_dump_json(indent=2), encoding="utf-8")
    (course_dir / "step_illustration_source.json").write_text(
        json.dumps(package.routing_report.step_illustration_source_links, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (course_dir / "tasks.json").write_text(
        json.dumps([json.loads(t.model_dump_json()) for t in package.tasks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (course_dir / "ocr_corrections.json").write_text(
        json.dumps([json.loads(c.model_dump_json()) for c in package.layer.ocr_corrections], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (course_dir / "media_passports.json").write_text(
        json.dumps([json.loads(m.model_dump_json()) for m in package.media_passports], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (course_dir / "bookmark_report.json").write_text(package.bookmark_report.model_dump_json(indent=2), encoding="utf-8")
    (course_dir / "summary_notes.md").write_text(package.summary_notes_markdown, encoding="utf-8")

    import base64 as _b64

    vtt_originals: list[tuple[int, str | None]] = []
    for i, st in enumerate(package.steps):
        if st.video_vtt_url:
            vtt_file = course_dir / "media" / Path(st.video_vtt_url).name
            if vtt_file.exists():
                vtt_originals.append((i, st.video_vtt_url))
                st.video_vtt_url = "data:text/vtt;base64," + _b64.b64encode(vtt_file.read_bytes()).decode("ascii")

    html_content = render_standalone_offline_html(package)
    for i, orig_vtt in vtt_originals:
        package.steps[i].video_vtt_url = orig_vtt
    html_path = course_dir / "index.html"
    html_path.write_text(html_content, encoding="utf-8")

    zip_name = f"{package.course_id}_offline.zip"
    zip_path = course_dir / zip_name

    files_to_pack = [
        "index.html",
        "layer.json",
        "registry_report.json",
        "routing_report.json",
        "step_illustration_source.json",
        "tasks.json",
        "ocr_corrections.json",
        "media_passports.json",
        "bookmark_report.json",
        "summary_notes.md",
    ]

    media_dir = course_dir / "media"
    spec_dir = course_dir / "scene_specs"
    non_video_bytes = 0

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname in files_to_pack:
            fpath = course_dir / fname
            if fpath.exists():
                zf.write(fpath, arcname=fname)
                non_video_bytes += fpath.stat().st_size
        for svg_f in sorted(illust_dir.glob("*.svg")):
            zf.write(svg_f, arcname=f"illustrations/{svg_f.name}")
            non_video_bytes += svg_f.stat().st_size
        if spec_dir.exists():
            for sp_f in sorted(spec_dir.glob("*.json")):
                zf.write(sp_f, arcname=f"scene_specs/{sp_f.name}")
                non_video_bytes += sp_f.stat().st_size
        if media_dir.exists():
            for mf in sorted(media_dir.iterdir()):
                if mf.is_file() and mf.suffix.lower() in (".mp4", ".srt", ".vtt", ".mp3", ".m4a"):
                    zf.write(mf, arcname=f"media/{mf.name}")
                    if mf.suffix.lower() in (".srt", ".vtt"):
                        non_video_bytes += mf.stat().st_size

    size_mb = round(zip_path.stat().st_size / (1024 * 1024), 4)
    size_no_video_mb = round(non_video_bytes / (1024 * 1024), 4)
    assert size_no_video_mb < 30.0, f"Превышен лимит 30 МБ (без видео) на главу: {size_no_video_mb} МБ"

    prefix = public_prefix.rstrip("/") if public_prefix else f"/outputs/{package.course_id}"
    package.offline_html_url = f"{prefix}/index.html"
    package.offline_zip_url = f"{prefix}/{zip_name}"
    package.offline_package_size_mb = size_mb
    package.offline_size_without_video_mb = size_no_video_mb

    (course_dir / "t3_course_package.json").write_text(package.model_dump_json(indent=2), encoding="utf-8")
    return package
