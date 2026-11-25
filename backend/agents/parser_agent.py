"""
Parser Agent: читает .md главы учебника + JSON-паспорт (в .md или .json),
извлекает формулы, термины и палетки и формирует Scene Graph (CourseManifest).

Поддерживает:
1) Работу через OpenAI-совместимую LLM (LLM_API_KEY из .env)
2) Детерминированный / оффлайн-режим с опорой на реальный текст глав и паспортов
   (включая эталонные модули Латышова 1991 и Басниев 2005, а также любые ctrl_* книги).
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from backend.schemas import (
    BookInfo,
    ChapterInfo,
    CourseManifest,
    FormulaSpec,
    QAReport,
    SceneSpec,
    TermBridge,
)
from backend.physics_engine import simulate_dupuit_flow, simulate_psss_transient, simulate_well_log

load_dotenv()

_CHAPTER_HEADING_RE = re.compile(
    r"^(#{1,3})\s+((?:Глава|ГЛАВА|Часть|ЧАСТЬ|§|\d+(?:\.\d+)?)\b.*|[А-ЯЁA-Z0-9][^\n]{3,90})$"
)
_LATEX_BLOCK_RE = re.compile(r"\$\$([^$]{1,500})\$\$|\\\[((?:[^\\]|\\(?!\])){1,500})\\\]")


def load_passport(passport_path: Path) -> dict[str, Any]:
    """Читает JSON-паспорт либо напрямую из .json, либо из ```json``` блока в .md."""
    raw = passport_path.read_text(encoding="utf-8", errors="replace")
    if passport_path.suffix.lower() == ".json":
        return json.loads(raw)
    fence = raw.find("```json")
    if fence != -1:
        start = raw.find("{", fence)
        end = raw.rfind("}")
        if start != -1 and end > start:
            # Находим закрывающий ``` после start
            close = raw.find("```", start)
            candidate_end = raw.rfind("}", start, close) if close != -1 else end
            if candidate_end > start:
                return json.loads(raw[start : candidate_end + 1])
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        return json.loads(raw[start : end + 1])
    return {}


def parse_markdown_chapters(book_path: Path) -> tuple[list[ChapterInfo], list[str]]:
    """Разбивает .md книгу на логические главы/разделы без загрузки лишнего мусора."""
    lines = book_path.read_text(encoding="utf-8", errors="replace").splitlines()
    headings: list[tuple[int, str]] = []

    in_format_block = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "----":
            in_format_block = not in_format_block
            continue
        if in_format_block:
            continue
        if stripped.startswith("# "):
            title = stripped.lstrip("#").strip()
            # Пропускаем общие титульные строки, оглавление и списки литературы в начале
            if len(title) < 3 or title.lower() in {"оглавление", "содержание"}:
                continue
            is_chapter = bool(
                re.match(r"^(Глава|ГЛАВА|§|\d+[\.\s]|ПРЕДИСЛОВИЕ|ВВЕДЕНИЕ|ПРИЛОЖЕНИЕ)", title, re.IGNORECASE)
                or (idx > 20 and len(title) > 8)
            )
            if is_chapter:
                headings.append((idx, title))

    # Объединяем подряд идущие заголовки (например "# Глава I" + "# ИНТЕРПРЕТАЦИЯ...")
    merged: list[tuple[int, str]] = []
    for line_no, title in headings:
        if merged and line_no - merged[-1][0] <= 3 and re.match(r"^Глава\s+[IVXLC\d]+$", merged[-1][1], re.I):
            merged[-1] = (merged[-1][0], f"{merged[-1][1]} — {title}")
        else:
            merged.append((line_no, title))

    if not merged:
        merged = [(0, book_path.stem)]

    chapters: list[ChapterInfo] = []
    for i, (start, title) in enumerate(merged):
        end = merged[i + 1][0] if i + 1 < len(merged) else len(lines)
        chunk = "\n".join(lines[start:end])
        if len(chunk.strip()) < 250 and i < len(merged) - 1:
            continue
        formula_count = chunk.count("$$") // 2 + chunk.count(r"\[")
        has_nomograms = ("FORMAT 7" in chunk) or ("ПАЛЕТКА" in chunk.upper())
        chapters.append(
            ChapterInfo(
                index=len(chapters),
                title=title[:140],
                start_line=start + 1,
                end_line=end,
                char_count=len(chunk),
                has_nomograms=has_nomograms,
                formula_count=formula_count,
            )
        )

    if not chapters:
        full_text = "\n".join(lines)
        chapters.append(
            ChapterInfo(
                index=0,
                title=book_path.stem,
                start_line=1,
                end_line=max(1, len(lines)),
                char_count=len(full_text),
                has_nomograms=("FORMAT 7" in full_text) or ("ПАЛЕТКА" in full_text.upper()),
                formula_count=len(_LATEX_BLOCK_RE.findall(full_text)),
            )
        )

    return chapters, lines


def _match_passport_for_book(book_file: str, passports: dict[str, dict[str, Any]]) -> str | None:
    """Находит соответствующий паспорт для книги train_* / ctrl_*."""
    stem = Path(book_file).stem.lower()
    # Прямые ключевые слова сопоставления
    keyword_map = {
        "latyshova": "латышова",
        "basniev": "басниев",
        "vendelshtein": "вендельштейн",
        "barenblatt": "баренблатт",
        "baraboshkin": "барабошкин",
        "kuznetsov": "litologiya",
    }
    for p_name, p_data in passports.items():
        src = str(p_data.get("meta", {}).get("source_file", "")).lower()
        if src and (stem in src or Path(src).stem in stem):
            return p_name
    for key, needle in keyword_map.items():
        if key in stem:
            for p_name in passports:
                if needle in p_name.lower():
                    return p_name
    return None


def _detect_module_type(book_file: str, passport: dict[str, Any]) -> str:
    low = (book_file + " " + str(passport.get("meta", {}).get("title", ""))).lower()
    if "latyshova" in low or "латышов" in low:
        return "latyshova_gis"
    if "basniev" in low or "басниев" in low:
        return "basniev_hydro"
    return "generic_chapter"


def discover_books(data_dir: Path) -> list[BookInfo]:
    """Сканирует data/books/ и data/passports/ и возвращает список доступных учебников."""
    books_dir = data_dir / "books"
    passports_dir = data_dir / "passports"
    passports: dict[str, dict[str, Any]] = {}

    if passports_dir.exists():
        for p in sorted(passports_dir.iterdir()):
            if p.suffix.lower() in {".md", ".json"}:
                try:
                    passports[p.name] = load_passport(p)
                except Exception:
                    pass

    result: list[BookInfo] = []
    if not books_dir.exists():
        return result

    for b in sorted(books_dir.glob("*.md")):
        p_name = _match_passport_for_book(b.name, passports)
        passport = passports.get(p_name, {}) if p_name else {}
        meta = passport.get("meta", {})
        chapters, _ = parse_markdown_chapters(b)
        result.append(
            BookInfo(
                book_file=b.name,
                passport_file=p_name,
                title=meta.get("title") or b.stem,
                authors=meta.get("authors") or [],
                year=meta.get("year"),
                domain=meta.get("primary_domain") or "",
                school=passport.get("meta", {}).get("school_and_standards", {}).get("methodological_school", "soviet_cis"),
                is_control=b.name.startswith("ctrl_"),
                recommended_module=_detect_module_type(b.name, passport),  # type: ignore[arg-type]
                chapters=chapters,
            )
        )
    return result


def _extract_term_bridges_from_passport(passport: dict[str, Any], max_items: int = 8) -> list[TermBridge]:
    """Извлекает пары терминологического моста из key_definitions паспорта."""
    bridges: list[TermBridge] = []
    for kd in passport.get("key_definitions", [])[:max_items]:
        ru_term = kd.get("term", "")
        en_term = kd.get("term_en_equivalent") or ru_term
        bridges.append(
            TermBridge(
                ru_symbol=ru_term.split()[0] if ru_term else "—",
                ru_term=ru_term,
                en_symbol=en_term.split("/")[0].strip()[:24],
                en_term=en_term,
                unit="",
                note=kd.get("school_note") or kd.get("note") or "",
            )
        )
    return bridges


def _latyshova_gold_scenes(physics_data: dict[str, Any]) -> list[SceneSpec]:
    """Эталонный курс по Латышовой (1991): ГИС, Арчи, ПС/КС, палетки БЭЗ, 3D Probe Lab."""
    summary = physics_data.get("summary", {})
    params = physics_data.get("parameters", {})
    return [
        SceneSpec(
            scene_id="lat_s1_intro",
            order=1,
            title="Электропроводность пород и удельное сопротивление вод",
            narration=(
                "В терригенном разрезе породообразующие минералы — кварц и полевой шпат — являются изоляторами. "
                "Электрический ток течёт почти исключительно по поровой воде. Поэтому удельное сопротивление "
                "полностью водоносного пласта ро-вп пропорционально сопротивлению пластовой воды ро-в."
            ),
            duration_sec=14.0,
            visual_backend="manim",
            manim_scene_class="LatyshovaIntroScene",
            formulas=[
                FormulaSpec(
                    latex=r"\rho_{\text{вп}} = P_{\text{п}} \cdot \rho_{\text{в}}",
                    western_latex=r"R_0 = F \cdot R_w",
                    title="Сопротивление водонасыщенного пласта (формула 2)",
                    variables={
                        "ρ_вп": "УЭС водонасыщенной породы, Ом·м",
                        "P_п": "Параметр пористости (formation factor F)",
                        "ρ_в": "УЭС пластовой воды при пластовой температуре, Ом·м",
                    },
                    source_ref="Латышова (1991), Глава I, §1, ф. (2)",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="ρ_вп",
                    ru_term="УЭС водоносной породы",
                    en_symbol="R_0",
                    en_term="Water-saturated rock resistivity",
                    unit="Ом·м",
                ),
                TermBridge(
                    ru_symbol="P_п",
                    ru_term="Параметр пористости",
                    en_symbol="F",
                    en_term="Formation resistivity factor",
                    unit="б/р",
                ),
            ],
            key_takeaways=[
                "Скелет породы практически не проводит ток",
                "При росте минерализации и температуры ρ_в снижается",
            ],
        ),
        SceneSpec(
            scene_id="lat_s2_archie",
            order=2,
            title="Уравнение Арчи–Дахнова и параметр насыщения P_н",
            narration=(
                "Параметр пористости P-п связан со степенной зависимостью коэффициента пористости К-п. "
                "Если в порах появляется нефть или газ, сопротивление возрастает в P-н раз. "
                "Параметр насыщения P-н позволяет перейти от показаний каротажа к коэффициенту водонасыщения К-в "
                "и нефтегазонасыщению К-нг."
            ),
            duration_sec=15.0,
            visual_backend="manim",
            manim_scene_class="LatyshovaArchieScene",
            formulas=[
                FormulaSpec(
                    latex=r"P_{\text{п}} = \frac{a_m}{K_{\text{п}}^{m}}, \quad P_{\text{н}} = \frac{\rho_{\text{п}}}{\rho_{\text{вп}}} = \frac{a_n}{K_{\text{в}}^{n}}",
                    western_latex=r"F = \frac{a}{\phi^m}, \quad I = \frac{R_t}{R_0} = \frac{b}{S_w^n}",
                    title="Уравнения пористости и насыщения (формулы 3, 10)",
                    variables={
                        "K_п": "Коэффициент пористости, д.е.",
                        "m": "Структурный показатель (1.3–2.2)",
                        "P_н": "Параметр насыщения",
                        "K_в": "Коэффициент водонасыщения, д.е.",
                    },
                    source_ref="Латышова (1991), Глава I, §1; Глава V, §23",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="K_п",
                    ru_term="Коэффициент пористости",
                    en_symbol="φ",
                    en_term="Total / effective porosity",
                    unit="% / д.е.",
                ),
                TermBridge(
                    ru_symbol="P_н",
                    ru_term="Параметр насыщения",
                    en_symbol="I",
                    en_term="Resistivity index (Rt/R0)",
                    unit="б/р",
                ),
                TermBridge(
                    ru_symbol="ρ_п",
                    ru_term="Удельное сопротивление пласта",
                    en_symbol="R_t",
                    en_term="True formation resistivity",
                    unit="Ом·м",
                ),
            ],
            key_takeaways=[
                f"Расчётный максимум ρ_БК в разрезе: {summary.get('max_rho_bk_ohmm', 42.0)} Ом·м",
                f"Максимальный параметр насыщения P_н: {summary.get('max_p_n', 20.6)}",
            ],
        ),
        SceneSpec(
            scene_id="lat_s3_welllog",
            order=3,
            title="Кривые КС и СП: выделение коллектора и уровня ВНК",
            narration=(
                "Против проницаемых песчаников наблюдается отрицательная аномалия потенциалов собственной поляризации СП, "
                "глинистая корка и радиальный градиент сопротивления между микрозондами МБК и боковым каротажем БК. "
                "По критическому значению альфа-СП отбиваются границы коллектора, а резкий спад сопротивления "
                f"на глубине {params.get('vnk_depth_m', 2425)} метров фиксирует водонефтяной контакт."
            ),
            duration_sec=16.0,
            visual_backend="manim",
            manim_scene_class="LatyshovaWellLogScene",
            formulas=[
                FormulaSpec(
                    latex=r"\Delta E_{\text{ст}} = -k_{\text{СП}} \lg\frac{\rho_{\text{ф}}}{\rho_{\text{в}}}, \quad \alpha_{\text{СП}} = \frac{\Delta E}{\Delta E_{\max}}",
                    western_latex=r"SSP = -K \log_{10}\frac{R_{mf}}{R_w}, \quad \alpha_{SP} = \frac{SP}{SSP}",
                    title="Статическая и относительная амплитуда СП",
                    variables={
                        "α_СП": "Относительная амплитуда СП (отсечка 0.45)",
                        "ρ_ф": "УЭС фильтрата бурового раствора, Ом·м",
                    },
                    source_ref="Латышова (1991), Глава II, §8; Глава V, §20",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="α_СП",
                    ru_term="Относительная амплитуда СП",
                    en_symbol="SP/SSP",
                    en_term="SP clean-sand ratio",
                    unit="д.е.",
                ),
                TermBridge(
                    ru_symbol="ВНК",
                    ru_term="Водонефтяной контакт",
                    en_symbol="OWC",
                    en_term="Oil-Water Contact",
                    unit="м",
                ),
            ],
            key_takeaways=[
                f"Эффективная нефтенасыщенная толщина h_эф: {summary.get('net_pay_oil_m', 9.5)} м",
                "В нефтеносном коллекторе при пресном растворе ρ_МБК < ρ_БК (понижающее проникновение)",
            ],
        ),
        SceneSpec(
            scene_id="lat_s4_bez_methodology",
            order=4,
            title="Методика интерпретации палеток БЭЗ (без подмены чисел)",
            narration=(
                "Важное методическое правило: кривые бокового электрического зондирования БЭЗ строятся на "
                "логарифмическом бланке как зависимость кажущегося сопротивления ро-к от разноса зонда АО. "
                "Фактическая кривая совмещается с семейством теоретических палеток для определения "
                "истинного сопротивления ро-п и диаметра зоны проникновения D. Поскольку палетки БЭЗ "
                "в учебнике не оцифрованы, конкретные отсчёты снимаются только по аттестованному альбому палеток."
            ),
            duration_sec=15.0,
            visual_backend="remotion_formula",
            methodology_only_nomogram=True,
            formulas=[
                FormulaSpec(
                    latex=r"\rho_{\text{к}} = f(AO) \;\xrightarrow{\text{совмещение с палеткой БКЗ}}\; (\rho_{\text{п}}, \, \rho_{\text{зп}}, \, D)",
                    western_latex=r"R_a(AO) \;\xrightarrow{\text{type-curve match}}\; (R_t, \, R_{xo}, \, d_i)",
                    title="Алгоритм палеточной интерпретации БЭЗ",
                    variables={
                        "AO": "Разнос градиент-зонда, м",
                        "ρ_к": "Кажущееся сопротивление, Ом·м",
                        "D": "Диаметр зоны проникновения, м",
                    },
                    source_ref="Латышова (1991), Глава I, §5 (только методика)",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="БЭЗ",
                    ru_term="Боковое электрическое зондирование",
                    en_symbol="BKZ / LLS",
                    en_term="Lateral Logging Sounding",
                    unit="Ом·м",
                ),
            ],
            key_takeaways=[
                "Палетки БЭЗ не оцифрованы — запрещено придумывать численные отсчёты с графиков",
                "Методика: построение ρ_к(AO) -> совмещение осей -> считывание D/d_c и ρ_п/ρ_c",
            ],
        ),
        SceneSpec(
            scene_id="lat_s5_probelab",
            order=5,
            title="Интерактивная 3D-лаборатория: Probe Lab по ГИС",
            narration=(
                "Перейдите в 3D-лабораторию Probe Lab, чтобы перемещать каротажный зонд вдоль ствола скважины, "
                "менять минерализацию пластовой воды ро-в, фильтрат раствора ро-ф и структурный показатель m, "
                "а также переключаться между терригенным и трещинным карбонатным типом коллектора."
            ),
            duration_sec=11.0,
            visual_backend="threejs_lab",
            lab_preset={
                "lab": "LatyshovaProbeLab",
                "rho_v": params.get("rho_v_ohmm", 0.05),
                "rho_f": params.get("rho_f_ohmm", 1.2),
                "m": params.get("m", 1.95),
                "n": params.get("n", 2.0),
                "vnk_depth_m": params.get("vnk_depth_m", 2425.0),
            },
            key_takeaways=[
                "Живой пересчёт P_п, P_н, K_в, K_нг на любой глубине",
                "Поддержка модели трещинной пористости по формуле (6) §1",
            ],
        ),
    ]


def _basniev_gold_scenes(physics_data: dict[str, Any]) -> list[SceneSpec]:
    """Эталонный курс по Басниеву и др. (2005): Дарси, Дюпюи, воронка депрессии, пьезопроводность и ПССС."""
    dup = physics_data.get("dupuit", {})
    metrics = dup.get("metrics", {})
    tr = physics_data.get("transient_psss", {})
    tr_params = tr.get("parameters", {})
    return [
        SceneSpec(
            scene_id="bas_s1_darcy",
            order=1,
            title="Закон Дарси: скорость фильтрации и истинная скорость",
            narration=(
                "В подземной гидромеханике движение флюида описывается законом Дарси. "
                "Фиктивная скорость фильтрации w равна отношению расхода к полной площади сечения породы "
                "и пропорциональна градиенту давления. Истинная средняя скорость в поровых каналах выше "
                "и определяется делением на просветность или активную пористость."
            ),
            duration_sec=14.0,
            visual_backend="manim",
            manim_scene_class="BasnievDarcyScene",
            formulas=[
                FormulaSpec(
                    latex=r"\vec{w} = -\frac{k}{\mu} \operatorname{grad} p, \quad v = \frac{w}{m}",
                    western_latex=r"\vec{u} = -\frac{k}{\mu} \nabla p, \quad v_{\text{int}} = \frac{u}{\phi}",
                    title="Векторная форма закона Дарси (Глава XVIII, §4)",
                    variables={
                        "w": "Скорость фильтрации (Darcy velocity), м/с",
                        "k": "Проницаемость, м² (1 мД = 10⁻¹⁵ м²)",
                        "μ": "Динамическая вязкость, Па·с",
                    },
                    source_ref="Басниев и др. (2005), Глава XVIII, §4",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="w",
                    ru_term="Скорость фильтрации",
                    en_symbol="u / v_D",
                    en_term="Darcy / superficial velocity",
                    unit="м/с",
                ),
                TermBridge(
                    ru_symbol="k",
                    ru_term="Абсолютная проницаемость",
                    en_symbol="k",
                    en_term="Absolute permeability",
                    unit="мД / м²",
                ),
            ],
            key_takeaways=[
                "1 мД = 10⁻¹⁵ м², 1 мПа·с = 10⁻³ Па·с",
                "Границы закона Дарси проверяются критическим числом Рейнольдса",
            ],
        ),
        SceneSpec(
            scene_id="bas_s2_dupuit",
            order=2,
            title="Плоскорадиальная фильтрация и формула Дюпюи",
            narration=(
                "Рассмотрим круговой пласт толщиной h и радиусом контура питания R-к с центральной скважиной радиуса r-с. "
                "Интегрирование уравнения Лапласа в цилиндрических координатах приводит к знаменитой формуле Дюпюи. "
                f"При проницаемости {dup.get('inputs', {}).get('k_md', 120)} миллидарси и депрессии "
                f"{dup.get('inputs', {}).get('delta_p_mpa', 7.5)} мегапаскаль расчётный дебит составляет "
                f"{metrics.get('q_m3_day', 0)} кубических метров в сутки."
            ),
            duration_sec=16.0,
            visual_backend="manim",
            manim_scene_class="BasnievDupuitScene",
            formulas=[
                FormulaSpec(
                    latex=r"Q = \frac{2\pi k h (p_{\text{к}} - p_{\text{с}})}{\mu \ln(R_{\text{к}} / r_{\text{с}})}",
                    western_latex=r"q = \frac{2\pi k h (p_e - p_w)}{\mu \ln(r_e / r_w)}",
                    title="Формула Дюпюи (20.19)",
                    variables={
                        "Q": "Объёмный дебит скважины, м³/с (м³/сут)",
                        "p_к, p_с": "Давление на контуре и на забое, Па (МПа)",
                        "R_к, r_с": "Радиус контура питания и скважины, м",
                    },
                    source_ref="Басниев и др. (2005), Глава XX, §3, ф. (20.19)",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="R_к, p_к",
                    ru_term="Контур питания и контурное давление",
                    en_symbol="r_e, p_e",
                    en_term="Drainage radius & boundary pressure",
                    unit="м, МПа",
                ),
                TermBridge(
                    ru_symbol="r_с, p_с",
                    ru_term="Радиус и забойное давление скважины",
                    en_symbol="r_w, p_wf",
                    en_term="Wellbore radius & flowing BHP",
                    unit="м, МПа",
                ),
            ],
            key_takeaways=[
                f"Дебит Q = {metrics.get('q_m3_day', 0)} м³/сут",
                f"Коэффициент продуктивности C = {metrics.get('productivity_index_m3_day_mpa', 0)} м³/(сут·МПа)",
            ],
        ),
        SceneSpec(
            scene_id="bas_s3_cone",
            order=3,
            title="Логарифмическая воронка депрессии и закон w(r) ~ 1/r",
            narration=(
                "Давление в пласте распределено по логарифмическому закону. Основная потеря напора и резкое падение "
                "давления происходят в непосредственной близости от забоя. Поскольку через каждое цилиндрическое "
                "сечение протекает один и тот же расход, скорость фильтрации резко возрастает обратно пропорционально радиусу."
            ),
            duration_sec=14.0,
            visual_backend="manim",
            manim_scene_class="BasnievConeScene",
            formulas=[
                FormulaSpec(
                    latex=r"p(r) = p_{\text{с}} + \frac{p_{\text{к}} - p_{\text{с}}}{\ln(R_{\text{к}}/r_{\text{с}})} \ln\frac{r}{r_{\text{с}}}, \quad w(r) = \frac{Q}{2\pi h r}",
                    western_latex=r"p(r) = p_{wf} + \frac{p_e - p_{wf}}{\ln(r_e/r_w)} \ln\frac{r}{r_w}",
                    title="Воронка депрессии (20.20) и скорость (20.21)",
                    variables={"r": "Текущий радиус, м", "w(r)": "Радиальная скорость фильтрации"},
                    source_ref="Басниев и др. (2005), Глава XX, §3",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="Δp",
                    ru_term="Депрессия на пласт",
                    en_symbol="Δp = p_e - p_wf",
                    en_term="Pressure drawdown",
                    unit="МПа",
                )
            ],
            key_takeaways=[
                "Большая часть депрессии расходуется в призабойной зоне",
                "Состояние околоскважинной зоны (скин) критически влияет на дебит",
            ],
        ),
        SceneSpec(
            scene_id="bas_s4_psss",
            order=4,
            title="Упругий режим, пьезопроводность κ и метод ПССС",
            narration=(
                "При пуске скважины давление перераспределяется не мгновенно, а за счёт упругого запаса жидкости и породы. "
                "Скорость распространения волны давления определяет коэффициент пьезопроводности каппа. "
                "В приближённом методе последовательной смены стационарных состояний Исаака Чарного "
                "граница возмущённой области расширяется как корень из четырёх каппа тэ."
            ),
            duration_sec=16.0,
            visual_backend="manim",
            manim_scene_class="BasnievPSSSScene",
            formulas=[
                FormulaSpec(
                    latex=r"\kappa = \frac{k}{\mu \beta^*}, \quad \beta^* = m\beta_{\text{ж}} + \beta_{\text{с}}, \quad R(t) = \sqrt{r_{\text{с}}^2 + 4\kappa t}",
                    western_latex=r"\eta = \frac{k}{\mu c_t \phi}, \quad r_{inv}(t) \approx 2\sqrt{\eta t}",
                    title="Пьезопроводность и радиус возмущения по ПССС (Глава XXIV, §1)",
                    variables={
                        "κ": "Коэффициент пьезопроводности, м²/с",
                        "β*": "Коэффициент упругоёмкости пласта, Па⁻¹",
                        "R(t)": "Подвижный радиус возмущённой области, м",
                    },
                    source_ref="Басниев и др. (2005), Главы XXIII–XXIV",
                )
            ],
            term_bridges=[
                TermBridge(
                    ru_symbol="κ",
                    ru_term="Коэффициент пьезопроводности",
                    en_symbol="η / D_h",
                    en_term="Hydraulic diffusivity",
                    unit="м²/с",
                ),
                TermBridge(
                    ru_symbol="ПССС",
                    ru_term="Последовательная смена стационарных состояний",
                    en_symbol="Successive Steady States",
                    en_term="Moving-boundary approximation",
                    unit="метод",
                ),
            ],
            key_takeaways=[
                f"Коэффициент пьезопроводности κ = {tr_params.get('kappa_m2_s', 0.21)} м²/с",
                "Сравнение ПССС с точным решением через интегральную показательную функцию Ei(-r²/4κt)",
            ],
        ),
        SceneSpec(
            scene_id="bas_s5_hydrolab",
            order=5,
            title="Интерактивная 3D-лаборатория: Hydro Lab",
            narration=(
                "Откройте 3D Hydro Lab, чтобы в реальном времени менять проницаемость k, вязкость мю и депрессию дельта-п, "
                "наблюдать перестройку 3D-воронки депрессии, ускорение частиц флюида у ствола "
                "и сравнение профиля ПССС с точным уравнением пьезопроводности."
            ),
            duration_sec=11.0,
            visual_backend="threejs_lab",
            lab_preset={
                "lab": "BasnievHydroLab",
                "k_md": dup.get("inputs", {}).get("k_md", 120.0),
                "mu_cp": dup.get("inputs", {}).get("mu_cp", 1.8),
                "h_m": dup.get("inputs", {}).get("h_m", 14.0),
                "delta_p_mpa": dup.get("inputs", {}).get("delta_p_mpa", 7.5),
            },
            key_takeaways=[
                "Прямая связь параметров Дюпюи с геометрией воронки депрессии",
                "Наглядная динамика упругого режима во времени",
            ],
        ),
    ]


def _extract_formulas_from_text(chapter_text: str, max_formulas: int = 4) -> list[FormulaSpec]:
    """Извлекает реальные LaTeX-формулы из выбранной главы контрольного/произвольного учебника."""
    specs: list[FormulaSpec] = []
    for match in _LATEX_BLOCK_RE.finditer(chapter_text):
        tex = (match.group(1) or match.group(2) or "").strip()
        tex = re.sub(r"\\tag\{[^}]+\}", "", tex).strip()
        if len(tex) < 4 or len(tex) > 180 or "нрзб" in tex.lower():
            continue
        specs.append(
            FormulaSpec(
                latex=tex,
                title=f"Уравнение из текста главы #{len(specs) + 1}",
                source_ref="Извлечено детерминированным парсером из .md",
            )
        )
        if len(specs) >= max_formulas:
            break
    return specs


def _generic_chapter_scenes(
    chapter_title: str,
    chapter_text: str,
    passport: dict[str, Any],
) -> list[SceneSpec]:
    """Универсальный детерминированный генератор сцен для ctrl_* и любых загруженных книг."""
    meta = passport.get("meta", {})
    bridges = _extract_term_bridges_from_passport(passport, max_items=6)
    formulas = _extract_formulas_from_text(chapter_text, max_formulas=4)
    has_nomogram = ("FORMAT 7" in chapter_text) or ("ПАЛЕТКА" in chapter_text.upper())

    # Чистые абзацы текста (без служебных VLM-блоков)
    clean_lines = []
    in_vlm = False
    for ln in chapter_text.splitlines():
        s = ln.strip()
        if s == "----":
            in_vlm = not in_vlm
            continue
        if in_vlm or s.startswith("<!--") or s.startswith("#") or s.startswith("|"):
            continue
        if len(s) > 40 and "[нрзб]" not in s:
            clean_lines.append(re.sub(r"\$\$?.*?\$\$?", "", s).strip())
        if len(clean_lines) >= 8:
            break

    intro_text = " ".join(clean_lines[:2])[:320] if clean_lines else passport.get("executive_summary", "")[:320]
    core_text = " ".join(clean_lines[2:5])[:340] if len(clean_lines) > 2 else intro_text

    scenes = [
        SceneSpec(
            scene_id="gen_s1_overview",
            order=1,
            title=f"Обзор: {chapter_title[:65]}",
            narration=(
                f"Изучаем главу «{chapter_title}» из книги «{meta.get('title', 'Учебник')}». "
                f"{intro_text}"
            ),
            duration_sec=14.0,
            visual_backend="manim",
            manim_scene_class="GenericChapterScene",
            term_bridges=bridges[:2],
            key_takeaways=[
                f"Школа: {meta.get('school_and_standards', {}).get('methodological_school', 'soviet_cis')}",
                f"Система единиц: {meta.get('units_system', 'mixed')}",
            ],
        ),
        SceneSpec(
            scene_id="gen_s2_equations",
            order=2,
            title="Математическая модель и нотация главы",
            narration=(
                f"Ключевые соотношения главы представлены в авторской нотации учебника. {core_text} "
                "Для точного сопоставления с международными стандартами рядом приведён терминологический мост."
            ),
            duration_sec=15.0,
            visual_backend="manim" if formulas else "remotion_formula",
            manim_scene_class="GenericChapterScene" if formulas else "",
            formulas=formulas[:2],
            term_bridges=bridges[2:4] if len(bridges) > 2 else bridges[:2],
            methodology_only_nomogram=has_nomogram,
            key_takeaways=[
                "Все формулы извлечены напрямую из текста главы без LLM-галлюцинаций",
                "Методика палеток даётся без выдумывания численных отсчётов" if has_nomogram else "Параметры привязаны к области применимости",
            ],
        ),
        SceneSpec(
            scene_id="gen_s3_synthesis",
            order=3,
            title="Область применимости и выводы для практики",
            narration=(
                "Подведём итог: при переносе моделей и эмпирических коэффициентов на реальные активы "
                "необходимо учитывать тип коллектора, локальную калибровку по керну и ограничения исходной школы."
            ),
            duration_sec=12.0,
            visual_backend="remotion_split",
            formulas=formulas[2:3],
            term_bridges=bridges[:3],
            methodology_only_nomogram=has_nomogram,
            key_takeaways=passport.get("practical_value", {}).get("what_reader_can_do_after", [])[:3]
            or ["Проверка границ применимости модели"],
        ),
    ]
    return scenes


async def _try_llm_enrich_scenes(
    chapter_title: str,
    chapter_text: str,
    passport: dict[str, Any],
    base_scenes: list[SceneSpec],
) -> list[SceneSpec]:
    """Если в .env задан реальный LLM_API_KEY, уточняет нарратив сцен по тексту главы и паспорту."""
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
        return base_scenes

    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip()
    model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        routing = passport.get("agent_routing_card", {})
        prompt = (
            "Ты научный редактор нефтегазового видеокурса. "
            "Улучши русскоязычный дикторский текст (narration) для сцен, строго соблюдая:\n"
            f"1) quantitative_safety_warning: {routing.get('quantitative_safety_warning', '')}\n"
            f"2) school_warning: {routing.get('school_warning', '')}\n"
            f"3) reservoir_type_warning: {routing.get('reservoir_type_warning', '')}\n"
            "Запрещено выдумывать числа с неоцифрованных палеток.\n"
            f"Глава: {chapter_title}\n"
            f"Фрагмент текста:\n{chapter_text[:4000]}\n\n"
            "Текущие сцены (JSON):\n"
            + json.dumps([{"scene_id": s.scene_id, "title": s.title, "narration": s.narration} for s in base_scenes], ensure_ascii=False)
            + '\nВерни строго JSON вида {"scenes": [{"scene_id": "...", "narration": "..."}]}'
        )
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        parsed = json.loads(content)
        updates = {item["scene_id"]: item["narration"] for item in parsed.get("scenes", []) if "scene_id" in item and "narration" in item}
        for s in base_scenes:
            if s.scene_id in updates and len(updates[s.scene_id].strip()) > 30:
                s.narration = updates[s.scene_id].strip()
    except Exception:
        # Надёжный fallback на детерминированный сценарий при сбое сети/API
        pass

    return base_scenes


def build_course_manifest_sync(
    data_dir: Path,
    book_file: str,
    passport_file: str | None = None,
    chapter_index: int = 0,
    module_override: str = "auto",
    voice: str = "ru-RU-DmitryNeural",
) -> tuple[CourseManifest, str, str, dict[str, Any]]:
    """Синхронная детерминированная сборка CourseManifest и контекста главы."""
    book_path = data_dir / "books" / book_file
    if not book_path.exists():
        raise FileNotFoundError(f"Book file not found: {book_path}")

    passports_dir = data_dir / "passports"
    passport: dict[str, Any] = {}
    resolved_passport = passport_file

    if not resolved_passport and passports_dir.exists():
        all_passports = {
            p.name: load_passport(p)
            for p in sorted(passports_dir.iterdir())
            if p.suffix.lower() in {".md", ".json"}
        }
        resolved_passport = _match_passport_for_book(book_file, all_passports)
        if resolved_passport:
            passport = all_passports[resolved_passport]
    elif resolved_passport:
        p_path = passports_dir / resolved_passport
        if p_path.exists():
            passport = load_passport(p_path)

    chapters, lines = parse_markdown_chapters(book_path)
    chosen = chapters[min(max(chapter_index, 0), len(chapters) - 1)]
    chapter_text = "\n".join(lines[chosen.start_line - 1 : chosen.end_line])

    module_type = _detect_module_type(book_file, passport) if module_override == "auto" else module_override

    if module_type == "latyshova_gis":
        physics_data = simulate_well_log()
        scenes = _latyshova_gold_scenes(physics_data)
    elif module_type == "basniev_hydro":
        dup = simulate_dupuit_flow()
        tr = simulate_psss_transient()
        physics_data = {"module": "basniev_hydro", "dupuit": dup, "transient_psss": tr}
        scenes = _basniev_gold_scenes(physics_data)
    else:
        physics_data = {
            "module": "generic_chapter",
            "formula_count": chosen.formula_count,
            "has_nomograms": chosen.has_nomograms,
        }
        scenes = _generic_chapter_scenes(chosen.title, chapter_text, passport)

    meta = passport.get("meta", {})
    school_info = meta.get("school_and_standards", {})
    course_id = f"{Path(book_file).stem}_{uuid.uuid4().hex[:8]}"

    manifest = CourseManifest(
        course_id=course_id,
        module_type=module_type,  # type: ignore[arg-type]
        book_file=book_file,
        passport_file=resolved_passport,
        book_title=meta.get("title") or book_file,
        authors=meta.get("authors") or [],
        chapter_title=chosen.title,
        chapter_number=f"Раздел {chosen.index + 1}",
        methodological_school=school_info.get("methodological_school", "soviet_cis"),
        units_system=meta.get("units_system", "soviet_practice"),
        total_duration_sec=round(sum(s.duration_sec for s in scenes), 2),
        fps=30,
        resolution="1920x1080",
        voice=voice,
        scenes=scenes,
        physics_data=physics_data,
        qa_report=QAReport(passed=True),
    )
    return manifest, chosen.title, chapter_text, passport


async def build_course_manifest(
    data_dir: Path,
    book_file: str,
    passport_file: str | None = None,
    chapter_index: int = 0,
    module_override: str = "auto",
    voice: str = "ru-RU-DmitryNeural",
    use_llm: bool = True,
) -> CourseManifest:
    """Формирует полный CourseManifest с расчётами physics_engine и Scene Graph."""
    manifest, chosen_title, chapter_text, passport = build_course_manifest_sync(
        data_dir=data_dir,
        book_file=book_file,
        passport_file=passport_file,
        chapter_index=chapter_index,
        module_override=module_override,
        voice=voice,
    )
    if use_llm:
        manifest.scenes = await _try_llm_enrich_scenes(chosen_title, chapter_text, passport, manifest.scenes)
        manifest.total_duration_sec = round(sum(s.duration_sec for s in manifest.scenes), 2)
    return manifest
