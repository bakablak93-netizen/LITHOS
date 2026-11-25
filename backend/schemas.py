from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class TermBridge(BaseModel):
    """Пара терминов: советская/СНГ нотация и западный эквивалент."""

    ru_symbol: str = Field(..., description="Обозначение в учебнике (например, К_п, ρ_п, κ)")
    ru_term: str = Field(..., description="Русскоязычный термин")
    en_symbol: str = Field(..., description="Западный символ (например, φ, R_t, η)")
    en_term: str = Field(..., description="Английский эквивалент")
    unit: str = Field(default="", description="Единицы измерения в учебнике (мД, Ом·м, %)")
    note: str = Field(default="", description="Краткое примечание о различиях школ")


class FormulaSpec(BaseModel):
    """Детерминированная формула для рендера в Manim и Remotion."""

    latex: str = Field(..., description="LaTeX-запись формулы в нотации учебника")
    title: str = Field(..., description="Название уравнения")
    western_latex: str = Field(default="", description="Эквивалент в западной нотации")
    variables: dict[str, str] = Field(default_factory=dict, description="Расшифровка переменных")
    source_ref: str = Field(default="", description="Ссылка на главу/формулу учебника")


class SubtitleCue(BaseModel):
    """Сегмент субтитров с точными таймкодами от TTS."""

    index: int
    start_sec: float
    end_sec: float
    text: str


class SceneSpec(BaseModel):
    """Одна сцена курса в Scene Graph (100% детерминированная графика)."""

    scene_id: str
    order: int
    title: str
    narration: str = Field(..., description="Текст русской озвучки для TTS")
    duration_sec: float = Field(default=10.0, ge=2.0)
    fps: int = Field(default=30)
    visual_backend: Literal["manim", "threejs_lab", "remotion_split", "remotion_formula"] = "manim"
    manim_scene_class: str = Field(default="", description="Имя класса Manim при visual_backend=manim")
    manim_video_path: str | None = Field(default=None, description="Относительный URL отрендеренного Manim MP4")
    audio_path: str | None = Field(default=None, description="Относительный URL MP3-озвучки")
    subtitles: list[SubtitleCue] = Field(default_factory=list)
    formulas: list[FormulaSpec] = Field(default_factory=list)
    term_bridges: list[TermBridge] = Field(default_factory=list)
    lab_preset: dict[str, Any] = Field(default_factory=dict, description="Параметры для 3D-лаборатории")
    key_takeaways: list[str] = Field(default_factory=list)
    methodology_only_nomogram: bool = Field(
        default=False,
        description="True если сцена затрагивает неоцифрованную палетку (только методика считывания, без выдуманных чисел)",
    )


class QACheck(BaseModel):
    """Отдельная проверка Domain QA по JSON-паспорту учебника."""

    check_id: str
    category: Literal[
        "quantitative_safety",
        "school_notation",
        "reservoir_type",
        "deterministic_visuals",
        "nomogram_guard",
    ]
    status: Literal["PASS", "WARN", "FIXED", "FAIL"]
    message: str
    affected_scenes: list[str] = Field(default_factory=list)


class QAReport(BaseModel):
    """Итоговый отчёт Domain QA Verifier."""

    passed: bool
    checks: list[QACheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    auto_fixes: list[str] = Field(default_factory=list)
    passport_warnings_applied: dict[str, str] = Field(default_factory=dict)


class CourseManifest(BaseModel):
    """Главный контракт course_manifest.json, связывающий Backend, Physics, Manim, Remotion и Web UI."""

    course_id: str
    module_type: Literal["latyshova_gis", "basniev_hydro", "generic_chapter"]
    book_file: str
    passport_file: str | None = None
    book_title: str
    authors: list[str] = Field(default_factory=list)
    chapter_title: str
    chapter_number: str = ""
    methodological_school: str = "soviet_cis"
    units_system: str = "soviet_practice"
    total_duration_sec: float = 0.0
    fps: int = 30
    resolution: str = "1920x1080"
    voice: str = "ru-RU-DmitryNeural"
    final_video_url: str | None = None
    srt_url: str | None = None
    scenes: list[SceneSpec] = Field(default_factory=list)
    physics_data: dict[str, Any] = Field(default_factory=dict)
    qa_report: QAReport


class ChapterInfo(BaseModel):
    index: int
    title: str
    start_line: int
    end_line: int
    char_count: int
    has_nomograms: bool = False
    formula_count: int = 0


class BookInfo(BaseModel):
    book_file: str
    passport_file: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    domain: str = ""
    school: str = "soviet_cis"
    is_control: bool = False
    recommended_module: Literal["latyshova_gis", "basniev_hydro", "generic_chapter"] = "generic_chapter"
    chapters: list[ChapterInfo] = Field(default_factory=list)


class CourseBuildRequest(BaseModel):
    book_file: str
    passport_file: str | None = None
    chapter_index: int = 0
    module_override: Literal["auto", "latyshova_gis", "basniev_hydro", "generic_chapter"] = "auto"
    voice: Literal["ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"] = "ru-RU-DmitryNeural"
    render_video: bool = True
    use_llm: bool = True


class CourseJobStatus(BaseModel):
    job_id: str
    course_id: str
    status: Literal["queued", "running", "completed", "failed"]
    stage: str
    progress_pct: int = Field(ge=0, le=100)
    logs: list[str] = Field(default_factory=list)
    manifest_url: str | None = None
    video_url: str | None = None
    error: str | None = None
