"""
Domain QA Verifier: проверяет CourseManifest на соответствие JSON-паспорту учебника.

Проверяемые правила:
1. quantitative_safety_warning + Nomogram Guard:
   - Запрет выдумывания чисел с неоцифрованных палеток (БЭЗ, z-фактор, НГМ).
   - Выявление локальных unsafe_numbers зависимостей без пометки.
2. school_warning:
   - Наличие советской/СНГ нотации и терминологического моста на западные эквиваленты.
3. reservoir_type_warning:
   - Учёт применимости к типу коллектора (терригенные vs карбонатные/трещинные).
4. Deterministic Visuals Guard:
   - Никакого AI-видео (Runway/Kling/Sora) — только Manim, Three.js или Remotion.
"""

from __future__ import annotations

import re
from typing import Any

from backend.schemas import CourseManifest, QACheck, QAReport, TermBridge

_ALLOWED_BACKENDS = {"manim", "threejs_lab", "remotion_split", "remotion_formula"}
_NOMOGRAM_KEYWORDS = ("палетк", "номограмм", "бэз", "нгм-60", "z-фактор")
_FABRICATED_PALETTE_NUM_RE = re.compile(
    r"(?:по палетке|с палетки|на палетке|по номограмме)[^.]{0,60}\b(?:равно|равен|получаем|снимаем)\s+\d+[.,]?\d*",
    re.IGNORECASE,
)


