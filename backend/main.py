"""
FastAPI Backend: загрузка глав/паспортов, оркестрация пайплайна «Глава -> курс»,
живые вычисления физики для 3D Probe Lab / Hydro Lab и отдача артефактов.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.agents.parser_agent import build_course_manifest, discover_books, load_passport
from backend.agents.qa_verifier import verify_course_manifest
from backend.physics_engine import simulate_dupuit_flow, simulate_psss_transient, simulate_well_log
from backend.schemas import BookInfo, CourseBuildRequest, CourseJobStatus, CourseManifest
from backend.tts_engine import generate_course_audio_and_srt
from backend.video_assembler import assemble_final_video, render_manim_scenes

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_raw_data_dir = Path(os.getenv("DATA_DIR", "data"))
_raw_output_dir = Path(os.getenv("OUTPUT_DIR", "outputs"))
DATA_DIR = (_raw_data_dir if _raw_data_dir.is_absolute() else PROJECT_ROOT / _raw_data_dir).resolve()
OUTPUT_DIR = (_raw_output_dir if _raw_output_dir.is_absolute() else PROJECT_ROOT / _raw_output_dir).resolve()
WEB_DIST_DIR = (PROJECT_ROOT / "web_ui" / "dist").resolve()

DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "books").mkdir(parents=True, exist_ok=True)
(DATA_DIR / "passports").mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="LITHOS: Глава → Курс (KMG Digital Hackathon 2026)",
    version="1.0.0",
    description="Детерминированная генерация нефтегазовых видеокурсов и 3D-лабораторий из учебников и JSON-паспортов.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

JOBS: dict[str, CourseJobStatus] = {}


class LatyshovaLabParams(BaseModel):
    rho_v: float = 0.05
    rho_f: float = 1.20
    a_m: float = 0.81
    m: float = 1.95
    a_n: float = 1.0
    n: float = 2.0
    temp_c: float = 65.0
    vnk_depth_m: float = 2425.0
    reservoir_mode: str = "clastic"
    k_pt: float = 0.015


class BasnievLabParams(BaseModel):
    k_md: float = 120.0
    mu_cp: float = 1.8
    h_m: float = 14.0
    p_k_mpa: float = 24.0
    p_c_mpa: float = 16.5
    r_c_m: float = 0.1
    r_k_m: float = 250.0
    porosity_m: float = 0.18
    q_m3_day: float = 180.0
    t_hours: float = 6.0


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "data_dir": str(DATA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "llm_configured": bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_API_KEY") != "PASTE_YOUR_KEY_HERE"),
    }


@app.get("/api/books", response_model=list[BookInfo])
def list_books() -> list[BookInfo]:
    return discover_books(DATA_DIR)


@app.post("/api/upload")
async def upload_book_or_passport(
    book_file: UploadFile | None = File(default=None),
    passport_file: UploadFile | None = File(default=None),
) -> dict[str, Any]:
    saved: dict[str, str] = {}
    if book_file and book_file.filename:
        safe_name = Path(book_file.filename).name
        dest = DATA_DIR / "books" / safe_name
        dest.write_bytes(await book_file.read())
        saved["book_file"] = safe_name
    if passport_file and passport_file.filename:
        safe_name = Path(passport_file.filename).name
        dest = DATA_DIR / "passports" / safe_name
        dest.write_bytes(await passport_file.read())
        saved["passport_file"] = safe_name
    if not saved:
        raise HTTPException(status_code=400, detail="Не переданы файлы книги или паспорта.")
    return {"saved": saved, "books": [b.model_dump() for b in discover_books(DATA_DIR)]}


async def _run_pipeline(job_id: str, req: CourseBuildRequest) -> None:
    job = JOBS[job_id]

    def log(msg: str) -> None:
        job.logs.append(msg)

    try:
        job.status = "running"
        job.stage = "Парсинг главы и расчёт физики"
        job.progress_pct = 15
        log(f"Загрузка {req.book_file} (глава #{req.chapter_index + 1})...")

        manifest = await build_course_manifest(
            data_dir=DATA_DIR,
            book_file=req.book_file,
            passport_file=req.passport_file,
            chapter_index=req.chapter_index,
            module_override=req.module_override,
            voice=req.voice,
            use_llm=req.use_llm,
        )
        job.course_id = manifest.course_id
        course_dir = OUTPUT_DIR / manifest.course_id
        course_dir.mkdir(parents=True, exist_ok=True)
        public_prefix = f"/outputs/{manifest.course_id}"

        # Domain QA Verifier по JSON-паспорту
        job.stage = "Domain QA Verifier (проверка по паспорту)"
        job.progress_pct = 35
        passport_data: dict[str, Any] = {}
        if manifest.passport_file:
            p_path = DATA_DIR / "passports" / manifest.passport_file
            if p_path.exists():
                passport_data = load_passport(p_path)
        manifest.qa_report = verify_course_manifest(manifest, passport_data)
        log(f"Domain QA завершён: {len(manifest.qa_report.checks)} проверок, auto_fixes={len(manifest.qa_report.auto_fixes)}.")

        # TTS + таймкоды
        job.stage = f"Синтез русской речи ({req.voice}) и таймкодов"
        job.progress_pct = 55
        manifest = await generate_course_audio_and_srt(manifest, course_dir, public_prefix)
        log(f"Озвучка готова ({manifest.total_duration_sec} с).")

        # Manim + Remotion/FFmpeg (если запрошен видеорендер)
        if req.render_video:
            job.stage = "Рендер научных сцен Manim"
            job.progress_pct = 75
            manifest = await asyncio.to_thread(
                render_manim_scenes, manifest, PROJECT_ROOT, course_dir, public_prefix, log
            )

            job.stage = "Сборка видео (Remotion + FFmpeg)"
            job.progress_pct = 90
            manifest = await asyncio.to_thread(
                assemble_final_video, manifest, PROJECT_ROOT, course_dir, public_prefix, log
            )
        else:
            manifest_path = course_dir / "course_manifest.json"
            manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        manifest_path = course_dir / "course_manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

        job.manifest_url = f"{public_prefix}/course_manifest.json"
        job.video_url = manifest.final_video_url
        job.stage = "Готово"
        job.progress_pct = 100
        job.status = "completed"
        log(f"Курс {manifest.course_id} успешно сформирован.")
    except Exception as exc:
        job.status = "failed"
        job.stage = "Ошибка"
        job.error = str(exc)
        log(f"Ошибка пайплайна: {exc}")


@app.post("/api/courses/build", response_model=CourseJobStatus)
async def start_course_build(req: CourseBuildRequest) -> CourseJobStatus:
    job_id = uuid.uuid4().hex[:10]
    job = CourseJobStatus(
        job_id=job_id,
        course_id="",
        status="queued",
        stage="Инициализация",
        progress_pct=5,
        logs=["Задача поставлена в очередь."],
    )
    JOBS[job_id] = job
    asyncio.create_task(_run_pipeline(job_id, req))
    return job


@app.get("/api/jobs/{job_id}", response_model=CourseJobStatus)
def get_job_status(job_id: str) -> CourseJobStatus:
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]


@app.get("/api/courses", response_model=list[CourseManifest])
def list_courses() -> list[CourseManifest]:
    items: list[CourseManifest] = []
    for manifest_file in sorted(OUTPUT_DIR.glob("*/course_manifest.json"), reverse=True):
        try:
            items.append(CourseManifest.model_validate_json(manifest_file.read_text(encoding="utf-8")))
        except Exception:
            pass
    return items


@app.get("/api/courses/{course_id}", response_model=CourseManifest)
def get_course(course_id: str) -> CourseManifest:
    manifest_file = OUTPUT_DIR / course_id / "course_manifest.json"
    if not manifest_file.exists():
        raise HTTPException(status_code=404, detail="Course manifest not found")
    return CourseManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))


@app.post("/api/physics/latyshova")
def compute_latyshova_physics(params: LatyshovaLabParams) -> dict[str, Any]:
    return simulate_well_log(
        rho_v=params.rho_v,
        rho_f=params.rho_f,
        a_m=params.a_m,
        m=params.m,
        a_n=params.a_n,
        n=params.n,
        temp_c=params.temp_c,
        vnk_depth_m=params.vnk_depth_m,
        reservoir_mode=params.reservoir_mode,
        k_pt=params.k_pt,
    )


@app.post("/api/physics/basniev")
def compute_basniev_physics(params: BasnievLabParams) -> dict[str, Any]:
    dup = simulate_dupuit_flow(
        k_md=params.k_md,
        mu_cp=params.mu_cp,
        h_m=params.h_m,
        p_k_mpa=params.p_k_mpa,
        p_c_mpa=params.p_c_mpa,
        r_c_m=params.r_c_m,
        r_k_m=params.r_k_m,
        porosity_m=params.porosity_m,
    )
    tr = simulate_psss_transient(
        k_md=params.k_md,
        mu_cp=params.mu_cp,
        h_m=params.h_m,
        porosity_m=params.porosity_m,
        p_k_mpa=params.p_k_mpa,
        q_m3_day=params.q_m3_day,
        r_c_m=params.r_c_m,
        r_max_m=params.r_k_m,
        times_hours=[0.25, 1.5, params.t_hours, 24.0],
    )
    return {"dupuit": dup, "transient_psss": tr}


# Раздача собранного React-интерфейса (production Docker режим)
if WEB_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST_DIR / "assets")), name="web_assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        candidate = WEB_DIST_DIR / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST_DIR / "index.html")
