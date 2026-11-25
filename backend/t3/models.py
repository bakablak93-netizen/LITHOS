"""
Модели данных Т3 «Глава → курс» (Pydantic v2) с обратной совместимостью.
Описывают внутренний формат LITHOS и перечень полей для сопоставления с внешними схемами организаторов.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class PdfPageRange(BaseModel):
    """Непрерывный сегмент PDF-страниц (список таких сегментов образует разрывный диапазон)."""

    start_pdf_page: int = Field(..., ge=1)
    end_pdf_page: int = Field(..., ge=1)
    start_printed_page: str = Field(default="")
    end_printed_page: str = Field(default="")
    section_label: str = Field(default="")


class ComputedValueProvenance(BaseModel):
    """Происхождение расчётного значения в учебном слое."""

    parameter: str
    value: float | str
    unit: str
    model: str = Field(..., description="Математическая модель / функция physics_engine")
    inputs: dict[str, Any] = Field(default_factory=dict)
    origin: str = Field(default="physics_engine_deterministic")


class SourceUnit(BaseModel):
    """
    Единица независимого реестра источника, извлечённая напрямую из PDF и размеченных страниц
    независимо от проверяемого учебного слоя.
    """

    unit_id: str
    unit_type: Literal[
        "paragraph",
        "figure",
        "caption",
        "legend",
        "formula",
        "table",
        "worked_example",
        "problem",
        "ocr_illegible",
        "missing_scan",
    ]
    pdf_page: int
    printed_page: str
    location: str = Field(..., description="Раздел/параграф и позиция на странице")
    verbatim_text: str = Field(..., description="Точный цитатный текст из источника")
    figure_ref: str | None = Field(default=None, description="Номер рисунка/таблицы/задачи (например, Рис. 10.1)")
    numbers_and_units: list[dict[str, str]] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    ocr_status: Literal["clean", "corrected", "illegible", "missing_scan", "legend_missing"] = "clean"
    ocr_note: str = Field(default="")
    expected_inclusion: Literal["must_cover", "optional_context", "excluded_with_reason"] = "must_cover"
    default_exclusion_reason: str | None = None


class SourceRegistry(BaseModel):
    """Независимый реестр исходной главы учебника, привязанный к PDF и хешу файла."""

    registry_id: str
    book_id: str
    book_file: str
    pdf_file: str
    source_sha256: str
    total_pdf_pages: int
    chapter_id: str
    chapter_title: str
    is_training: bool = True
    pdf_ranges: list[PdfPageRange] = Field(default_factory=list)
    page_numbering_differ: bool = False
    page_numbering_note: str = ""
    units: list[SourceUnit] = Field(default_factory=list)
    summary_counts: dict[str, int] = Field(default_factory=dict)


class OCRCorrectionEntry(BaseModel):
    """Запись листа исправлений OCR с точной привязкой к PDF-странице и основанию."""

    correction_id: str
    book_file: str
    pdf_page: int
    printed_page: str
    original_ocr: str
    corrected_reading: str
    rationale: str
    applied_in_node_id: str
    applied_in_step_id: str


class EpistemicSplit(BaseModel):
    """Разделение наблюдения (измерения), вывода (вычисления) и допущения (интерпретации)."""

    observation: str = Field(..., description="Прямое наблюдение / измерение (каротаж, керн, опыт)")
    inference: str = Field(..., description="Математический или логический вывод / вычисление")
    assumption: str = Field(..., description="Допущение модели и границы применимости")


class NotApplicableField(BaseModel):
    """Явная фиксация статуса и причины неприменимости поля узла Т3."""

    field_name: str
    status: Literal["not_applicable", "pending_expert_check"] = "not_applicable"
    reason: str


class TypedNodeLink(BaseModel):
    """Типизированная связь между узлами учебного слоя."""

    source_node_id: str
    target_node_id: str
    link_type: Literal[
        "prerequisite",
        "example",
        "refutes_misconception",
        "data_transfer",
        "mechanism_to_practice",
        "contrast",
        "generalization",
    ]
    link_label_ru: str = Field(
        default="",
        description="Каноническая подпись связи: предпосылка / пример / опровергает заблуждение / переход к данным",
    )
    rationale: str


class InefficiencyLens(BaseModel):
    """Линза неэффективности процесса специалиста: входы, ручные шаги, точки суждения, время, ошибки."""

    inputs: list[str] = Field(default_factory=list)
    manual_steps: list[str] = Field(default_factory=list)
    expert_judgment_points: list[str] = Field(default_factory=list)
    estimated_time_min: int = Field(default=15, ge=1)
    typical_errors: list[str] = Field(default_factory=list)
    origin_tag: Literal["real_data", "simulation", "author_number", "computed", "model_generated"] = "author_number"


class TextbookProblem(BaseModel):
    """Отдельная задача из текста главы учебника с привязкой к странице и рисунку."""

    problem_id: str
    problem_number: str
    prompt: str
    pdf_page: int
    printed_page: str
    figure_ref: str | None = None
    unit_id: str = ""


class CoreTerm(BaseModel):
    """Опорный термин с определением при первом употреблении и мостом СНГ ↔ Запад."""

    term: str
    definition: str
    first_introduced_pdf_page: int
    first_introduced_printed_page: str
    cis_symbol: str = "—"
    west_symbol: str = "—"
    west_term: str = ""
    unit: str = ""


class WorkedExampleSpec(BaseModel):
    """Структура авторского разобранного примера или задачи из главы."""

    status: Literal["present", "not_applicable"] = "present"
    not_applicable_reason: str = ""
    problem_number: str = ""
    figure_ref: str = ""
    pdf_page: int = 1
    printed_page: str = "1"
    conditions: str = ""
    steps: list[str] = Field(default_factory=list)
    result: str = ""


class ModernEquivalent(BaseModel):
    """Связь исторического прибора/методики с современным аналогом."""

    historical_item: str
    historical_context: str
    modern_analog: str
    modern_context: str
    pdf_page: int


class QuoteAndPage(BaseModel):
    """Точная цитата из источника с разделением цитаты и редакторского пересказа."""

    unit_id: str
    pdf_page: int
    printed_page: str
    verbatim_quote: str
    editorial_paraphrase: str
    numbers_and_units: list[dict[str, str]] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)


class KnowledgeClaim(BaseModel):
    """Проверяемое утверждение учебного слоя, привязанное к единице реестра и доказательству."""

    claim_id: str
    node_id: str
    unit_id: str
    pdf_page: int
    printed_page: str
    verbatim_quote: str
    claim_text: str
    epistemic_role: Literal["observation", "calculation", "assumption", "interpretation"] = "observation"
    origin_tag: Literal["real_data", "simulation", "author_number", "computed", "model_generated"] = "author_number"
    conditions: list[str] = Field(default_factory=list)
    numbers_and_units: list[dict[str, str]] = Field(default_factory=list)
    computed_values: list[ComputedValueProvenance] = Field(default_factory=list)
    requires_expert_check: bool = False
    expert_check_reason: str = ""


class KnowledgeNode(BaseModel):
    """Полная структура узла учебного слоя по Т3."""

    node_id: str
    chapter_id: str
    order: int
    order_rationale: str = Field(..., description="Обоснование порядка узла в маршруте главы")
    source_heading: str = Field(..., description="Заголовок раздела/параграфа в источнике")
    step_title: str = Field(..., description="Самостоятельный заголовок шага в 3–7 слов")
    summary_2_3_sentences: str = Field(..., description="Суть шага в 2–3 фразах")
    primary_difficulty: Literal[
        "conceptual_mechanism",
        "spatial_3d_geometry",
        "multi_curve_reading",
        "mathematical_derivation",
        "unit_and_scale_conversion",
        "procedural_decision",
        "terminology_bridge",
    ]
    secondary_difficulty: Literal[
        "conceptual_mechanism",
        "spatial_3d_geometry",
        "multi_curve_reading",
        "mathematical_derivation",
        "unit_and_scale_conversion",
        "procedural_decision",
        "terminology_bridge",
    ]
    primary_difficulty_code: Literal["М", "В", "И", "Ф", "П", "Пр", "Н", "Р"] = Field(
        default="М",
        description="Официальный код трудности Т3: М, В, И, Ф, П, Пр, Н, Р",
    )
    secondary_difficulty_code: Literal["М", "В", "И", "Ф", "П", "Пр", "Н", "Р"] = Field(
        default="П",
        description="Вторичный код трудности Т3",
    )
    estimated_minutes: int = Field(default=8, ge=2, le=45)
    mechanism: str = Field(..., description="Физический или геологический механизм")
    practice: str = Field(..., description="Практическое применение в работе специалиста")
    nuances: str = Field(..., description="Нюансы, граничные условия и ограничения")
    deeper_branch: str = Field(..., description="Ветка «Глубже» для продвинутого разбора")
    quotes_and_pages: list[QuoteAndPage] = Field(default_factory=list)
    epistemic_split: EpistemicSplit
    field_provenance: dict[str, str] = Field(
        default_factory=dict,
        description="Происхождение каждого поля узла (source_verbatim, editorial_synthesis, physics_engine, passport_bridge)",
    )
    typed_links: list[TypedNodeLink] = Field(default_factory=list)
    core_terms: list[CoreTerm] = Field(default_factory=list)
    threshold_concept: str = Field(..., description="Пороговая идея, меняющая понимание темы")
    misconception_to_fix: str = Field(..., description="Исправляемое типичное заблуждение")
    data_transfer: str = Field(..., description="Перенос в данные: как идея выглядит на диаграммах/в керне/таблицах")
    it_analogy_and_limits: str = Field(..., description="ИТ-аналогия для новичка и точные границы её применимости")
    specialist_manual_steps: list[str] = Field(default_factory=list, description="Ручные шаги специалиста")
    decision_points: list[str] = Field(default_factory=list, description="Точки принятия решения специалистом")
    inefficiency_lens: InefficiencyLens | None = None
    worked_example: WorkedExampleSpec
    textbook_problems: list[TextbookProblem] = Field(default_factory=list)
    modern_equivalents: list[ModernEquivalent] = Field(default_factory=list)
    not_applicable_fields: list[NotApplicableField] = Field(default_factory=list)
    expert_review_flags: list[str] = Field(default_factory=list)
    covered_unit_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    computed_values: list[ComputedValueProvenance] = Field(default_factory=list)


class StudyLayer(BaseModel):
    """Единый учебный слой главы — единственный источник истины для HTML, заданий, графиков и роликов."""

    layer_id: str
    schema_version: str = "lithos.t3.layer.v2"
    book_id: str
    book_file: str
    pdf_file: str
    source_sha256: str
    book_title: str
    authors: list[str] = Field(default_factory=list)
    chapter_id: str
    chapter_title: str
    is_training: bool = True
    pdf_ranges: list[PdfPageRange] = Field(default_factory=list)
    nodes: list[KnowledgeNode] = Field(default_factory=list)
    claims: list[KnowledgeClaim] = Field(default_factory=list)
    coverage_map: dict[str, str] = Field(
        default_factory=dict,
        description="Сопоставление unit_id -> node_id или 'EXCLUDED:<reason>'",
    )
    excluded_units: dict[str, str] = Field(default_factory=dict)
    ocr_corrections: list[OCRCorrectionEntry] = Field(default_factory=list)
    pedagogical_checks: dict[str, Any] = Field(default_factory=dict)


class RegistryDiscrepancy(BaseModel):
    """Несоответствие при двусторонней сверке независимого реестра и учебного слоя."""

    discrepancy_id: str
    discrepancy_type: Literal[
        "missing_unit",
        "duplicate_unit",
        "extra_unit",
        "wrong_page",
        "quote_modified",
        "wrong_number",
        "wrong_unit",
        "condition_lost",
        "empty_coverage",
        "out_of_range_gap",
    ]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "INFO"]
    unit_id: str
    node_id: str | None = None
    pdf_page: int
    printed_page: str = ""
    message: str
    expected_from_registry: str = ""
    found_in_layer: str = ""


class RegistryVerificationReport(BaseModel):
    """Отчёт двусторонней сверки «Независимый реестр ↔ Учебный слой»."""

    passed: bool
    registry_id: str
    layer_id: str
    book_file: str
    pdf_ranges: list[PdfPageRange] = Field(default_factory=list)
    total_registry_units: int
    covered_units_count: int
    excluded_units_count: int
    manual_verification_required_count: int
    discrepancies: list[RegistryDiscrepancy] = Field(default_factory=list)
    manual_verification_items: list[dict[str, Any]] = Field(default_factory=list)
    summary_by_type: dict[str, int] = Field(default_factory=dict)


class IllustrationSpec(BaseModel):
    """Паспорт предметной иллюстрации или анимации на шаге курса (классы A–D)."""

    illustration_id: str
    node_id: str
    step_id: str
    title: str
    visual_class: Literal["A", "B", "C", "D"] = Field(
        ...,
        description="A: расчётная физическая модель/анимация, B: параметрический график/разрез по данным, C: кодовая перерисовка по скану учебника, D: структурная/табличная схема",
    )
    format_kind: Literal["interactive_svg", "animated_svg", "redraw_svg", "video_clip"] = "redraw_svg"
    source_ref: str = Field(..., description="Привязка к источнику: рис. N, стр. M или расчётный датасет")
    redraw_caption: str = Field(..., description="Подпись под изображением, например: «перерисовано по рис. 10.1, стр. 201»")
    pdf_page: int
    printed_page: str
    claim_id: str
    asset_rel_path: str
    svg_markup: str = ""
    legend_items: list[dict[str, str]] = Field(default_factory=list)
    scale_and_units: str = ""
    provenance_note: str = ""


class NodeRoutingEntry(BaseModel):
    """Запись маршрутизации узла по признакам видеоёмкости."""

    node_id: str
    step_id: str
    step_title: str
    video_capacity_score: int = Field(..., ge=0, le=10)
    video_capacity_features: list[str] = Field(default_factory=list)
    selected_format: Literal[
        "video_16_9_and_interactive",
        "shorts_9_16_and_interactive",
        "interactive_domain_animation",
        "code_redraw_figure",
        "structured_diagram_table",
    ]
    routing_rationale: str
    visual_class: Literal["A", "B", "C", "D"]
    template_id: str
    model_state: Literal["deterministic_physics", "parametric_geology", "scan_code_redraw", "nomogram_methodology_only"]
    coverage_status: Literal["covered", "needs_model"] = "covered"
    artifact_path: str = ""
    missing_requirement: str = ""
    illustration_id: str = ""
    source_ref: str = ""


class RoutingReport(BaseModel):
    """Отчёт маршрутизации главы и таблица соответствия «шаг → иллюстрация → источник»."""

    course_id: str
    chapter_id: str
    book_file: str
    domain_package_id: str = "oil_gas_ru"
    total_steps: int
    covered_steps: int
    needs_model_steps: int
    class_a_b_count: int
    hook_shorts_share_pct: float = 0.0
    video_heavy_template_coverage: list[dict[str, str]] = Field(default_factory=list)
    entries: list[NodeRoutingEntry] = Field(default_factory=list)
    step_illustration_source_links: list[dict[str, str]] = Field(default_factory=list)


class StudyTask(BaseModel):
    """Учебное задание Т3 (поддерживает 5 официальных типов Т3 + прикладные кейсы)."""

    task_id: str
    course_id: str
    node_id: str
    step_id: str
    claim_id: str
    pdf_page: int
    printed_page: str
    task_type: Literal[
        "single_choice",
        "multi_select",
        "ordering",
        "fill_in_blank",
        "calculation",
        "matching",
        "case_decision",
    ]
    difficulty_level: Literal["базовый", "инженерный", "продвинутый"] = "инженерный"
    prompt: str
    case_observation: str = Field(default="", description="Наблюдения/данные для задачи «признаки → правило → вывод»")
    case_rule: str = Field(default="", description="Правило/критерий для задачи на решение по данным")
    case_conclusion: str = Field(default="", description="Вывод для задачи на решение по данным")
    options: list[str] = Field(default_factory=list)
    ordering_items: list[str] = Field(default_factory=list)
    matching_pairs: list[dict[str, str]] = Field(default_factory=list)
    blank_acceptable_answers: list[str] = Field(default_factory=list)
    calculation_unit: str = ""
    calculation_tolerance: float = 0.05
    correct_answer: Any = Field(..., description="Ключ правильного ответа (индекс, список, словарь, строка или число)")
    answer_key_display: str = Field(..., description="Читаемый ключ ответа")
    explanation: str = Field(..., description="Короткое понятное объяснение после ответа")
    error_analysis: dict[str, str] = Field(default_factory=dict, description="Разбор типичных ошибок по вариантам")
    hint_steps: list[str] = Field(default_factory=list, description="Локальные ступенчатые подсказки (без сети)")
    source_ref: str = Field(..., description="Точная ссылка на источник и страницу")
    verbatim_quote: str = ""


class FlashcardItem(BaseModel):
    """Содержательная карточка для режимов «Знаю» / «Повторить»."""

    card_id: str
    node_id: str
    step_id: str
    front_question: str
    back_answer: str
    term_or_formula: str
    pdf_page: int
    printed_page: str
    source_ref: str


class StudyStepScreen(BaseModel):
    """Экран шага курса, доведённый до структуры Т3."""

    step_id: str
    node_id: str
    order: int
    estimated_minutes: int = 8
    difficulty_codes: list[str] = Field(default_factory=list)
    source_heading: str
    step_title: str = Field(..., description="Самостоятельный заголовок в 3–7 слов")
    summary_2_3_sentences: str
    explanation_paragraphs: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Абзацы объяснения с обязательной ссылкой на страницу и unit_id",
    )
    first_use_terms: list[CoreTerm] = Field(default_factory=list)
    formulas_decoded: list[dict[str, Any]] = Field(default_factory=list)
    applicability_conditions: list[str] = Field(default_factory=list)
    worked_example: WorkedExampleSpec
    textbook_problems: list[TextbookProblem] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    modern_context: list[ModernEquivalent] = Field(default_factory=list)
    it_analogy_and_limits: str
    typical_error: str
    epistemic_split: EpistemicSplit
    specialist_manual_steps: list[str] = Field(default_factory=list)
    decision_points: list[str] = Field(default_factory=list)
    inefficiency_lens: InefficiencyLens | None = None
    deeper_branch: str
    illustration: IllustrationSpec
    video_url: str | None = None
    video_aspect: str | None = None
    media_passport_id: str | None = None
    ocr_corrections_applied: list[OCRCorrectionEntry] = Field(default_factory=list)
    practicum: dict[str, Any] | None = None


class SceneSpec(BaseModel):
    """Предрендерная машиночитаемая спецификация сцены (сохраняется в scene_specs/*.json до рендера)."""

    scene_id: str
    node_id: str
    claim_id: str
    format_kind: Literal["shorts_9_16", "explainer_16_9", "interactive_svg"] = "explainer_16_9"
    frame_class: Literal["A", "B", "C", "D"] = "A"
    origin_label: Literal["real_data", "simulation", "author_number", "computed", "model_generated"] = "simulation"
    objects: list[str] = Field(default_factory=list)
    state_model: str
    initial_conditions: dict[str, Any] = Field(default_factory=dict)
    parameters_and_units: dict[str, str] = Field(default_factory=dict)
    invariants: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    scales: dict[str, Any] = Field(default_factory=dict)
    synchronized_views: list[str] = Field(default_factory=list)
    source: dict[str, Any] = Field(default_factory=dict)


class WordTimecode(BaseModel):
    """Словесный таймкод закадровой речи."""

    word: str
    normalized_pronunciation: str
    start_sec: float
    end_sec: float
    sync_drift_sec: float = 0.0


class AudioQualityReport(BaseModel):
    """Аудиометрики ролика: громкость LUFS, пик, темп речи, словарь произношений и статус WER."""

    voice_id: str
    synthesis_mode: Literal["edge_tts_neural", "offline_formant_synthesizer"]
    duration_sec: float
    integrated_lufs: float
    true_peak_dbfs: float
    clipping_detected: bool = False
    speech_rate_wpm: float
    pronunciation_replacements_applied: list[dict[str, str]] = Field(default_factory=list)
    controversial_terms_report: list[dict[str, str]] = Field(default_factory=list)
    word_timecodes: list[WordTimecode] = Field(default_factory=list)
    asr_model_available: bool = False
    measured_wer_pct: float | None = None
    max_word_desync_sec: float = 0.0
    asr_verification_status: str = "проверка ожидается"


class PhysicsInvariantItem(BaseModel):
    """Пункт чек-листа физики Т3."""

    invariant_id: str
    category: Literal[
        "scale_and_exaggeration",
        "mass_balance",
        "fluid_flow_direction",
        "axis_orientation",
        "view_consistency",
        "instrument_physics",
        "misconception_guard",
    ]
    title: str
    automated_check_passed: bool
    measured_value: str
    expected_invariant: str
    expert_confirmation_status: Literal["confirmed_by_source_law", "requires_expert_signoff"] = "confirmed_by_source_law"
    expert_note: str = ""


class VideoScenePassport(BaseModel):
    """Посценная привязка фактов и фраз закадра к утверждению слоя, странице и датасету."""

    scene_id: str
    order: int
    start_sec: float
    end_sec: float
    title: str
    narration_text: str
    claim_id: str
    node_id: str
    unit_id: str
    pdf_page: int
    printed_page: str
    dataset_or_model: str
    parameters_and_units: dict[str, str] = Field(default_factory=dict)
    invariants_checked: list[str] = Field(default_factory=list)
    frame_origin: Literal["class_A_simulation", "class_B_data_plot", "class_C_scan_redraw"] = "class_A_simulation"
    epistemic_badges_in_frame: list[Literal["Измерение", "Вычисление", "Допущение", "Интерпретация"]] = Field(
        default_factory=list
    )
    true_scale_shown: bool = False
    vertical_exaggeration_factor: float = 1.0
    pedagogical_element: str = ""


class MediaPassport(BaseModel):
    """Полный паспорт ролика (9:16 шортс или 16:9 разбор) по Этапу 3 Т3."""

    passport_id: str
    course_id: str
    chapter_id: str
    book_file: str
    format_kind: Literal["shorts_9_16", "explainer_16_9"]
    aspect_ratio: Literal["9:16", "16:9"]
    resolution: Literal["1080x1920", "1920x1080"]
    fps: int = 30
    duration_sec: float
    video_rel_path: str
    srt_rel_path: str
    audio_rel_path: str
    scene_spec_rel_path: str = ""
    file_size_bytes: int
    hook_question_0_3s: str
    prediction_pause_sec: float = Field(..., ge=1.0, le=1.8)
    prediction_pause_window: str
    transfer_question_end: str
    counterexample_included: str
    historical_to_modern_bridge: str
    true_scale_frame_timecode: str
    vertical_exaggeration_label: str
    unified_legend: list[dict[str, str]] = Field(default_factory=list)
    scenes: list[VideoScenePassport] = Field(default_factory=list)
    audio_report: AudioQualityReport
    physics_checklist: list[PhysicsInvariantItem] = Field(default_factory=list)
    source_layer_hash: str = ""


class VerifierFinding(BaseModel):
    """Замечание верификатора внешних «закладок» (Этап 4 Т3)."""

    finding_id: str
    verdict: Literal["confirmed_violation", "warning", "insufficient_evidence"] = "confirmed_violation"
    defect_type: Literal[
        "condition_loss",
        "polarity_flip",
        "number_mismatch",
        "unit_mismatch",
        "wrong_mechanism",
        "wrong_scale",
        "outdated_claim",
        "fabricated_nomogram",
        "page_citation_mismatch",
        "expert_ambiguity",
    ]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "EXPERT_REVIEW"]
    target_object: str = Field(..., description="ID утверждения, сценария, спецификации или кадра")
    problematic_fragment: str = Field(default="", description="Конкретный проблемный фрагмент текста или параметра")
    explanation: str = Field(default="", description="Предметное объяснение, почему фрагмент ошибочен")
    proposed_fix: str = Field(..., description="Конкретное исправление по источнику")
    pdf_page: int
    printed_page: str
    supporting_quote: str = Field(default="", description="Подтверждающая подлинная цитата из источника")
    rationale: str = Field(..., description="Основание и подлинная цитата из реестра источника")


class BookmarkVerificationReport(BaseModel):
    """Отчёт проверки утверждений, сценариев, спецификаций и кадров на «закладки»."""

    passed: bool
    evaluation_mode: Literal["internal_calibration", "official_bookmark_package"] = "internal_calibration"
    book_file: str
    total_checked_objects: int
    findings: list[VerifierFinding] = Field(default_factory=list)
    expert_review_queue: list[VerifierFinding] = Field(default_factory=list)
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    counts_by_verdict: dict[str, int] = Field(default_factory=dict)


class StudyCoursePackage(BaseModel):
    """Полный собранный пакет курса Т3 для одной главы."""

    course_id: str
    schema_version: str = "lithos.t3.package.v2"
    domain_package_id: str = "oil_gas_ru"
    book_id: str
    book_file: str
    pdf_file: str
    book_title: str
    authors: list[str] = Field(default_factory=list)
    chapter_id: str
    chapter_title: str
    is_training: bool = True
    pdf_ranges: list[PdfPageRange] = Field(default_factory=list)
    layer: StudyLayer
    registry_report: RegistryVerificationReport
    routing_report: RoutingReport
    scene_specs: list[SceneSpec] = Field(default_factory=list)
    steps: list[StudyStepScreen] = Field(default_factory=list)
    tasks: list[StudyTask] = Field(default_factory=list)
    flashcards: list[FlashcardItem] = Field(default_factory=list)
    summary_notes_markdown: str = ""
    media_passports: list[MediaPassport] = Field(default_factory=list)
    bookmark_report: BookmarkVerificationReport
    practicum: dict[str, Any] | None = None
    offline_html_url: str = ""
    offline_zip_url: str = ""
    offline_package_size_mb: float = 0.0
