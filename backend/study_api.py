"""
FastAPI роутер Т3 «Глава → курс» (backend/study_api.py).
Подключается к штатной точке входа backend/main.py без нарушения существующих API-контрактов.
"""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.t3.bookmarks_verifier import run_internal_calibration_benchmark
from backend.t3.custom_book import BookExtractError, build_custom_course_package, extract_book_pages
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
    render_mp4: bool = True


def _get_dirs() -> tuple[Path, Path]:
    from backend.main import DATA_DIR, OUTPUT_DIR

    return DATA_DIR, OUTPUT_DIR


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _load_or_build_t3_package(course_id: str) -> StudyCoursePackage:
    data_dir, output_dir = _get_dirs()
    pkg_file = output_dir / course_id / "t3_course_package.json"
    if pkg_file.exists():
        pkg = StudyCoursePackage.model_validate_json(pkg_file.read_text(encoding="utf-8"))
        missing_mp4 = any(
            mp.video_rel_path
            and not (output_dir / course_id / "media" / Path(mp.video_rel_path).name).exists()
            for mp in pkg.media_passports
        )
        if not (missing_mp4 and _has_ffmpeg()):
            return pkg

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
        render_mp4=_has_ffmpeg(),
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
                "is_custom": False,
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
    # Добавляем пользовательские курсы (custom_*), созданные через мастер загрузки
    for pkg_file in sorted(output_dir.glob("custom_*/t3_course_package.json"), reverse=True):
        try:
            pkg = StudyCoursePackage.model_validate_json(pkg_file.read_text(encoding="utf-8"))
            summaries.insert(
                0,
                {
                    "course_id": pkg.course_id,
                    "book_file": pkg.book_file,
                    "pdf_file": pkg.pdf_file,
                    "book_title": pkg.book_title,
                    "chapter_title": pkg.chapter_title,
                    "is_training": False,
                    "is_custom": True,
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
                },
            )
        except Exception:
            continue
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
        res = build_all_six_t3_courses(data_dir=data_dir, output_dir=output_dir, render_mp4=_has_ffmpeg())
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


# ------------------------------------------------------------------
# Реальный мастер «Своя книга → Глава → Курс» с сохранением статуса
# ------------------------------------------------------------------

_JOBS_LOCK = threading.Lock()


def _jobs_path(output_dir: Path) -> Path:
    return output_dir / "_custom_jobs.json"


def _load_jobs(output_dir: Path) -> dict[str, dict[str, Any]]:
    p = _jobs_path(output_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_job(output_dir: Path, job_id: str, data: dict[str, Any]) -> None:
    with _JOBS_LOCK:
        jobs = _load_jobs(output_dir)
        jobs[job_id] = data
        _jobs_path(output_dir).write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding="utf-8")


class CustomBuildRequest(BaseModel):
    book_id: str = ""
    library_book: str = ""
    chapter_title: str = "Выбранная глава"
    start_page: int = 1
    end_page: int = 10


