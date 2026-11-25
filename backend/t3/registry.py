"""
Этап 1 Т3: Независимый реестр источника (PDF + назначенные страницы) и двусторонняя сверка учебного слоя.

Ключевой инвариант:
Реестр строится напрямую по PDF-файлу книги (хеш SHA-256, число страниц, извлечение текста PDF)
и размеченным страницам диапазона НЕЗАВИСИМО от проверяемого учебного слоя (StudyLayer) и его внутренней карты покрытия.
Удаление рисунка (например, Кузнецов, стр. 201, Рис. 10.1), формулы или абзаца одновременно из всех списков слоя
гарантированно обнаруживается при сверке с независимым реестром.
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.t3.models import (
    PdfPageRange,
    RegistryDiscrepancy,
    RegistryVerificationReport,
    SourceRegistry,
    SourceUnit,
    StudyLayer,
)

# Официальный каталог 6 книг проекта LITHOS с привязкой к PDF, типу (train/ctrl) и штатным диапазонам Т3
BOOK_CATALOG: dict[str, dict[str, Any]] = {
    "train_latyshova.md": {
        "book_id": "train_latyshova",
        "pdf_file": "Латышова - Практическое руководство по интерпретации диаграмм геофизических исследований скважин - 1991.pdf",
        "title": "Практическое руководство по интерпретации диаграмм геофизических исследований скважин",
        "authors": ["Латышова М. Г."],
        "year": 1991,
        "is_training": True,
        "chapter_id": "latyshova_ch5",
        "chapter_title": "Глава V (§17–§20): Построение разрезов скважин, выделение коллекторов и оценка их продуктивности (PDF 90–108)",
        "default_ranges": [
            {"start": 90, "end": 108, "section": "Глава V, §17–§20. Условия вскрытия, литологический разрез, выделение и оценка насыщения коллекторов"},
        ],
        "page_mode": "two_up_latyshova",
    },
    "train_basniev.md": {
        "book_id": "train_basniev",
        "pdf_file": "Басниев и др - Нефтегазовая гидромеханика - 2005.pdf",
        "title": "Нефтегазовая гидромеханика",
        "authors": ["Басниев К. С.", "Дмитриев Н. М.", "Розенберг Г. Д."],
        "year": 2005,
        "is_training": True,
        "chapter_id": "basniev_ch23_24",
        "chapter_title": "Глава XXIII и Глава XXIV (§1): Неустановившееся движение упругой жидкости, уравнение пьезопроводности и метод ПССС (PDF 474–500)",
        "default_ranges": [
            {"start": 474, "end": 500, "section": "Глава XXIII (§1–§5) и Глава XXIV (§1). Упругий режим, точные решения Ei и метод ПССС Чарного"},
        ],
        "page_mode": "direct_1_to_1",
    },
    "train_kuznetsov.md": {
        "book_id": "train_kuznetsov",
        "pdf_file": "Кузнецов Литология природных резервуаров нефти и газа 2012.pdf",
        "title": "Литология природных резервуаров нефти и газа",
        "authors": ["Кузнецов В. Г."],
        "year": 2012,
        "is_training": True,
        "chapter_id": "kuznetsov_ch10",
        "chapter_title": "Глава 10. Природные резервуары рифов (§10.1–§10.4, PDF 200–222)",
        "default_ranges": [
            {"start": 200, "end": 222, "section": "Глава 10. Природные резервуары рифов (§10.1–§10.4, стр. 200–222)"},
        ],
        "page_mode": "direct_1_to_1",
    },
    "ctrl_vendelshtein.md": {
        "book_id": "ctrl_vendelshtein",
        "pdf_file": "Вендельштейн и др - Геофизические методы определения параметров нефтегазовых коллекторов - 1978.pdf",
        "title": "Геофизические методы определения параметров нефтегазовых коллекторов",
        "authors": ["Вендельштейн Б. Ю.", "Резванов Р. А."],
        "year": 1978,
        "is_training": False,
        "chapter_id": "vendelshtein_ch1_discontinuous",
        "chapter_title": "Глава I (§I.1 «Косвенные количественные признаки» и §I.2–§I.3): Выделение коллекторов и оценка насыщения (PDF 9–14, 20–30)",
        "default_ranges": [
            {"start": 9, "end": 14, "section": "Глава I, §I.1. Косвенные количественные признаки выделения терригенных коллекторов"},
            {"start": 20, "end": 30, "section": "Глава I, §I.2–§I.3. Оценка характера насыщения, эффективная мощность и отбивка ВНК/ГЖК"},
        ],
        "page_mode": "two_up_vendelshtein",
    },
    "ctrl_barenblatt.md": {
        "book_id": "ctrl_barenblatt",
        "pdf_file": "Баренблатт и др - Движение жидкостей и газов в природных пластах - 1984.pdf",
        "title": "Движение жидкостей и газов в природных пластах",
        "authors": ["Баренблатт Г. И.", "Ентов В. М.", "Рыжик В. М."],
        "year": 1984,
        "is_training": False,
        "chapter_id": "barenblatt_s4",
        "chapter_title": "Глава 1, §4. Нестационарное движение однородной сжимаемой жидкости. Линейная теория (PDF 38–51)",
        "default_ranges": [
            {"start": 38, "end": 51, "section": "Глава 1, §4. Нестационарное движение однородной сжимаемой жидкости. Линейная теория"},
        ],
        "page_mode": "direct_1_to_1",
    },
    "ctrl_baraboshkin_b.md": {
        "book_id": "ctrl_baraboshkin_b",
        "pdf_file": "Барабошкин - Практическая седиментология (терригенные коллектора) - 2007.pdf",
        "title": "Практическая седиментология (терригенные коллектора)",
        "authors": ["Барабошкин Е. Ю."],
        "year": 2007,
        "is_training": False,
        "chapter_id": "baraboshkin_s1_2",
        "chapter_title": "Глава 1, §1.2. Дельты [Deltas]: флювиальные, волновые и приливные системы (PDF 30–44, печ. 29–43)",
        "default_ranges": [
            {"start": 30, "end": 44, "section": "Глава 1, §1.2. Дельты [Deltas]: морфология, флювиальные, волновые и приливные дельты"},
        ],
        "page_mode": "offset_minus_1",
    },
}

_NUM_UNIT_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9_])"
    r"(\d+(?:[.,]\d+)?(?:\s*[–—-]\s*\d+(?:[.,]\d+)?)?)\s*"
    r"(%|м³/сут|м3/сут|м³/с|м²/с|м2/с|мД|мкм²|Ом·м|Ом\*м|МПа|кПа|Па·с|мПа·с|г/л|г/см³|кгс/см²|мВ|м/с|мм/с|сут|ч|км|м|см|мм)\b"
)

_CONDITION_KEYWORDS = (
    "если ",
    "при условии",
    "только при",
    "неприменим",
    "однозначно нельзя",
    "допустим",
    "в случае",
    "не является признаком",
    "при наличии",
    "не оцифрован",
)


def compute_printed_page(pdf_page: int, page_mode: str) -> str:
    """Вычисляет печатный номер страницы (или разворот) по номеру PDF-страницы и режиму скана."""
    if page_mode == "direct_1_to_1":
        return str(pdf_page)
    if page_mode == "offset_minus_1":
        return str(max(1, pdf_page - 1))
    if page_mode == "two_up_latyshova":
        if pdf_page <= 2:
            return str(pdf_page)
        left = 2 * pdf_page - 4
        right = left + 1
        return f"{left}–{right}"
    if page_mode == "two_up_vendelshtein":
        if pdf_page <= 2:
            return str(pdf_page)
        left = 2 * pdf_page - 3
        right = left + 1
        return f"{left}–{right}"
    return str(pdf_page)


@lru_cache(maxsize=16)
def get_pdf_metadata(pdf_path_str: str) -> tuple[str, int]:
    """Возвращает (sha256, total_pages) для PDF-источника."""
    pdf_path = Path(pdf_path_str)
    if not pdf_path.exists():
        return ("missing_pdf_source", 0)
    raw = pdf_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        total_pages = len(reader.pages)
    except Exception:
        total_pages = 0
    return sha, total_pages


def parse_range_spec(range_spec: str | list[tuple[int, int]] | list[dict[str, Any]] | None, book_file: str) -> list[PdfPageRange]:
    """
    Парсит спецификацию диапазонов PDF (включая разрывные диапазоны вида '9-14,20-30' или [(9, 14), (20, 30)]).
    """
    cat = BOOK_CATALOG.get(book_file, {})
    page_mode = cat.get("page_mode", "direct_1_to_1")

    if range_spec is None:
        raw_ranges = cat.get("default_ranges", [{"start": 1, "end": 15, "section": "Основной раздел"}])
    elif isinstance(range_spec, str):
        raw_ranges = []
        for part in range_spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a_str, b_str = part.split("-", 1)
                raw_ranges.append({"start": int(a_str.strip()), "end": int(b_str.strip()), "section": f"PDF {part}"})
            else:
                p = int(part)
                raw_ranges.append({"start": p, "end": p, "section": f"PDF {p}"})
    elif isinstance(range_spec, list):
        raw_ranges = []
        for item in range_spec:
            if isinstance(item, tuple):
                raw_ranges.append({"start": int(item[0]), "end": int(item[1]), "section": f"PDF {item[0]}–{item[1]}"})
            elif isinstance(item, dict):
                raw_ranges.append(
                    {
                        "start": int(item.get("start") or item.get("start_pdf_page", 1)),
                        "end": int(item.get("end") or item.get("end_pdf_page", 1)),
                        "section": str(item.get("section") or item.get("section_label") or ""),
                    }
                )
            elif isinstance(item, PdfPageRange):
                raw_ranges.append(
                    {
                        "start": item.start_pdf_page,
                        "end": item.end_pdf_page,
                        "section": item.section_label,
                    }
                )
    else:
        raw_ranges = [{"start": 1, "end": 15, "section": "Основной раздел"}]

    result: list[PdfPageRange] = []
    for r in raw_ranges:
        s = int(r["start"])
        e = int(r["end"])
        if e < s:
            s, e = e, s
        result.append(
            PdfPageRange(
                start_pdf_page=s,
                end_pdf_page=e,
                start_printed_page=compute_printed_page(s, page_mode),
                end_printed_page=compute_printed_page(e, page_mode),
                section_label=r.get("section") or f"PDF стр. {s}–{e}",
            )
        )
    return result


def is_pdf_page_in_ranges(pdf_page: int, pdf_ranges: list[PdfPageRange]) -> bool:
    return any(r.start_pdf_page <= pdf_page <= r.end_pdf_page for r in pdf_ranges)


def extract_numbers_and_units(text: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in _NUM_UNIT_RE.finditer(text):
        val = m.group(1).strip().replace(",", ".")
        unit = m.group(2).strip()
        key = (val, unit)
        if key not in seen:
            seen.add(key)
            found.append({"value": val, "unit": unit})
    return found


def extract_conditions(text: str) -> list[str]:
    conds: list[str] = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        low = sent.lower()
        if any(kw in low for kw in _CONDITION_KEYWORDS):
            cleaned = re.sub(r"\s+", " ", sent).strip()
            if 15 <= len(cleaned) <= 360:
                conds.append(cleaned)
    return conds


def split_markdown_by_pdf_page(md_text: str) -> dict[int, list[str]]:
    """
    Разбивает исходный файл книги по маркерам <!-- page N -->.
    В файлах data/books/*.md маркер <!-- page N --> стоит в конце страницы N
    (или перед началом страницы N+1 в зависимости от книги).
    Проверяем оба случая: в Кузнецове и Вендельштейне после <!-- page N --> идёт содержимое страницы N!
    """
    pages: dict[int, list[str]] = {}
    cur_page = 1
    for line in md_text.splitlines():
        m = re.match(r"^<!--\s*page\s+(\d+)\s*-->$", line.strip())
        if m:
            cur_page = int(m.group(1))
            pages.setdefault(cur_page, [])
            continue
        pages.setdefault(cur_page, []).append(line)
    return pages


def build_independent_registry(
    data_dir: Path,
    book_file: str,
    pdf_ranges: str | list[tuple[int, int]] | list[dict[str, Any]] | list[PdfPageRange] | None = None,
) -> SourceRegistry:
    """
    Строит независимый реестр единиц источника по PDF и назначенным страницам.
    Не использует StudyLayer или его карту покрытия.
    """
    cat = BOOK_CATALOG.get(
        book_file,
        {
            "book_id": Path(book_file).stem,
            "pdf_file": "",
            "title": Path(book_file).stem,
            "authors": [],
            "year": None,
            "is_training": not book_file.startswith("ctrl_"),
            "chapter_id": f"{Path(book_file).stem}_ch1",
            "chapter_title": Path(book_file).stem,
            "page_mode": "direct_1_to_1",
        },
    )
    book_id = cat["book_id"]
    page_mode = cat.get("page_mode", "direct_1_to_1")
    parsed_ranges = parse_range_spec(pdf_ranges, book_file)

    pdf_rel_name = cat.get("pdf_file", "")
    pdf_path = data_dir / "книги" / pdf_rel_name if pdf_rel_name else Path("")
    if pdf_rel_name and pdf_path.exists():
        sha256, total_pdf_pages = get_pdf_metadata(str(pdf_path))
    else:
        md_fallback = data_dir / "books" / book_file
        sha256 = hashlib.sha256(md_fallback.read_bytes()).hexdigest() if md_fallback.exists() else "unknown"
        total_pdf_pages = max((r.end_pdf_page for r in parsed_ranges), default=1)

    md_path = data_dir / "books" / book_file
    if not md_path.exists():
        raise FileNotFoundError(f"Файл книги не найден: {md_path}")

    md_text = md_path.read_text(encoding="utf-8", errors="replace")
    pages_map = split_markdown_by_pdf_page(md_text)

    units: list[SourceUnit] = []
    cur_section = cat.get("chapter_title", book_id)

    target_pages: list[int] = []
    for rng in parsed_ranges:
        for p in range(rng.start_pdf_page, rng.end_pdf_page + 1):
            if p not in target_pages:
                target_pages.append(p)

    for pdf_page in target_pages:
        printed_page = compute_printed_page(pdf_page, page_mode)
        raw_lines = pages_map.get(pdf_page, [])
        if not raw_lines:
            units.append(
                SourceUnit(
                    unit_id=f"{book_id}_p{pdf_page:03d}_missing_scan",
                    unit_type="missing_scan",
                    pdf_page=pdf_page,
                    printed_page=printed_page,
                    location=f"{cur_section} · стр. {pdf_page}",
                    verbatim_text=f"[Отсутствует текстовый слой или скан страницы {pdf_page}]",
                    ocr_status="missing_scan",
                    ocr_note="Страница отсутствует в текстовом слое; требуется ручная сверка со сканом PDF.",
                    expected_inclusion="excluded_with_reason",
                    default_exclusion_reason="Пустая или отсутствующая страница в OCR-слое",
                )
            )
            continue

        # Разбираем блоки внутри страницы: VLM-блоки (---- ... ----), заголовки, формулы, таблицы, подписи рисунков и абзацы
        idx = 0
        unit_seq = 0
        while idx < len(raw_lines):
            line = raw_lines[idx].strip()
            if not line:
                idx += 1
                continue

            # Пропускаем одиночный печатный номер страницы (колонтитул)
            if line.isdigit() and len(line) <= 4:
                idx += 1
                continue

            # Заголовок раздела
            if line.startswith("#"):
                cur_section = line.lstrip("#").strip()[:120]
                idx += 1
                continue

            # Блок описания иллюстрации / схемы / графика (---- ... ----)
            if line == "----":
                vlm_lines: list[str] = []
                idx += 1
                while idx < len(raw_lines) and raw_lines[idx].strip() != "----":
                    vlm_lines.append(raw_lines[idx].strip())
                    idx += 1
                if idx < len(raw_lines) and raw_lines[idx].strip() == "----":
                    idx += 1
                vlm_text = "\n".join(ln for ln in vlm_lines if ln)
                if vlm_text:
                    unit_seq += 1
                    has_no_legend = "не определяется без легенды" in vlm_text.lower()
                    # Проверяем наличие FORMAT 13: LEGEND внутри VLM-блока
                    if "FORMAT 13: LEGEND" in vlm_text:
                        parts = vlm_text.split("━━━ FORMAT 13: LEGEND")
                        fig_part = parts[0].strip()
                        leg_part = "━━━ FORMAT 13: LEGEND" + parts[1].strip()
                    else:
                        fig_part = vlm_text
                        leg_part = ""

                    units.append(
                        SourceUnit(
                            unit_id=f"{book_id}_p{pdf_page:03d}_vlmfig_{unit_seq:02d}",
                            unit_type="figure",
                            pdf_page=pdf_page,
                            printed_page=printed_page,
                            location=f"{cur_section} · иллюстрация #{unit_seq}",
                            verbatim_text=fig_part[:600],
                            figure_ref=f"Иллюстрация стр. {pdf_page} (#{unit_seq})",
                            numbers_and_units=extract_numbers_and_units(fig_part),
                            conditions=extract_conditions(fig_part),
                            ocr_status="legend_missing" if has_no_legend else "clean",
                            ocr_note="Часть условных знаков на скане требует сверки с легендой" if has_no_legend else "",
                            expected_inclusion="must_cover",
                        )
                    )
                    if leg_part:
                        unit_seq += 1
                        units.append(
                            SourceUnit(
                                unit_id=f"{book_id}_p{pdf_page:03d}_legend_{unit_seq:02d}",
                                unit_type="legend",
                                pdf_page=pdf_page,
                                printed_page=printed_page,
                                location=f"{cur_section} · легенда #{unit_seq}",
                                verbatim_text=leg_part[:600],
                                figure_ref=f"Легенда стр. {pdf_page}",
                                ocr_status="legend_missing" if "не определяется без легенды" in leg_part.lower() else "clean",
                                ocr_note="Условные знаки без текстовой подписи на самом графике" if "не определяется без легенды" in leg_part.lower() else "",
                                expected_inclusion="must_cover",
                            )
                        )
                continue

            # Таблица Markdown
            if line.startswith("|"):
                tbl_lines: list[str] = []
                while idx < len(raw_lines) and raw_lines[idx].strip().startswith("|"):
                    tbl_lines.append(raw_lines[idx].strip())
                    idx += 1
                tbl_text = "\n".join(tbl_lines)
                unit_seq += 1
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_tbl_{unit_seq:02d}",
                        unit_type="table",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · таблица #{unit_seq}",
                        verbatim_text=tbl_text[:600],
                        figure_ref=f"Таблица (стр. {pdf_page})",
                        numbers_and_units=extract_numbers_and_units(tbl_text),
                        ocr_status="illegible" if "[нрзб]" in tbl_text.lower() else "clean",
                        expected_inclusion="must_cover",
                    )
                )
                continue

            # Отдельная блочная формула $$ ... $$ или \[ ... \]
            if line.startswith("$$") or line.startswith(r"\["):
                form_lines = [line]
                idx += 1
                while idx < len(raw_lines):
                    nxt = raw_lines[idx].strip()
                    form_lines.append(nxt)
                    idx += 1
                    if nxt.endswith("$$") or nxt.endswith(r"\]"):
                        break
                form_text = " ".join(form_lines).strip()
                unit_seq += 1
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_eq_{unit_seq:02d}",
                        unit_type="formula",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · формула #{unit_seq}",
                        verbatim_text=form_text[:500],
                        numbers_and_units=extract_numbers_and_units(form_text),
                        ocr_status="illegible" if "[нрзб]" in form_text.lower() else "clean",
                        expected_inclusion="must_cover",
                    )
                )
                continue

            # Собираем обычный текстовый абзац
            para_lines = [line]
            idx += 1
            while idx < len(raw_lines):
                nxt = raw_lines[idx].strip()
                if not nxt or nxt == "----" or nxt.startswith("#") or nxt.startswith("|") or nxt.startswith("$$"):
                    break
                para_lines.append(nxt)
                idx += 1
            para_text = re.sub(r"\s+", " ", " ".join(para_lines)).strip()
            if len(para_text) < 4:
                continue

            unit_seq += 1
            has_nrzb = "[нрзб]" in para_text.lower()

            # Классифицируем абзац: подпись рисунка (Рис. N...), легенда (Фации: 1 – ...), пример, задача, формула или текст
            fig_match = re.match(r"^(?:\*+)?(Рис(?:унок|\.)\s*\d+(?:\.\d+)?[а-г]?)\.?\s*(.*)$", para_text, re.I)
            legend_match = re.match(r"^(Фации|Условные обозначения|Пласты|Коллекторы|Кривые)\s*:\s*\d+\s*[–—-]", para_text, re.I)
            ex_match = re.match(r"^(?:\*+)?(Пример\s*\d+(?:\.\d+)?)\b", para_text, re.I)
            prob_match = re.match(r"^(?:\*+)?(Задач[аи]\s*\d*(?:\.\d+)?)\b", para_text, re.I)

            if fig_match:
                fig_num = fig_match.group(1).strip()
                fig_slug = re.sub(r"[^0-9a-zA-Z]+", "_", fig_num.lower()).strip("_")
                # Создаём явную единицу рисунка + подписи со стабильным ID (например, train_kuznetsov_p201_fig_10_1)
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_fig_{fig_slug}_{unit_seq:02d}",
                        unit_type="figure",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · {fig_num}",
                        verbatim_text=para_text,
                        figure_ref=fig_num,
                        numbers_and_units=extract_numbers_and_units(para_text),
                        conditions=extract_conditions(para_text),
                        ocr_status="illegible" if has_nrzb else "clean",
                        expected_inclusion="must_cover",
                    )
                )
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_cap_{fig_slug}_{unit_seq:02d}",
                        unit_type="caption",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · подпись {fig_num}",
                        verbatim_text=para_text,
                        figure_ref=fig_num,
                        numbers_and_units=extract_numbers_and_units(para_text),
                        ocr_status="illegible" if has_nrzb else "clean",
                        expected_inclusion="must_cover",
                    )
                )
            elif legend_match:
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_leg_{unit_seq:02d}",
                        unit_type="legend",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · экспликация/легенда рисунка",
                        verbatim_text=para_text,
                        numbers_and_units=extract_numbers_and_units(para_text),
                        ocr_status="illegible" if has_nrzb else "clean",
                        expected_inclusion="must_cover",
                    )
                )
            elif ex_match:
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_ex_{unit_seq:02d}",
                        unit_type="worked_example",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · {ex_match.group(1)}",
                        verbatim_text=para_text,
                        figure_ref=ex_match.group(1),
                        numbers_and_units=extract_numbers_and_units(para_text),
                        conditions=extract_conditions(para_text),
                        ocr_status="illegible" if has_nrzb else "clean",
                        expected_inclusion="must_cover",
                    )
                )
            elif prob_match:
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_prob_{unit_seq:02d}",
                        unit_type="problem",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · {prob_match.group(1)}",
                        verbatim_text=para_text,
                        figure_ref=prob_match.group(1),
                        numbers_and_units=extract_numbers_and_units(para_text),
                        conditions=extract_conditions(para_text),
                        ocr_status="illegible" if has_nrzb else "clean",
                        expected_inclusion="must_cover",
                    )
                )
            elif has_nrzb:
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_nrzb_{unit_seq:02d}",
                        unit_type="ocr_illegible",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · неразборчивый участок OCR #{unit_seq}",
                        verbatim_text=para_text,
                        numbers_and_units=extract_numbers_and_units(para_text),
                        conditions=extract_conditions(para_text),
                        ocr_status="illegible",
                        ocr_note="Содержит маркер [нрзб]; требует ручной сверки по PDF-оригиналу.",
                        expected_inclusion="must_cover",
                    )
                )
            else:
                # Проверяем, является ли короткая строка артефактом подписи оси на скане (например "а", "б", "Уровень моря")
                is_substantive_heading = bool(
                    re.match(r"^(?:таблица|данные\s+к|пример|задача|упражнение|рис\.?|глава|§)\b", para_text.strip(), re.I)
                )
                is_axis_artifact = (not is_substantive_heading) and len(para_text) < 22 and not any(ch in para_text for ch in ".,:;=")
                units.append(
                    SourceUnit(
                        unit_id=f"{book_id}_p{pdf_page:03d}_par_{unit_seq:02d}",
                        unit_type="paragraph",
                        pdf_page=pdf_page,
                        printed_page=printed_page,
                        location=f"{cur_section} · абзац #{unit_seq}",
                        verbatim_text=para_text,
                        numbers_and_units=extract_numbers_and_units(para_text),
                        conditions=extract_conditions(para_text),
                        ocr_status="clean",
                        expected_inclusion="excluded_with_reason" if is_axis_artifact else "must_cover",
                        default_exclusion_reason="Короткая текстовая метка внутри поля рисунка (включена в состав фигуры)" if is_axis_artifact else None,
                    )
                )

    summary_counts: dict[str, int] = {}
    for u in units:
        summary_counts[u.unit_type] = summary_counts.get(u.unit_type, 0) + 1

    differ = page_mode != "direct_1_to_1"
    note = (
        "Печатная нумерация совпадает с PDF 1:1."
        if not differ
        else "PDF является двухстраничным разворотом (2-up скан): одна страница PDF содержит две печатные страницы."
        if page_mode.startswith("two_up")
        else "Печатная нумерация смещена относительно PDF на 1 страницу (титульный лист)."
    )

    return SourceRegistry(
        registry_id=f"reg_{cat['chapter_id']}",
        book_id=book_id,
        book_file=book_file,
        pdf_file=pdf_rel_name,
        source_sha256=sha256,
        total_pdf_pages=total_pdf_pages,
        chapter_id=cat["chapter_id"],
        chapter_title=cat["chapter_title"],
        is_training=bool(cat.get("is_training", True)),
        pdf_ranges=parsed_ranges,
        page_numbering_differ=differ,
        page_numbering_note=note,
        units=units,
        summary_counts=summary_counts,
    )


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def verify_registry_against_layer(
    registry: SourceRegistry,
    layer: StudyLayer,
) -> RegistryVerificationReport:
    """
    Двусторонняя сверка независимого реестра источника (SourceRegistry) и учебного слоя (StudyLayer).

    Выявляет:
    1) empty_coverage — пустой охват слоя
    2) missing_unit — пропуск единицы реестра (в том числе при одновременном удалении рисунка
       из узлов, утверждений и карты покрытия слоя, например Рис. 10.1 Кузнецова со стр. 201)
    3) duplicate_unit — дубликаты единиц/утверждений в слое
    4) extra_unit — лишние единицы, отсутствующие в независимом реестре
    5) out_of_range_gap — единицы со страниц вне назначенного диапазона или из разрыва диапазона
    6) wrong_page — подмена PDF или печатной страницы
    7) quote_modified — искажение точной цитаты источника
    8) wrong_number — подмена числового значения
    9) wrong_unit — неверная единица измерения
    10) condition_lost — потеря граничного условия или переворот модальности («нельзя» -> «можно»)
    """
    discrepancies: list[RegistryDiscrepancy] = []
    reg_by_id: dict[str, SourceUnit] = {u.unit_id: u for u in registry.units}

    # 0. Проверка на пустой охват
    if not layer.nodes or (not layer.coverage_map and all(not n.covered_unit_ids for n in layer.nodes)):
        discrepancies.append(
            RegistryDiscrepancy(
                discrepancy_id="DISC-EMPTY-001",
                discrepancy_type="empty_coverage",
                severity="CRITICAL",
                unit_id="ALL",
                pdf_page=registry.pdf_ranges[0].start_pdf_page if registry.pdf_ranges else 1,
                message="Пустой охват учебного слоя: ни одна единица независимого реестра не связана с узлами.",
            )
        )
        return RegistryVerificationReport(
            passed=False,
            registry_id=registry.registry_id,
            layer_id=layer.layer_id,
            book_file=registry.book_file,
            pdf_ranges=registry.pdf_ranges,
            total_registry_units=len(registry.units),
            covered_units_count=0,
            excluded_units_count=0,
            manual_verification_required_count=0,
            discrepancies=discrepancies,
            summary_by_type={"empty_coverage": 1},
        )

    # Собираем фактические привязки из узлов и утверждений слоя
    node_covered_counts: dict[str, list[str]] = {}
    for node in layer.nodes:
        seen_in_node: set[str] = set()
        for uid in node.covered_unit_ids:
            if uid in seen_in_node:
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-DUP-NODE-{node.node_id}-{uid}",
                        discrepancy_type="duplicate_unit",
                        severity="HIGH",
                        unit_id=uid,
                        node_id=node.node_id,
                        pdf_page=reg_by_id[uid].pdf_page if uid in reg_by_id else 0,
                        message=f"Дубликат единицы {uid} внутри списка covered_unit_ids узла {node.node_id}.",
                    )
                )
            seen_in_node.add(uid)
            node_covered_counts.setdefault(uid, []).append(node.node_id)

    # Проверка дубликатов claim_id
    seen_claims: set[str] = set()
    for cl in layer.claims:
        if cl.claim_id in seen_claims:
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-DUP-CLAIM-{cl.claim_id}",
                    discrepancy_type="duplicate_unit",
                    severity="HIGH",
                    unit_id=cl.unit_id,
                    node_id=cl.node_id,
                    pdf_page=cl.pdf_page,
                    message=f"Дубликат идентификатора утверждения {cl.claim_id} в слое.",
                )
            )
        seen_claims.add(cl.claim_id)

    # 1. Сверка Реестр -> Слой (поиск пропущенных единиц и необоснованных исключений)
    covered_count = 0
    excluded_count = 0
    manual_items: list[dict[str, Any]] = []

    for unit in registry.units:
        if unit.ocr_status in ("illegible", "missing_scan", "legend_missing"):
            manual_items.append(
                {
                    "unit_id": unit.unit_id,
                    "unit_type": unit.unit_type,
                    "pdf_page": unit.pdf_page,
                    "printed_page": unit.printed_page,
                    "ocr_status": unit.ocr_status,
                    "note": unit.ocr_note or "Требует ручной сверки со сканом PDF",
                    "excerpt": unit.verbatim_text[:160],
                }
            )

        linked_nodes = node_covered_counts.get(unit.unit_id, [])
        excl_reason = layer.excluded_units.get(unit.unit_id, "").strip()
        cov_entry = layer.coverage_map.get(unit.unit_id, "").strip()

        if linked_nodes:
            covered_count += 1
        elif excl_reason or cov_entry.startswith("EXCLUDED:"):
            reason = excl_reason or cov_entry.split("EXCLUDED:", 1)[1].strip()
            # Обязательные содержательные единицы (рисунки, подписи, формулы, таблицы, примеры, задачи)
            # нельзя молча исключать без реальной технической причины (например, missing_scan)
            if unit.unit_type in ("figure", "caption", "formula", "table", "worked_example", "problem") and unit.ocr_status != "missing_scan":
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-UNJUSTIFIED-EXCL-{unit.unit_id}",
                        discrepancy_type="missing_unit",
                        severity="CRITICAL",
                        unit_id=unit.unit_id,
                        pdf_page=unit.pdf_page,
                        printed_page=unit.printed_page,
                        message=f"Обязательная содержательная единица ({unit.unit_type} {unit.figure_ref or unit.unit_id}, стр. {unit.pdf_page}) исключена из узлов слоя.",
                        expected_from_registry=unit.verbatim_text[:180],
                        found_in_layer=f"EXCLUDED: {reason}",
                    )
                )
            elif len(reason) < 5:
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-EMPTY-EXCL-{unit.unit_id}",
                        discrepancy_type="missing_unit",
                        severity="HIGH",
                        unit_id=unit.unit_id,
                        pdf_page=unit.pdf_page,
                        printed_page=unit.printed_page,
                        message=f"Единица {unit.unit_id} (стр. {unit.pdf_page}) исключена без конкретного основания.",
                    )
                )
            else:
                excluded_count += 1
        else:
            # Единица полностью отсутствует в узлах, утверждениях и исключениях слоя!
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-MISSING-{unit.unit_id}",
                    discrepancy_type="missing_unit",
                    severity="CRITICAL",
                    unit_id=unit.unit_id,
                    pdf_page=unit.pdf_page,
                    printed_page=unit.printed_page,
                    message=(
                        f"Пропуск единицы источника в слое: {unit.unit_type} "
                        f"({unit.figure_ref or unit.location}, PDF стр. {unit.pdf_page}) отсутствует во всех списках слоя."
                    ),
                    expected_from_registry=unit.verbatim_text[:200],
                    found_in_layer="MISSING",
                )
            )

    # 2. Сверка Слой -> Реестр (лишние единицы, разрыв диапазона, подмена страницы, цитаты, числа, единицы, условия)
    all_layer_unit_refs: list[tuple[str, str | None, int]] = []
    for node in layer.nodes:
        for uid in node.covered_unit_ids:
            u_page = reg_by_id[uid].pdf_page if uid in reg_by_id else -1
            all_layer_unit_refs.append((uid, node.node_id, u_page))

    for uid, nid, _ in all_layer_unit_refs:
        if uid not in reg_by_id:
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-EXTRA-{uid}",
                    discrepancy_type="extra_unit",
                    severity="HIGH",
                    unit_id=uid,
                    node_id=nid,
                    pdf_page=0,
                    message=f"Лишняя единица {uid} в узле {nid}: отсутствует в независимом реестре источника.",
                )
            )

    # Проверяем цитаты в узлах (quotes_and_pages) и утверждениях (claims)
    for node in layer.nodes:
        for qp in node.quotes_and_pages:
            if not is_pdf_page_in_ranges(qp.pdf_page, registry.pdf_ranges):
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-GAP-QP-{node.node_id}-{qp.unit_id}",
                        discrepancy_type="out_of_range_gap",
                        severity="CRITICAL",
                        unit_id=qp.unit_id,
                        node_id=node.node_id,
                        pdf_page=qp.pdf_page,
                        printed_page=qp.printed_page,
                        message=f"Страница цитаты PDF {qp.pdf_page} выходит за пределы назначенного (разрывного) диапазона главы.",
                    )
                )
            if qp.unit_id not in reg_by_id:
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-EXTRA-QP-{qp.unit_id}",
                        discrepancy_type="extra_unit",
                        severity="HIGH",
                        unit_id=qp.unit_id,
                        node_id=node.node_id,
                        pdf_page=qp.pdf_page,
                        message=f"Цитата ссылается на несуществующую в реестре единицу {qp.unit_id}.",
                    )
                )
                continue

            reg_u = reg_by_id[qp.unit_id]
            if qp.pdf_page != reg_u.pdf_page:
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-PAGE-QP-{qp.unit_id}",
                        discrepancy_type="wrong_page",
                        severity="HIGH",
                        unit_id=qp.unit_id,
                        node_id=node.node_id,
                        pdf_page=qp.pdf_page,
                        printed_page=qp.printed_page,
                        message=f"Неверная страница у единицы {qp.unit_id}: в слое указана стр. {qp.pdf_page}, в реестре источника — стр. {reg_u.pdf_page}.",
                        expected_from_registry=str(reg_u.pdf_page),
                        found_in_layer=str(qp.pdf_page),
                    )
                )

            norm_reg = _norm_ws(reg_u.verbatim_text)
            norm_qp = _norm_ws(qp.verbatim_quote)
            if norm_qp and norm_qp not in norm_reg and norm_reg not in norm_qp:
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-QUOTE-QP-{qp.unit_id}",
                        discrepancy_type="quote_modified",
                        severity="HIGH",
                        unit_id=qp.unit_id,
                        node_id=node.node_id,
                        pdf_page=reg_u.pdf_page,
                        printed_page=reg_u.printed_page,
                        message=f"Изменён цитатный текст единицы {qp.unit_id} на стр. {reg_u.pdf_page}.",
                        expected_from_registry=norm_reg[:180],
                        found_in_layer=norm_qp[:180],
                    )
                )

    for cl in layer.claims:
        if not is_pdf_page_in_ranges(cl.pdf_page, registry.pdf_ranges):
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-GAP-CL-{cl.claim_id}",
                    discrepancy_type="out_of_range_gap",
                    severity="CRITICAL",
                    unit_id=cl.unit_id,
                    node_id=cl.node_id,
                    pdf_page=cl.pdf_page,
                    printed_page=cl.printed_page,
                    message=f"Утверждение {cl.claim_id} ссылается на страницу PDF {cl.pdf_page} вне назначенного диапазона главы.",
                )
            )

        if cl.unit_id not in reg_by_id:
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-EXTRA-CL-{cl.claim_id}",
                    discrepancy_type="extra_unit",
                    severity="HIGH",
                    unit_id=cl.unit_id,
                    node_id=cl.node_id,
                    pdf_page=cl.pdf_page,
                    message=f"Утверждение {cl.claim_id} ссылается на отсутствующую в реестре единицу {cl.unit_id}.",
                )
            )
            continue

        reg_u = reg_by_id[cl.unit_id]

        # 2.1 Проверка страницы
        if cl.pdf_page != reg_u.pdf_page:
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-PAGE-CL-{cl.claim_id}",
                    discrepancy_type="wrong_page",
                    severity="HIGH",
                    unit_id=cl.unit_id,
                    node_id=cl.node_id,
                    pdf_page=cl.pdf_page,
                    printed_page=cl.printed_page,
                    message=f"Подмена страницы в утверждении {cl.claim_id}: указана стр. {cl.pdf_page} вместо стр. {reg_u.pdf_page}.",
                    expected_from_registry=str(reg_u.pdf_page),
                    found_in_layer=str(cl.pdf_page),
                )
            )

        # 2.2 Проверка подлинности цитаты
        norm_reg = _norm_ws(reg_u.verbatim_text)
        norm_cl_q = _norm_ws(cl.verbatim_quote)
        if norm_cl_q and norm_cl_q not in norm_reg and norm_reg not in norm_cl_q:
            discrepancies.append(
                RegistryDiscrepancy(
                    discrepancy_id=f"DISC-QUOTE-CL-{cl.claim_id}",
                    discrepancy_type="quote_modified",
                    severity="HIGH",
                    unit_id=cl.unit_id,
                    node_id=cl.node_id,
                    pdf_page=reg_u.pdf_page,
                    printed_page=reg_u.printed_page,
                    message=f"Искажена дословная цитата в утверждении {cl.claim_id} (стр. {reg_u.pdf_page}).",
                    expected_from_registry=norm_reg[:180],
                    found_in_layer=norm_cl_q[:180],
                )
            )

        # 2.3 Проверка чисел и единиц измерения
        if reg_u.numbers_and_units:
            reg_pairs = [(item["value"], item["unit"]) for item in reg_u.numbers_and_units]
            reg_vals = {v for v, _ in reg_pairs}
            reg_units_for_val: dict[str, set[str]] = {}
            for v, u in reg_pairs:
                reg_units_for_val.setdefault(v, set()).add(u)

            claim_pairs = cl.numbers_and_units or extract_numbers_and_units(cl.claim_text)
            for cp in claim_pairs:
                c_val = str(cp.get("value", "")).replace(",", ".")
                c_unit = str(cp.get("unit", "")).strip()
                if c_val in reg_vals:
                    allowed_units = reg_units_for_val.get(c_val, set())
                    if c_unit and allowed_units and c_unit not in allowed_units:
                        discrepancies.append(
                            RegistryDiscrepancy(
                                discrepancy_id=f"DISC-UNIT-CL-{cl.claim_id}-{c_val}",
                                discrepancy_type="wrong_unit",
                                severity="HIGH",
                                unit_id=cl.unit_id,
                                node_id=cl.node_id,
                                pdf_page=reg_u.pdf_page,
                                printed_page=reg_u.printed_page,
                                message=f"Неверная единица измерения для значения {c_val} в {cl.claim_id}: '{c_unit}' вместо {sorted(allowed_units)}.",
                                expected_from_registry=f"{c_val} {sorted(allowed_units)[0]}",
                                found_in_layer=f"{c_val} {c_unit}",
                            )
                        )
                else:
                    # Число в утверждении не совпадает ни с одним числом из исходной единицы (и не является расчётным)
                    calc_vals = {str(cv.value) for cv in cl.computed_values}
                    if c_val and c_val not in calc_vals:
                        discrepancies.append(
                            RegistryDiscrepancy(
                                discrepancy_id=f"DISC-NUM-CL-{cl.claim_id}-{c_val}",
                                discrepancy_type="wrong_number",
                                severity="HIGH",
                                unit_id=cl.unit_id,
                                node_id=cl.node_id,
                                pdf_page=reg_u.pdf_page,
                                printed_page=reg_u.printed_page,
                                message=f"Подмена числа в утверждении {cl.claim_id} (стр. {reg_u.pdf_page}): '{c_val} {c_unit}' отсутствует в источнике {reg_pairs}.",
                                expected_from_registry=str(reg_pairs),
                                found_in_layer=f"{c_val} {c_unit}",
                            )
                        )

        # 2.4 Проверка сохранения граничных условий и модальности («однозначно нельзя» vs «однозначно можно»)
        if reg_u.conditions:
            if not cl.conditions:
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-COND-LOST-{cl.claim_id}",
                        discrepancy_type="condition_lost",
                        severity="CRITICAL",
                        unit_id=cl.unit_id,
                        node_id=cl.node_id,
                        pdf_page=reg_u.pdf_page,
                        printed_page=reg_u.printed_page,
                        message=f"Потеряно условие применимости из источника (стр. {reg_u.pdf_page}) в утверждении {cl.claim_id}.",
                        expected_from_registry=reg_u.conditions[0],
                        found_in_layer="conditions=[]",
                    )
                )
            if "однозначно нельзя" in norm_reg.lower() and "однозначно можно" in cl.claim_text.lower():
                discrepancies.append(
                    RegistryDiscrepancy(
                        discrepancy_id=f"DISC-COND-FLIP-{cl.claim_id}",
                        discrepancy_type="condition_lost",
                        severity="CRITICAL",
                        unit_id=cl.unit_id,
                        node_id=cl.node_id,
                        pdf_page=reg_u.pdf_page,
                        printed_page=reg_u.printed_page,
                        message=f"Переворот модальности условия в утверждении {cl.claim_id} (стр. {reg_u.pdf_page}): 'однозначно нельзя' заменено на 'однозначно можно'.",
                        expected_from_registry="однозначно нельзя",
                        found_in_layer="однозначно можно",
                    )
                )

    summary_by_type: dict[str, int] = {}
    for d in discrepancies:
        summary_by_type[d.discrepancy_type] = summary_by_type.get(d.discrepancy_type, 0) + 1

    return RegistryVerificationReport(
        passed=len(discrepancies) == 0,
        registry_id=registry.registry_id,
        layer_id=layer.layer_id,
        book_file=registry.book_file,
        pdf_ranges=registry.pdf_ranges,
        total_registry_units=len(registry.units),
        covered_units_count=covered_count,
        excluded_units_count=excluded_count,
        manual_verification_required_count=len(manual_items),
        discrepancies=discrepancies,
        manual_verification_items=manual_items,
        summary_by_type=summary_by_type,
    )
