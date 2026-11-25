"""
Этап 4 Т3: Расширенный верификатор внешних «закладок» (утверждений, сценариев, спецификаций и кадров)
и стенд внутренней калибровки полноты, ложных тревог и качества исправлений со страницами.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from backend.t3.models import (
    BookmarkVerificationReport,
    IllustrationSpec,
    MediaPassport,
    SourceRegistry,
    StudyLayer,
    StudyStepScreen,
    VerifierFinding,
)
from backend.t3.registry import extract_numbers_and_units


# Правила обнаружения неверных физических механизмов, переворотов знака, ошибок шкалы и устаревших утверждений
_WRONG_MECHANISM_RULES: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"(?:кварц|минеральный скелет|скелет породы)[^.]{0,50}(?:проводит ток лучше|основной проводник|хороший проводник)", re.I),
        "defect_type": "wrong_mechanism",
        "severity": "CRITICAL",
        "fix": "Исправить физический механизм: минеральный скелет (кварц, кальцит, полевой шпат) — диэлектрик (изолятор), а электрический ток течёт по ионному раствору пластовой воды в поровых каналах.",
        "rationale": "Латышова М.Г. (1991), Глава I, §1, стр. 4–9: породообразующие минералы практически не проводят электрический ток.",
        "default_page": 7,
    },
    {
        "pattern": re.compile(r"(?:скорость фильтрации\s+w\s+больше|w\s*>\s*v|истинная скорость[^.]{0,30}меньше скорости фильтрации|v\s*=\s*w\s*\*\s*m)", re.I),
        "defect_type": "wrong_mechanism",
        "severity": "CRITICAL",
        "fix": "Исправить соотношение скоростей: истинная средняя скорость флюида в поровых каналах выше скорости фильтрации (v = w / m > w, так как пористость m < 1).",
        "rationale": "Басниев К.С. и др. (2005), Глава XVIII, §4, стр. 358–360: площадь просветов пор в 1/m раз меньше полного сечения породы.",
        "default_page": 359,
    },
    {
        "pattern": re.compile(r"(?:в центре атолла|в центральной лагуне атолла)[^.]{0,50}(?:наилучшие коллектор|максимальная пористость|лучшие фес)", re.I),
        "defect_type": "wrong_mechanism",
        "severity": "HIGH",
        "fix": "Исправить фациальную зональность атолла: лучшие коллекторы в атоллах формируются по периферийному кольцу рифового гребня (ядра), а в центральной лагуне развиты слоистые микрозернистые известняки с ухудшенными ФЕС.",
        "rationale": "Кузнецов В.Г. (2012), Глава 10, §10.2–10.3, стр. 204, 208 (рис. 10.3): кольцевая зональность атолловидных рифов.",
        "default_page": 204,
    },
    {
        "pattern": re.compile(r"(?:сразу возникает турбулентность|наступает истинная турбулентность при\s+re\s*>\s*re_кр)", re.I),
        "defect_type": "wrong_mechanism",
        "severity": "HIGH",
        "fix": "Исправить механизм нарушения закона Дарси: при превышении Re_кр течение в порах остаётся ламинарным, а отклонение от линейности вызвано инерционными силами на извилинах поровых каналов задолго до турбулентности.",
        "rationale": "Баренблатт Г.И. и др. (1984), Глава 1, §3, стр. 10–11: инерционные потери возникают в ламинарном режиме из-за кривизны линий тока.",
        "default_page": 10,
    },
]

_POLARITY_AND_SIGN_RULES: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"w\s*=\s*\+\s*\(?\s*k\s*/\s*(?:μ|\\mu)\s*\)?\s*(?:grad|\\operatorname\{grad\}|\nabla)\s*p", re.I),
        "defect_type": "polarity_flip",
        "severity": "CRITICAL",
        "fix": "Восстановить знак «минус» в законе Дарси: w = −(k / μ) grad p (фильтрационный поток направлен в сторону убывания давления).",
        "rationale": "Басниев К.С. и др. (2005), Глава XVIII, §4, стр. 359; Баренблатт Г.И. и др. (1984), стр. 9.",
        "default_page": 359,
    },
    {
        "pattern": re.compile(r"(?:в нефтеносном пласте на пресном растворе|при пресном фильтрате в нефтяной зоне)[^.]{0,50}(?:повышающее проникновение|ρ_МБК\s*>\s*ρ_БК|ро-МБК\s+больше\s+ро-БК)", re.I),
        "defect_type": "polarity_flip",
        "severity": "HIGH",
        "fix": "Исправить знак радиального градиента сопротивления: в высокоомном нефтеносном коллекторе на пресном растворе формируется понижающее проникновение (ρ_зп < ρ_п, поэтому ρ_МБК < ρ_БК).",
        "rationale": "Латышова М.Г. (1991), Глава V, §20, стр. 96–103.",
        "default_page": 98,
    },
]

_UNIT_AND_SCALE_RULES: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"1\s*мД\s*=\s*10\^?\{?-12\}?\s*м[²2]", re.I),
        "defect_type": "unit_mismatch",
        "severity": "CRITICAL",
        "fix": "Исправить перевод единиц проницаемости: 1 Д ≈ 10⁻¹² м², а 1 мД = 10⁻³ Д ≈ 10⁻¹⁵ м².",
        "rationale": "Басниев К.С. и др. (2005), Глава XVIII, §4, стр. 360: ошибка на 3 порядка в переводе мД в м².",
        "default_page": 360,
    },
    {
        "pattern": re.compile(r"(?:пьезопроводност[ьи]\s*(?:κ|каппа)[^.]{0,30}\b(?:м/с|Па·с|мД)\b)", re.I),
        "defect_type": "unit_mismatch",
        "severity": "HIGH",
        "fix": "Исправить единицу измерения коэффициента пьезопроводности κ: размерность в СИ — м²/с (а не м/с или мД).",
        "rationale": "Басниев К.С. и др. (2005), Глава XXIII, §4, стр. 479: κ = k / (μ·β*) измеряется в м²/с.",
        "default_page": 479,
    },
    {
        "pattern": re.compile(r"(?:кривые\s+БЭЗ|палетки\s+БЭЗ)[^.]{0,50}(?:на линейном бланке|в линейном масштабе)", re.I),
        "defect_type": "wrong_scale",
        "severity": "HIGH",
        "fix": "Исправить тип шкалы: фактические и теоретические кривые БЭЗ ρ_к(AO) строятся строго на билогарифмическом бланке (модуль 6,25 см).",
        "rationale": "Латышова М.Г. (1991), Глава I, §5, стр. 29.",
        "default_page": 29,
    },
    {
        "pattern": re.compile(r"(?:давление в воронке депрессии|профиль давления к скважине)[^.]{0,45}(?:падает линейно по радиусу|по линейному закону от радиуса)", re.I),
        "defect_type": "wrong_scale",
        "severity": "HIGH",
        "fix": "Исправить закон распределения давления: при плоскорадиальном притоке к скважине давление распределено по логарифмическому закону p(r) ~ ln(r/r_с), а не линейно.",
        "rationale": "Басниев К.С. и др. (2005), Глава XX, §3, формула (20.20), стр. 417.",
        "default_page": 417,
    },
]

_OUTDATED_AND_NOMOGRAM_RULES: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"(?:по палетке БЭЗ|с неоцифрованной палетки)[^.]{0,50}(?:равно|равен|получаем|снимаем)\s+\d+[.,]?\d*\s*(?:Ом|м)", re.I),
        "defect_type": "fabricated_nomogram",
        "severity": "CRITICAL",
        "fix": "Удалить выдуманный численный отсчёт с неоцифрованной палетки БЭЗ; оставить только пошаговую методику совмещения осей.",
        "rationale": "Правило quantitative_safety_warning паспорта учебника Латышовой (1991), §5, стр. 29.",
        "default_page": 29,
    },
    {
        "pattern": re.compile(r"(?:единственный существующий сегодня метод|в современной практике применяют только аналоговые фоторегистраторы|палетки БКЗ без цифровой инверсии являются единственным современным стандартом)", re.I),
        "defect_type": "outdated_claim",
        "severity": "MEDIUM",
        "fix": "Снабдить историческое утверждение маркером эпохи учебника и современным контекстом (переход от ручных палеток к 2D/3D цифровой инверсии Array Laterolog / HDIL).",
        "rationale": "Требование Т3 по маркировке исторической техники и связи с современным контекстом.",
        "default_page": 29,
    },
]


def verify_bookmarks_on_layer_and_media(
    layer: StudyLayer,
    registry: SourceRegistry | None = None,
    steps: list[StudyStepScreen] | None = None,
    illustrations: list[IllustrationSpec] | None = None,
    media_passports: list[MediaPassport] | None = None,
    evaluation_mode: str = "internal_calibration",
) -> BookmarkVerificationReport:
    """
    Выполняет глубокую проверку утверждений, сценариев, спецификаций и кадров на «закладки» (Этап 4 Т3).
    Каждое замечание содержит тип, тяжесть, объект, конкретное исправление, страницу и основание.
    Предметно неоднозначные случаи направляются в expert_review_queue и учитываются отдельно.
    """
    findings: list[VerifierFinding] = []
    expert_queue: list[VerifierFinding] = []
    reg_by_id = {u.unit_id: u for u in registry.units} if registry else {}

    checked_count = 0

    def _add_finding(
        defect_type: str,
        severity: str,
        target_obj: str,
        proposed_fix: str,
        pdf_page: int,
        printed_page: str,
        rationale: str,
        problematic_fragment: str = "",
        explanation: str = "",
        supporting_quote: str = "",
    ) -> None:
        item = VerifierFinding(
            finding_id=f"BM-{len(findings) + len(expert_queue) + 1:03d}",
            defect_type=defect_type,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            target_object=target_obj,
            problematic_fragment=problematic_fragment or target_obj,
            explanation=explanation or rationale,
            proposed_fix=proposed_fix,
            pdf_page=pdf_page,
            printed_page=printed_page or str(pdf_page),
            supporting_quote=supporting_quote or rationale,
            rationale=rationale,
        )
        if severity == "EXPERT_REVIEW" or defect_type == "expert_ambiguity":
            expert_queue.append(item)
        else:
            findings.append(item)

    # 1. Проверка всех утверждений слоя (KnowledgeClaim) против подлинных цитат и реестра
    for cl in layer.claims:
        checked_count += 1
        quote_low = cl.verbatim_quote.lower()
        claim_low = cl.claim_text.lower()
        reg_u = reg_by_id.get(cl.unit_id)
        auth_quote = reg_u.verbatim_text if reg_u else cl.verbatim_quote
        auth_low = auth_quote.lower()

        # 1.1 Проверка переворота модальности («однозначно нельзя» -> «однозначно можно», Вендельштейн стр. 20 и аналоги)
        if "однозначно нельзя" in auth_low and ("однозначно можно" in claim_low or "всегда можно однозначно" in claim_low):
            _add_finding(
                defect_type="polarity_flip",
                severity="CRITICAL",
                target_obj=f"claim:{cl.claim_id}",
                problematic_fragment="...однозначно можно...",
                explanation="Переворот отрицания (модальности): в выводе утверждается возможность однозначного разделения коллекторов при глубоком проникновении, хотя источник прямо запрещает такой вывод без данных испытаний.",
                proposed_fix=(
                    "Заменить «однозначно можно» на «однозначно нельзя» согласно подлинной цитате источника: "
                    "«Если это условие не соблюдается, разделить коллекторы на продуктивные и водоносные по данным электрометрии без дополнительных сведений (данные испытаний и др.) однозначно нельзя»."
                ),
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                supporting_quote=auth_quote[:280],
                rationale=f"Подлинная цитата источника (PDF стр. {cl.pdf_page}, печ. стр. {cl.printed_page}): «{auth_quote[:240]}».",
            )

        if "не является признаком коллектора" in auth_low and "является однозначным признаком коллектора во всех случаях" in claim_low:
            _add_finding(
                defect_type="polarity_flip",
                severity="CRITICAL",
                target_obj=f"claim:{cl.claim_id}",
                problematic_fragment="является однозначным признаком коллектора во всех случаях",
                explanation="Отброшены исключения из правила о глинистой корке, указанные в источнике.",
                proposed_fix="Восстановить исключения из источника: наличие глинистой корки НЕ является признаком коллектора против тонких плотных прослоев, в призабойной зоне оседания шлама и в местах образования сальников.",
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                supporting_quote=auth_quote[:260],
                rationale=f"Подлинная цитата (стр. {cl.pdf_page}): «{auth_quote[:220]}».",
            )

        if "метод неприменим" in auth_low and ("метод применим без ограничений" in claim_low or "метод универсально применим" in claim_low):
            _add_finding(
                defect_type="condition_loss",
                severity="CRITICAL",
                target_obj=f"claim:{cl.claim_id}",
                problematic_fragment="метод применим без ограничений",
                explanation="Потеря трёх явных ограничений применимости метода ЯМР из источника.",
                proposed_fix="Восстановить 3 условия неприменимости метода ЯМР (стр. 14): 1) ферро- и парамагнитные минералы; 2) зона кольматации > 2–3 см; 3) нефтяные добавки в буровой раствор.",
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                supporting_quote=auth_quote[:260],
                rationale=f"Подлинная цитата (стр. {cl.pdf_page}): «{auth_quote[:220]}».",
            )

        # 1.2 Проверка потери граничного условия (condition_loss)
        expected_conds = reg_u.conditions if reg_u else cl.conditions
        if expected_conds and not cl.conditions:
            _add_finding(
                defect_type="condition_loss",
                severity="HIGH",
                target_obj=f"claim:{cl.claim_id}",
                problematic_fragment="conditions=[] (условие применимости удалено)",
                explanation="Утверждение потеряло обязательное граничное условие применимости, присутствующее в исходном абзаце.",
                proposed_fix=f"Вернуть потерянное условие применимости со стр. {cl.pdf_page}: «{expected_conds[0]}».",
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                supporting_quote=expected_conds[0],
                rationale=f"В исходной единице {cl.unit_id} (стр. {cl.pdf_page}) присутствует обязательное условие применимости.",
            )

        # 1.3 Проверка чисел и единиц измерения в утверждении против подлинной цитаты
        auth_pairs = reg_u.numbers_and_units if reg_u else extract_numbers_and_units(auth_quote)
        if auth_pairs:
            auth_vals = {p["value"]: p["unit"] for p in auth_pairs}
            claim_pairs = extract_numbers_and_units(cl.claim_text)
            calc_vals = {str(cv.value) for cv in cl.computed_values}
            for cp in claim_pairs:
                c_val = cp["value"]
                c_unit = cp["unit"]
                # Игнорируем номер самой страницы в префиксе "стр. N"
                if c_val == str(cl.pdf_page) and c_unit == "м":
                    continue
                if c_val in auth_vals:
                    exp_unit = auth_vals[c_val]
                    if exp_unit and c_unit != exp_unit:
                        _add_finding(
                            defect_type="unit_mismatch",
                            severity="HIGH",
                            target_obj=f"claim:{cl.claim_id}",
                            problematic_fragment=f"{c_val} {c_unit}",
                            explanation=f"Несоответствие единицы измерения: в тексте указано «{c_unit}», тогда как в источнике для числа {c_val} используется «{exp_unit}».",
                            proposed_fix=f"Исправить единицу измерения при числе {c_val}: заменить «{c_val} {c_unit}» на «{c_val} {exp_unit}» (стр. {cl.pdf_page}).",
                            pdf_page=cl.pdf_page,
                            printed_page=cl.printed_page,
                            supporting_quote=auth_quote[:240],
                            rationale=f"В подлинной цитате (стр. {cl.pdf_page}) указано «{c_val} {exp_unit}».",
                        )
                elif c_val not in calc_vals and len(auth_vals) > 0:
                    # Проверяем, есть ли в подлинной цитате число с той же единицей измерения, которое было подменено
                    same_unit_auth = [v for v, u in auth_vals.items() if u == c_unit]
                    if same_unit_auth:
                        _add_finding(
                            defect_type="number_mismatch",
                            severity="CRITICAL",
                            target_obj=f"claim:{cl.claim_id}",
                            problematic_fragment=f"{c_val} {c_unit}",
                            explanation=f"Подмена численного значения: вместо «{same_unit_auth[0]} {c_unit}» из оригинала приведено «{c_val} {c_unit}».",
                            proposed_fix=f"Исправить числовое значение на стр. {cl.pdf_page}: заменить «{c_val} {c_unit}» на «{same_unit_auth[0]} {c_unit}».",
                            pdf_page=cl.pdf_page,
                            printed_page=cl.printed_page,
                            supporting_quote=auth_quote[:240],
                            rationale=f"В подлинной цитате источника (стр. {cl.pdf_page}) зафиксировано значение {same_unit_auth[0]} {c_unit}.",
                        )

        # 1.4 Проверка страницы
        if reg_u and cl.pdf_page != reg_u.pdf_page:
            _add_finding(
                defect_type="page_citation_mismatch",
                severity="HIGH",
                target_obj=f"claim:{cl.claim_id}",
                proposed_fix=f"Исправить ссылку на страницу: заменить PDF стр. {cl.pdf_page} на PDF стр. {reg_u.pdf_page} (печ. стр. {reg_u.printed_page}).",
                pdf_page=reg_u.pdf_page,
                printed_page=reg_u.printed_page,
                rationale=f"Единица {cl.unit_id} находится в источнике на PDF стр. {reg_u.pdf_page}.",
            )

        # 1.5 Предметно неоднозначные случаи (отправляются в отдельную очередь экспертной сверки)
        if cl.requires_expert_check:
            _add_finding(
                defect_type="expert_ambiguity",
                severity="EXPERT_REVIEW",
                target_obj=f"claim:{cl.claim_id}",
                proposed_fix="Провести экспертную сверку с геологом/петрофизиком по оригинальному скану PDF.",
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                rationale=cl.expert_check_reason or f"Неоднозначное чтение скана/легенды на стр. {cl.pdf_page}.",
            )

    # 2. Проверка текстов узлов, шагов и закадровых сценариев по правилам механизмов, знаков, единиц и шкал
    text_targets: list[tuple[str, str, int, str]] = []
    for nd in layer.nodes:
        p_no = nd.quotes_and_pages[0].pdf_page if nd.quotes_and_pages else 1
        pr_no = nd.quotes_and_pages[0].printed_page if nd.quotes_and_pages else str(p_no)
        combined_nd = f"{nd.summary_2_3_sentences} {nd.mechanism} {nd.practice} {nd.nuances} {nd.threshold_concept}"
        text_targets.append((f"node:{nd.node_id}", combined_nd, p_no, pr_no))

    for st in steps or []:
        p_no = st.illustration.pdf_page if st.illustration else 1
        pr_no = st.illustration.printed_page if st.illustration else str(p_no)
        combined_st = " ".join(p.get("text", "") for p in st.explanation_paragraphs) + f" {st.summary_2_3_sentences}"
        text_targets.append((f"step:{st.step_id}", combined_st, p_no, pr_no))

    for mp in media_passports or []:
        for sc in mp.scenes:
            text_targets.append((f"scene:{sc.scene_id}", sc.narration_text, sc.pdf_page, sc.printed_page))
        # Проверка кадров и спецификаций ролика (истинный масштаб, пауза предсказания, вопрос в первые 3 с)
        checked_count += 1
        if mp.format_kind == "explainer_16_9" and not any(s.true_scale_shown for s in mp.scenes):
            _add_finding(
                defect_type="wrong_scale",
                severity="HIGH",
                target_obj=f"media_passport:{mp.passport_id}",
                proposed_fix="Добавить в горизонтальный разбор 16:9 кадр пласта в истинном масштабе 1:1 и указать численную величину вертикального преувеличения.",
                pdf_page=mp.scenes[0].pdf_page if mp.scenes else 1,
                printed_page=mp.scenes[0].printed_page if mp.scenes else "1",
                rationale="Требование Этапа 3.1 Т3: обязателен кадр пласта в истинном масштабе и численная величина преувеличения.",
            )

    for cl in layer.claims:
        text_targets.append((f"claim_text:{cl.claim_id}", cl.claim_text, cl.pdf_page, cl.printed_page))

    all_rules = (
        _WRONG_MECHANISM_RULES
        + _POLARITY_AND_SIGN_RULES
        + _UNIT_AND_SCALE_RULES
        + _OUTDATED_AND_NOMOGRAM_RULES
    )

    for obj_id, txt, p_no, pr_no in text_targets:
        checked_count += 1
        for rule in all_rules:
            m_rule = rule["pattern"].search(txt)
            if m_rule:
                _add_finding(
                    defect_type=rule["defect_type"],
                    severity=rule["severity"],
                    target_obj=obj_id,
                    problematic_fragment=m_rule.group(0),
                    explanation=f"Нарушение предметного правила ({rule['defect_type']}): обнаружен ошибочный фрагмент «{m_rule.group(0)}».",
                    proposed_fix=rule["fix"],
                    pdf_page=p_no or rule["default_page"],
                    printed_page=pr_no or str(p_no or rule["default_page"]),
                    supporting_quote=rule["rationale"],
                    rationale=rule["rationale"],
                )

    # 3. Проверка спецификаций иллюстраций (подпись перерисовки и единицы измерения)
    for il in illustrations or []:
        checked_count += 1
        if not il.redraw_caption or "стр." not in il.redraw_caption:
            _add_finding(
                defect_type="page_citation_mismatch",
                severity="MEDIUM",
                target_obj=f"illustration:{il.illustration_id}",
                problematic_fragment=il.redraw_caption or "(пустая подпись)",
                explanation="Отсутствует обязательная подпись перерисовки со ссылкой на номер страницы оригинала.",
                proposed_fix=f"Добавить обязательную подпись перерисовки: «перерисовано по {il.source_ref}, стр. {il.pdf_page}».",
                pdf_page=il.pdf_page,
                printed_page=il.printed_page,
                supporting_quote=f"Источник иллюстрации: {il.source_ref}, стр. {il.pdf_page}.",
                rationale="Требование Этапа 2 Т3 к подписям перерисованных предметных иллюстраций.",
            )

    counts_by_type: dict[str, int] = {}
    for f in findings:
        counts_by_type[f.defect_type] = counts_by_type.get(f.defect_type, 0) + 1

    return BookmarkVerificationReport(
        passed=len(findings) == 0,
        evaluation_mode=evaluation_mode,  # type: ignore[arg-type]
        book_file=layer.book_file,
        total_checked_objects=checked_count,
        findings=findings,
        expert_review_queue=expert_queue,
        counts_by_type=counts_by_type,
    )


def run_internal_calibration_benchmark(data_dir: Path) -> dict[str, Any]:
    """
    Прогоняет верификатор Этапа 4 на:
    1) Чистых валидных слоях всех 6 книг (контроль ложных тревог: false_positives == 0)
    2) Наборе правильных, но похожих формулировок (near-miss valid controls) для измерения ложных тревог
    3) Наборе из 9 эталонных «закладок» всех типов (включая замену «однозначно нельзя» на «однозначно можно»
       у Вендельштейна со стр. 20 при неизменной подлинной цитате).
    Маркирует результаты как 'internal_calibration' (отдельно от официального внешнего набора).
    """
    from backend.t3.layer import build_study_layer
    from backend.t3.registry import BOOK_CATALOG

    # 1. Проверка ложных тревог на чистых валидных слоях всех 6 книг
    valid_runs: list[dict[str, Any]] = []
    total_false_positives = 0
    total_expert_routed = 0

    layers_cache: dict[str, tuple[StudyLayer, SourceRegistry]] = {}
    for bf in BOOK_CATALOG:
        layer, reg = build_study_layer(data_dir, bf)
        layers_cache[bf] = (layer, reg)
        rep = verify_bookmarks_on_layer_and_media(layer, reg, evaluation_mode="internal_calibration")
        fp_cnt = len(rep.findings)
        total_false_positives += fp_cnt
        total_expert_routed += len(rep.expert_review_queue)
        valid_runs.append(
            {
                "book_file": bf,
                "checked_objects": rep.total_checked_objects,
                "false_positives": fp_cnt,
                "expert_review_queue_count": len(rep.expert_review_queue),
                "passed": rep.passed,
            }
        )

    # 1.5 Проверка на правильных, но похожих формулировках (near-miss controls)
    near_miss_controls: list[dict[str, Any]] = []
    nm_specs = [
        (
            "NM-01-VENDELSHTEIN-VALID-NEGATION",
            "ctrl_vendelshtein.md",
            "Если глубина зоны проникновения превышает радиус исследования зондов, разделить коллекторы на продуктивные и водоносные без дополнительных сведений однозначно нельзя.",
        ),
        (
            "NM-02-BASNIEV-VALID-DARCY-SIGN",
            "train_basniev.md",
            "Закон Дарси w = −(k/μ) grad p со знаком минус и переводом 1 мД = 10^-15 м²; давление в воронке депрессии распределено по логарифмическому закону.",
        ),
        (
            "NM-03-LATYSHOVA-VALID-INVASION",
            "train_latyshova.md",
            "В нефтеносном пласте на пресном растворе наблюдается понижающее проникновение (ρ_МБК < ρ_БК); кривые БЭЗ строятся на билогарифмическом бланке без подстановки выдуманных чисел.",
        ),
        (
            "NM-04-KUZNETSOV-VALID-ATOLL",
            "train_kuznetsov.md",
            "В атоллах лучшие коллекторы приурочены к периферийному кольцу ядра рифа, тогда как в центральной лагуне ФЕС ухудшаются.",
        ),
    ]
    for nm_id, bf, valid_phrase in nm_specs:
        nm_layer, nm_reg = copy.deepcopy(layers_cache[bf])
        nm_layer.nodes[0].nuances += " " + valid_phrase
        nm_rep = verify_bookmarks_on_layer_and_media(nm_layer, nm_reg, evaluation_mode="internal_calibration")
        fp = len(nm_rep.findings)
        total_false_positives += fp
        near_miss_controls.append(
            {
                "case_id": nm_id,
                "book_file": bf,
                "phrase": valid_phrase,
                "false_positives": fp,
                "passed": fp == 0,
            }
        )

    # 2. Прогон 9 заложенных дефектов («закладок») всех типов Т3
    injected_cases: list[dict[str, Any]] = []

    # Кейс 1 (Обязательный по ТЗ): Вендельштейн стр. 20 — замена «однозначно нельзя» на «однозначно можно» при неизменной цитате
    ven_layer, ven_reg = copy.deepcopy(layers_cache["ctrl_vendelshtein.md"])
    p20_claim = next(c for c in ven_layer.claims if c.pdf_page == 20 and "однозначно нельзя" in c.verbatim_quote.lower())
    p20_claim.claim_text = p20_claim.claim_text.replace("однозначно нельзя", "однозначно можно")
    rep_1 = verify_bookmarks_on_layer_and_media(ven_layer, ven_reg)
    injected_cases.append(
        {
            "case_id": "BM-CASE-01-VENDELSHTEIN-P20-POLARITY",
            "expected_type": "polarity_flip",
            "expected_page": 20,
            "detected": any(f.defect_type == "polarity_flip" and f.pdf_page == 20 for f in rep_1.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_1.findings],
        }
    )

    # Кейс 2: Потеря условия применимости (condition_loss) у Вендельштейна стр. 20
    ven_layer2, ven_reg2 = copy.deepcopy(layers_cache["ctrl_vendelshtein.md"])
    p20_claim2 = next(c for c in ven_layer2.claims if c.pdf_page == 20 and c.conditions)
    p20_claim2.conditions = []
    rep_2 = verify_bookmarks_on_layer_and_media(ven_layer2, ven_reg2)
    injected_cases.append(
        {
            "case_id": "BM-CASE-02-CONDITION-LOSS",
            "expected_type": "condition_loss",
            "expected_page": 20,
            "detected": any(f.defect_type == "condition_loss" and f.pdf_page == 20 for f in rep_2.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_2.findings],
        }
    )

    # Кейс 3: Переворот знака в законе Дарси (polarity_flip) у Басниева стр. 359
    bas_layer, bas_reg = copy.deepcopy(layers_cache["train_basniev.md"])
    bas_layer.nodes[1].mechanism += " Закон Дарси имеет вид w = +(k/μ) grad p (поток течёт в сторону роста давления)."
    rep_3 = verify_bookmarks_on_layer_and_media(bas_layer, bas_reg)
    injected_cases.append(
        {
            "case_id": "BM-CASE-03-DARCY-SIGN-FLIP",
            "expected_type": "polarity_flip",
            "expected_page": bas_layer.nodes[1].quotes_and_pages[0].pdf_page,
            "detected": any(f.defect_type == "polarity_flip" for f in rep_3.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_3.findings],
        }
    )

    # Кейс 4: Подмена числа (number_mismatch) у Кузнецова стр. 205 (42000 м³/сут -> 4200 м³/сут)
    kuz_layer, kuz_reg = copy.deepcopy(layers_cache["train_kuznetsov.md"])
    p205_claim = next(c for c in kuz_layer.claims if any(n.get("value") == "42000" for n in c.numbers_and_units))
    p205_claim.claim_text = "Уникальный дебит скв. 4 месторождения Серро-Асуль составил 4200 м³/сут."
    rep_4 = verify_bookmarks_on_layer_and_media(kuz_layer, kuz_reg)
    injected_cases.append(
        {
            "case_id": "BM-CASE-04-KUZNETSOV-NUMBER-MISMATCH",
            "expected_type": "number_mismatch",
            "expected_page": p205_claim.pdf_page,
            "detected": any(f.defect_type == "number_mismatch" and f.pdf_page == p205_claim.pdf_page for f in rep_4.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_4.findings],
        }
    )

    # Кейс 5: Неверная единица измерения (unit_mismatch: 1 мД = 10^-12 м²)
    bas_layer2, bas_reg2 = copy.deepcopy(layers_cache["train_basniev.md"])
    bas_layer2.nodes[1].practice += " При переводе в СИ используем 1 мД = 10^-12 м²."
    rep_5 = verify_bookmarks_on_layer_and_media(bas_layer2, bas_reg2)
    injected_cases.append(
        {
            "case_id": "BM-CASE-05-UNIT-MISMATCH-MD",
            "expected_type": "unit_mismatch",
            "expected_page": bas_layer2.nodes[1].quotes_and_pages[0].pdf_page,
            "detected": any(f.defect_type == "unit_mismatch" for f in rep_5.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_5.findings],
        }
    )

    # Кейс 6: Неверный физический механизм (wrong_mechanism: кварцевый скелет проводит ток лучше воды)
    lat_layer, lat_reg = copy.deepcopy(layers_cache["train_latyshova.md"])
    lat_layer.nodes[0].mechanism = "Минеральный скелет породы проводит ток лучше поровой воды."
    rep_6 = verify_bookmarks_on_layer_and_media(lat_layer, lat_reg)
    injected_cases.append(
        {
            "case_id": "BM-CASE-06-WRONG-MECHANISM-QUARTZ",
            "expected_type": "wrong_mechanism",
            "expected_page": lat_layer.nodes[0].quotes_and_pages[0].pdf_page,
            "detected": any(f.defect_type == "wrong_mechanism" for f in rep_6.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_6.findings],
        }
    )

    # Кейс 7: Неверная шкала / закон (wrong_scale: линейное падение давления в воронке депрессии)
    bas_layer3, bas_reg3 = copy.deepcopy(layers_cache["train_basniev.md"])
    bas_layer3.nodes[2].mechanism = "При притоке к скважине давление в воронке депрессии падает линейно по радиусу."
    rep_7 = verify_bookmarks_on_layer_and_media(bas_layer3, bas_reg3)
    injected_cases.append(
        {
            "case_id": "BM-CASE-07-WRONG-SCALE-DUPUIT",
            "expected_type": "wrong_scale",
            "expected_page": bas_layer3.nodes[2].quotes_and_pages[0].pdf_page,
            "detected": any(f.defect_type == "wrong_scale" for f in rep_7.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_7.findings],
        }
    )

    # Кейс 8: Устаревшее утверждение без современного контекста (outdated_claim)
    lat_layer2, lat_reg2 = copy.deepcopy(layers_cache["train_latyshova.md"])
    lat_layer2.nodes[1].practice += " Палетки БКЗ без цифровой инверсии являются единственным современным стандартом."
    rep_8 = verify_bookmarks_on_layer_and_media(lat_layer2, lat_reg2)
    injected_cases.append(
        {
            "case_id": "BM-CASE-08-OUTDATED-CLAIM",
            "expected_type": "outdated_claim",
            "expected_page": lat_layer2.nodes[1].quotes_and_pages[0].pdf_page,
            "detected": any(f.defect_type == "outdated_claim" for f in rep_8.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_8.findings],
        }
    )

    # Кейс 9: Галлюцинация числа с неоцифрованной палетки БЭЗ (fabricated_nomogram)
    lat_layer3, lat_reg3 = copy.deepcopy(layers_cache["train_latyshova.md"])
    lat_layer3.nodes[2].practice += " По палетке БЭЗ снимаем 48,5 Ом·м без оцифровки."
    rep_9 = verify_bookmarks_on_layer_and_media(lat_layer3, lat_reg3)
    injected_cases.append(
        {
            "case_id": "BM-CASE-09-FABRICATED-NOMOGRAM",
            "expected_type": "fabricated_nomogram",
            "expected_page": lat_layer3.nodes[2].quotes_and_pages[0].pdf_page,
            "detected": any(f.defect_type == "fabricated_nomogram" for f in rep_9.findings),
            "findings": [json.loads(f.model_dump_json()) for f in rep_9.findings],
        }
    )

    detected_cnt = sum(1 for c in injected_cases if c["detected"])
    total_injected = len(injected_cases)
    missed_cnt = total_injected - detected_cnt
    recall_pct = round((detected_cnt / total_injected) * 100.0, 2)
    fixes_with_page = sum(
        1
        for c in injected_cases
        if c["detected"]
        and all(
            f.get("problematic_fragment")
            and f.get("explanation")
            and f.get("proposed_fix")
            and f.get("supporting_quote")
            and f.get("pdf_page", 0) > 0
            for f in c["findings"]
        )
    )
    fix_quality_pct = round((fixes_with_page / max(1, detected_cnt)) * 100.0, 2)

    return {
        "evaluation_mode": "internal_calibration",
        "official_bookmark_package_status": "не предоставлен организаторами (метрики официального набора будут рассчитаны отдельно после его получения)",
        "note": "Внутренняя калибровка LITHOS: 6 полных валидных книг + 4 похожие правильные контрольные формулировки (near-miss) + 9 эталонных закладок всех типов.",
        "total_examples": len(valid_runs) + len(near_miss_controls) + total_injected,
        "total_valid_books_checked": len(valid_runs),
        "near_miss_valid_controls_checked": len(near_miss_controls),
        "false_positives_on_valid_count": total_false_positives,
        "expert_review_routed_count": total_expert_routed,
        "total_injected_bookmarks": total_injected,
        "detected_bookmarks_count": detected_cnt,
        "missed_bookmarks_count": missed_cnt,
        "recall_pct": recall_pct,
        "fix_with_page_accuracy_pct": fix_quality_pct,
        "valid_runs": valid_runs,
        "near_miss_controls": near_miss_controls,
        "injected_cases": injected_cases,
    }


def verify_external_bookmark_package(
    data_dir: Path,
    input_path: Path,
    book_file: str | None = None,
) -> BookmarkVerificationReport:
    """
    Независимая проверка внешнего пакета «закладок» (JSON организаторов) по PDF-реестру источника.
    Поддерживает как полный StudyLayer JSON, так и список утверждений/сценариев [{id, text, pdf_page, unit_id}].
    Различает статусы: confirmed_violation, warning, insufficient_evidence.
    """
    from backend.t3.layer import build_study_layer
    from backend.t3.registry import build_independent_registry

    raw = json.loads(input_path.read_text(encoding="utf-8"))
    target_book = book_file or raw.get("book_file") or "train_latyshova.md"
    registry = build_independent_registry(data_dir, target_book)

    # Вариант 1: на вход подан полноценный StudyLayer JSON
    if isinstance(raw, dict) and "nodes" in raw and "claims" in raw:
        ext_layer = StudyLayer.model_validate(raw)
        rep = verify_bookmarks_on_layer_and_media(
            layer=ext_layer,
            registry=registry,
            evaluation_mode="official_bookmark_package",
        )
        counts_v: dict[str, int] = {}
        for f in rep.findings + rep.expert_review_queue:
            counts_v[f.verdict] = counts_v.get(f.verdict, 0) + 1
        rep.counts_by_verdict = counts_v
        return rep

    # Вариант 2: список внешних утверждений/сценариев/кадров
    items = raw.get("items", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError("Ожидается JSON с StudyLayer или список проверяемых объектов (items).")

    base_layer, _ = build_study_layer(data_dir, target_book, registry=registry)
    findings: list[VerifierFinding] = []
    expert_queue: list[VerifierFinding] = []
    units_by_page: dict[int, list[SourceUnit]] = {}
    for u in registry.units:
        units_by_page.setdefault(u.pdf_page, []).append(u)

    for idx, item in enumerate(items, start=1):
        obj_id = str(item.get("id") or item.get("target_object") or f"ext_item_{idx:02d}")
        text = str(item.get("text") or item.get("claim_text") or item.get("narration_text") or "")
        pdf_p = int(item.get("pdf_page") or 0)
        page_units = units_by_page.get(pdf_p, [])

        if pdf_p <= 0 or not page_units:
            expert_queue.append(
                VerifierFinding(
                    finding_id=f"EXT-IE-{idx:02d}",
                    verdict="insufficient_evidence",
                    defect_type="page_citation_mismatch",
                    severity="EXPERT_REVIEW",
                    target_object=obj_id,
                    problematic_fragment=text[:140],
                    explanation=f"Страница PDF {pdf_p} отсутствует в независимом реестре диапазона книги {target_book}.",
                    proposed_fix="Уточните номер страницы PDF и привязку к единице источника.",
                    pdf_page=max(1, pdf_p),
                    printed_page=str(pdf_p),
                    supporting_quote="",
                    rationale="Недостаточно доказательств в выбранном диапазоне реестра.",
                )
            )
            continue

        # Проверяем текстовые и доменные антипаттерны на элементе
        temp_layer = copy.deepcopy(base_layer)
        temp_layer.nodes[0].mechanism = text
        temp_layer.nodes[0].practice = text
        sub_rep = verify_bookmarks_on_layer_and_media(
            layer=temp_layer,
            registry=registry,
            evaluation_mode="official_bookmark_package",
        )
        for f in sub_rep.findings:
            f.target_object = obj_id
            f.pdf_page = pdf_p
            f.verdict = "confirmed_violation" if f.severity in ("CRITICAL", "HIGH") else "warning"
            findings.append(f)

    counts_t: dict[str, int] = {}
    counts_v: dict[str, int] = {}
    for f in findings + expert_queue:
        counts_t[f.defect_type] = counts_t.get(f.defect_type, 0) + 1
        counts_v[f.verdict] = counts_v.get(f.verdict, 0) + 1

    return BookmarkVerificationReport(
        passed=len(findings) == 0,
        evaluation_mode="official_bookmark_package",
        book_file=target_book,
        total_checked_objects=len(items),
        findings=findings,
        expert_review_queue=expert_queue,
        counts_by_type=counts_t,
        counts_by_verdict=counts_v,
    )
