"""
FastAPI роутер Т3 «Глава → курс» (backend/study_api.py).
Подключается к штатной точке входа backend/main.py без нарушения существующих API-контрактов.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.t3.bookmarks_verifier import run_internal_calibration_benchmark
from backend.t3.models import StudyCoursePackage
from backend.t3.pipeline import (
    build_all_six_t3_courses,
    build_t3_course_package,
    rebuild_t3_from_layer_fact_edit,
)
from backend.t3.registry import BOOK_CATALOG
from backend.t3.tasks_engine import (
    check_task_submission,
    select_hint_strategy_and_render_locally,
)

router = APIRouter(prefix="/api/t3", tags=["t3"])


class TaskCheckRequest(BaseModel):
    task_id: str
    answer: Any


class HintRequest(BaseModel):
    task_id: str
    attempt_number: int = 1
    hint_level: int = 1
    allow_online_openai: bool = False


class FactRebuildRequest(BaseModel):
    course_id: str
    claim_id: str = ""
    old_fact: str
    new_fact: str
    render_mp4: bool = False


def _get_dirs() -> tuple[Path, Path]:
    from backend.main import DATA_DIR, OUTPUT_DIR

    return DATA_DIR, OUTPUT_DIR


def _load_or_build_t3_package(course_id: str) -> StudyCoursePackage:
    data_dir, output_dir = _get_dirs()
    pkg_file = output_dir / course_id / "t3_course_package.json"
    if pkg_file.exists():
        return StudyCoursePackage.model_validate_json(pkg_file.read_text(encoding="utf-8"))

    # Определяем книгу по course_id (например, t3_train_kuznetsov -> train_kuznetsov.md)
    stem = course_id.removeprefix("t3_")
    book_file = f"{stem}.md"
    if book_file not in BOOK_CATALOG:
        candidate = data_dir / "books" / book_file
        if not candidate.exists():
            raise HTTPException(status_code=404, detail=f"Курс Т3 '{course_id}' не найден.")
    return build_t3_course_package(
        data_dir=data_dir,
        output_dir=output_dir,
        book_file=book_file,
        course_id_override=course_id,
        render_mp4=False,
    )


@router.get("/courses")
def list_t3_courses() -> list[dict[str, Any]]:
    data_dir, output_dir = _get_dirs()
    summaries: list[dict[str, Any]] = []
    for bf in BOOK_CATALOG:
        cid = f"t3_{BOOK_CATALOG[bf]['book_id']}"
        pkg = _load_or_build_t3_package(cid)
        summaries.append(
            {
                "course_id": pkg.course_id,
                "book_file": pkg.book_file,
                "pdf_file": pkg.pdf_file,
                "book_title": pkg.book_title,
                "chapter_title": pkg.chapter_title,
                "is_training": pkg.is_training,
                "steps_count": len(pkg.steps),
                "tasks_count": len(pkg.tasks),
                "flashcards_count": len(pkg.flashcards),
                "registry_passed": pkg.registry_report.passed,
                "registry_units_total": pkg.registry_report.total_registry_units,
                "needs_model_steps": pkg.routing_report.needs_model_steps,
                "offline_html_url": pkg.offline_html_url,
                "offline_zip_url": pkg.offline_zip_url,
                "offline_package_size_mb": pkg.offline_package_size_mb,
                "media_passports_count": len(pkg.media_passports),
            }
        )
    return summaries


@router.get("/courses/{course_id}", response_model=StudyCoursePackage)
def get_t3_course(course_id: str) -> StudyCoursePackage:
    return _load_or_build_t3_package(course_id)


@router.get("/courses/{course_id}/registry")
def get_t3_course_registry(course_id: str) -> dict[str, Any]:
    data_dir, output_dir = _get_dirs()
    pkg = _load_or_build_t3_package(course_id)
    reg_path = output_dir / course_id / "independent_registry.json"
    reg_data = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.exists() else {}
    return {
        "course_id": course_id,
        "verification_report": json.loads(pkg.registry_report.model_dump_json()),
        "independent_registry": reg_data,
    }


@router.get("/courses/{course_id}/routing")
def get_t3_course_routing(course_id: str) -> dict[str, Any]:
    pkg = _load_or_build_t3_package(course_id)
    return json.loads(pkg.routing_report.model_dump_json())


@router.post("/courses/{course_id}/check-task")
def check_t3_task(course_id: str, req: TaskCheckRequest) -> dict[str, Any]:
    pkg = _load_or_build_t3_package(course_id)
    task = next((t for t in pkg.tasks if t.task_id == req.task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Задание '{req.task_id}' не найдено в курсе '{course_id}'.")
    return check_task_submission(task, req.answer)


@router.post("/courses/{course_id}/hint")
def get_t3_task_hint(course_id: str, req: HintRequest) -> dict[str, Any]:
    pkg = _load_or_build_t3_package(course_id)
    task = next((t for t in pkg.tasks if t.task_id == req.task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Задание '{req.task_id}' не найдено.")
    node = next((n for n in pkg.layer.nodes if n.node_id == task.node_id), pkg.layer.nodes[0])
    return select_hint_strategy_and_render_locally(
        task=task,
        node=node,
        attempt_number=req.attempt_number,
        hint_level=req.hint_level,
        allow_online_openai=req.allow_online_openai,
    )


@router.post("/rebuild-fact")
def api_rebuild_from_fact(req: FactRebuildRequest) -> dict[str, Any]:
    _, output_dir = _get_dirs()
    pkg = _load_or_build_t3_package(req.course_id)
    cid = req.claim_id or pkg.layer.claims[0].claim_id
    res = rebuild_t3_from_layer_fact_edit(
        package=pkg,
        course_dir=output_dir / pkg.course_id,
        claim_id=cid,
        old_fact_substring=req.old_fact,
        new_fact_substring=req.new_fact,
        render_mp4=req.render_mp4,
    )
    return {k: v for k, v in res.items() if k != "updated_package"}


@router.get("/calibration")
def get_t3_calibration() -> dict[str, Any]:
    data_dir, _ = _get_dirs()
    return run_internal_calibration_benchmark(data_dir)


@router.get("/freeze-report")
def get_t3_freeze_report() -> dict[str, Any]:
    data_dir, output_dir = _get_dirs()
    report_path = output_dir / "t3_freeze_report.json"
    if not report_path.exists():
        res = build_all_six_t3_courses(data_dir=data_dir, output_dir=output_dir, render_mp4=False)
        return res["freeze_report"]
    return json.loads(report_path.read_text(encoding="utf-8"))


@router.get("/courses/{course_id}/download")
def download_t3_offline_zip(course_id: str) -> FileResponse:
    _, output_dir = _get_dirs()
    pkg = _load_or_build_t3_package(course_id)
    zip_path = output_dir / pkg.course_id / f"{pkg.course_id}_offline.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP-архив автономного курса не найден.")
    return FileResponse(path=str(zip_path), filename=zip_path.name, media_type="application/zip")