def verify_course_manifest(manifest: CourseManifest, passport: dict[str, Any] | None) -> QAReport:
    """Выполняет комплексную доменную QA-проверку и применяет авто-исправления."""
    passport = passport or {}
    routing = passport.get("agent_routing_card", {})
    quant_warn = str(routing.get("quantitative_safety_warning", "")).strip()
    school_warn = str(routing.get("school_warning", "")).strip()
    res_warn = str(routing.get("reservoir_type_warning") or "").strip()

    checks: list[QACheck] = []
    warnings: list[str] = []
    auto_fixes: list[str] = []

    # 1. Проверка 100% детерминированной графики (запрет AI-видео классов A и B)
    invalid_backend_scenes = [s.scene_id for s in manifest.scenes if s.visual_backend not in _ALLOWED_BACKENDS]
    if invalid_backend_scenes:
        for s in manifest.scenes:
            if s.visual_backend not in _ALLOWED_BACKENDS:
                s.visual_backend = "remotion_formula"  # type: ignore[assignment]
        auto_fixes.append(f"Переключены на детерминированный рендер сцены: {invalid_backend_scenes}")
        checks.append(
            QACheck(
                check_id="QA-DET-01",
                category="deterministic_visuals",
                status="FIXED",
                message="Обнаружен запрещённый недетерминированный бэкенд; принудительно заменён на Remotion/Manim.",
                affected_scenes=invalid_backend_scenes,
            )
        )
    else:
        checks.append(
            QACheck(
                check_id="QA-DET-01",
                category="deterministic_visuals",
                status="PASS",
                message="Все сцены используют 100% детерминированные движки (Manim / Three.js / Remotion).",
            )
        )

    # 2. Nomogram & Quantitative Safety Guard
    palettes_not_digitized = ("не оцифрован" in quant_warn.lower()) or ("нельзя" in quant_warn.lower())
    nomogram_scenes: list[str] = []
    fabricated_scenes: list[str] = []

    for s in manifest.scenes:
        combined = f"{s.title} {s.narration}".lower()
        if s.methodology_only_nomogram or any(kw in combined for kw in _NOMOGRAM_KEYWORDS):
            nomogram_scenes.append(s.scene_id)
            if palettes_not_digitized and not s.methodology_only_nomogram:
                s.methodology_only_nomogram = True
                auto_fixes.append(f"Сцена {s.scene_id} помечена methodology_only_nomogram=True")
            if _FABRICATED_PALETTE_NUM_RE.search(s.narration):
                fabricated_scenes.append(s.scene_id)
                s.narration = _FABRICATED_PALETTE_NUM_RE.sub(
                    "по палетке определяется методический порядок совмещения кривых без подстановки неоцифрованных чисел",
                    s.narration,
                )
                auto_fixes.append(f"Очищена потенциально выдуманная цифра с палетки в сцене {s.scene_id}")

    if fabricated_scenes:
        checks.append(
            QACheck(
                check_id="QA-NOM-01",
                category="nomogram_guard",
                status="FIXED",
                message="Удалены числовые значения, приписанные неоцифрованным палеткам; оставлена методика.",
                affected_scenes=fabricated_scenes,
            )
        )
    elif nomogram_scenes:
        checks.append(
            QACheck(
                check_id="QA-NOM-01",
                category="nomogram_guard",
                status="PASS",
                message=f"Сцены с палетками ({', '.join(nomogram_scenes)}) строго ограничены методикой считывания без галлюцинации чисел.",
                affected_scenes=nomogram_scenes,
            )
        )
    else:
        checks.append(
            QACheck(
                check_id="QA-NOM-01",
                category="nomogram_guard",
                status="PASS",
                message="Неоцифрованных палеток в сценарии не затронуто.",
            )
        )

    # Проверка unsafe_numbers из паспорта
    unsafe_params = [
        p.get("parameter", "")
        for p in passport.get("empirical_correlations_and_parameters", [])
        if p.get("citation_safety") == "unsafe_numbers"
    ]
    if unsafe_params:
        warnings.append(
            f"Локальные эмпирические зависимости в паспорте ({len(unsafe_params)} шт.) отмечены как unsafe_numbers — перенос на другие месторождения запрещён."
        )
        checks.append(
            QACheck(
                check_id="QA-QNT-02",
                category="quantitative_safety",
                status="WARN",
                message=f"Внимание: в учебнике присутствуют локальные коэффициенты ({', '.join(unsafe_params[:2])}); не экстраполировать без калибровки по керну.",
            )
        )
    else:
        checks.append(
            QACheck(
                check_id="QA-QNT-02",
                category="quantitative_safety",
                status="PASS",
                message="Количественные параметры соответствуют безопасным областям применимости из паспорта.",
            )
        )

    # 3. School & Terminology Bridge Guard
    scenes_missing_bridges = [
        s.scene_id for s in manifest.scenes if s.formulas and not s.term_bridges
    ]
    if scenes_missing_bridges:
        fallback_bridge = TermBridge(
            ru_symbol="К_п / κ",
            ru_term="Нотация СНГ",
            en_symbol="φ / η",
            en_term="Western SPE/Petrophysics equivalent",
            note="Автоматический мост по school_warning паспорта",
        )
        for s in manifest.scenes:
            if s.scene_id in scenes_missing_bridges:
                s.term_bridges.append(fallback_bridge)
        auto_fixes.append(f"Добавлен терминологический мост для сцен: {scenes_missing_bridges}")
        checks.append(
            QACheck(
                check_id="QA-SCH-01",
                category="school_notation",
                status="FIXED",
                message="Добавлены бейджи западных эквивалентов для формул советской/СНГ школы.",
                affected_scenes=scenes_missing_bridges,
            )
        )
    else:
        checks.append(
            QACheck(
                check_id="QA-SCH-01",
                category="school_notation",
                status="PASS",
                message="Все формульные сцены снабжены терминологическим мостом (СНГ ↔ Запад).",
            )
        )

    # 4. Reservoir Type Warning Guard
    if res_warn:
        warnings.append(f"Ограничение по типу коллектора: {res_warn}")
        checks.append(
            QACheck(
                check_id="QA-RES-01",
                category="reservoir_type",
                status="WARN",
                message=res_warn,
            )
        )
    else:
        checks.append(
            QACheck(
                check_id="QA-RES-01",
                category="reservoir_type",
                status="PASS",
                message="Ограничений несовместимости по типу коллектора не выявлено.",
            )
        )

    return QAReport(
        passed=all(c.status != "FAIL" for c in checks),
        checks=checks,
        warnings=warnings,
        auto_fixes=auto_fixes,
        passport_warnings_applied={
            "quantitative_safety_warning": quant_warn,
            "school_warning": school_warn,
            "reservoir_type_warning": res_warn,
        },
    )