@router.post("/books/inspect")
async def inspect_book_for_course(
    file: UploadFile | None = File(default=None),
    library_book: str = Form(default=""),
) -> dict[str, Any]:
    """Принимает загруженный .pdf / .md / .txt или библиотечную книгу, возвращает главы и предпросмотр страниц."""
    data_dir, output_dir = _get_dirs()
    upload_dir = output_dir / "_uploaded_books"
    upload_dir.mkdir(parents=True, exist_ok=True)

    if file and file.filename:
        safe_name = Path(file.filename).name
        book_id = f"up_{uuid.uuid4().hex[:10]}"
        raw_path = upload_dir / f"{book_id}_{safe_name}"
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail=f"Файл «{safe_name}» пустой. Выберите непустой файл (.pdf, .md, .txt).")
        raw_path.write_bytes(content)
        try:
            meta = extract_book_pages(raw_path, safe_name)
        except BookExtractError as exc:
            raw_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        meta["book_id"] = book_id
        (upload_dir / f"{book_id}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return {
            "book_id": book_id,
            "file_name": meta["file_name"],
            "format": meta["format"],
            "total_pages": meta["total_pages"],
            "chapters": meta["chapters"],
            "warnings": meta["warnings"],
            "is_library": False,
        }

    if library_book:
        src = data_dir / "books" / Path(library_book).name
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"Книга «{library_book}» не найдена в библиотеке.")
        cat = BOOK_CATALOG.get(src.name)
        book_id = f"lib_{src.stem}"
        try:
            meta = extract_book_pages(src, src.name)
        except BookExtractError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        meta["book_id"] = book_id
        (upload_dir / f"{book_id}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        chapters = meta["chapters"]
        if cat:
            # Ставим штатную главу Т3 первой в списке
            r0 = cat["pdf_ranges"][0]
            chapters = [
                {
                    "index": 0,
                    "title": cat["chapter_title"],
                    "start_page": r0["start_pdf_page"],
                    "end_page": cat["pdf_ranges"][-1]["end_pdf_page"],
                    "preview": f"Штатная глава Т3 ({cat['book_title']}). Диапазон PDF: {r0['start_pdf_page']}–{cat['pdf_ranges'][-1]['end_pdf_page']}.",
                    "is_t3_default": True,
                }
            ] + [dict(ch, index=ch["index"] + 1) for ch in chapters[:12]]
        return {
            "book_id": book_id,
            "library_book": src.name,
            "file_name": src.name,
            "format": "md",
            "total_pages": meta["total_pages"],
            "chapters": chapters,
            "warnings": meta["warnings"],
            "is_library": True,
        }

    raise HTTPException(status_code=400, detail="Передайте файл книги (.pdf, .md, .txt) или выберите книгу из библиотеки.")


@router.post("/books/build-custom")
def start_custom_course_build(req: CustomBuildRequest) -> dict[str, Any]:
    """Запускает реальную сборку курса по выбранной главе/диапазону страниц и сохраняет прогресс на диск."""
    data_dir, output_dir = _get_dirs()
    upload_dir = output_dir / "_uploaded_books"
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()

    job_state: dict[str, Any] = {
        "job_id": job_id,
        "status": "queued",
        "progress_pct": 5,
        "stage": "Подготовка сборки",
        "chapter_title": req.chapter_title,
        "start_page": req.start_page,
        "end_page": req.end_page,
        "course_id": None,
        "error": None,
        "pipeline_used": "T3 (полный конвейер)" if req.library_book and req.library_book in BOOK_CATALOG else "T3 Custom Book (PDF/MD/TXT → слой → задания → ZIP)",
        "created_at": now,
        "updated_at": now,
    }
    _save_job(output_dir, job_id, job_state)

    def _worker() -> None:
        def _upd(pct: int, stage: str) -> None:
            job_state["status"] = "running"
            job_state["progress_pct"] = pct
            job_state["stage"] = stage
            job_state["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_job(output_dir, job_id, job_state)

        try:
            if req.library_book and req.library_book in BOOK_CATALOG:
                _upd(25, "Сверка независимого реестра и построение учебного слоя Т3")
                cid = f"t3_{BOOK_CATALOG[req.library_book]['book_id']}"
                _upd(65, "Загрузка и проверка медиапакета Т3")
                pkg = _load_or_build_t3_package(cid)
            else:
                meta_path = upload_dir / f"{req.book_id}.json"
                if not meta_path.exists():
                    raise BookExtractError("Загруженная книга не найдена. Загрузите файл повторно.")
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                pkg = build_custom_course_package(
                    book_meta=meta,
                    chapter_title=req.chapter_title,
                    start_page=req.start_page,
                    end_page=req.end_page,
                    output_dir=output_dir,
                    progress_cb=_upd,
                )
            job_state["status"] = "completed"
            job_state["progress_pct"] = 100
            job_state["stage"] = "Курс готов"
            job_state["course_id"] = pkg.course_id
            job_state["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_job(output_dir, job_id, job_state)
        except Exception as exc:
            job_state["status"] = "failed"
            job_state["stage"] = "Ошибка сборки"
            job_state["error"] = str(exc)
            job_state["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_job(output_dir, job_id, job_state)

    threading.Thread(target=_worker, daemon=True).start()
    return job_state


@router.get("/jobs/{job_id}")
def get_custom_job(job_id: str) -> dict[str, Any]:
    _, output_dir = _get_dirs()
    jobs = _load_jobs(output_dir)
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Задача сборки '{job_id}' не найдена.")
    return jobs[job_id]


@router.get("/jobs")
def list_custom_jobs() -> list[dict[str, Any]]:
    _, output_dir = _get_dirs()
    jobs = _load_jobs(output_dir)
    return sorted(jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)[:15]

