"""
Штатная командная точка входа Т3 «Глава → курс» (python3 -m backend.study).

Поддерживаемые команды:
  python3 -m backend.study build-all [--output-dir outputs] [--no-video]
  python3 -m backend.study build-course --book train_kuznetsov.md [--ranges 200-222] [--output-dir outputs]
  python3 -m backend.study verify-registry [--book train_kuznetsov.md]
  python3 -m backend.study verify-bookmarks
  python3 -m backend.study rebuild-fact --book train_latyshova.md --old "9,5 м" --new "10,0 м"
  python3 -m backend.study check-compat --manifest path/to/course_manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from backend.schemas import CourseManifest
from backend.t3.bookmarks_verifier import run_internal_calibration_benchmark, verify_external_bookmark_package
from backend.t3.layer import build_study_layer
from backend.t3.models import StudyCoursePackage
from backend.t3.pipeline import (
    build_all_six_t3_courses,
    build_t3_course_package,
    rebuild_t3_from_layer_fact_edit,
)
from backend.t3.registry import (
    BOOK_CATALOG,
    build_independent_registry,
    verify_registry_against_layer,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"


def validate_or_migrate_legacy_course(raw_data: dict[str, Any] | str) -> dict[str, Any]:
    """
    Проверяет совместимость сохранённого курса (v1 CourseManifest или v2 StudyCoursePackage).
    При расширении JSON использует совместимые необязательные поля или узкую версионированную миграцию.
    При повреждённых обязательных полях выбрасывает ValueError с понятным сообщением вместо молчаливой потери данных.
    """
    if isinstance(raw_data, str):
        try:
            data = json.loads(raw_data)
        except Exception as exc:
            raise ValueError(f"Некорректный JSON сохранённого курса: {exc}") from exc
    else:
        data = dict(raw_data)

    if not isinstance(data, dict) or not data.get("course_id"):
        raise ValueError("Ошибка миграции курса: отсутствует обязательное поле 'course_id' (молчаливая потеря данных запрещена).")

    # Если это уже пакет Т3 v2
    if data.get("schema_version", "").startswith("lithos.t3.") or "layer" in data:
        pkg = StudyCoursePackage.model_validate(data)
        return {"format": "t3_package_v2", "course_id": pkg.course_id, "validated": True, "package": pkg}

    # Если это сохранённый курс v1 (CourseManifest)
    if "scenes" not in data or "book_file" not in data:
        raise ValueError(
            f"Ошибка совместимости курса '{data.get('course_id')}': отсутствуют обязательные поля 'book_file' или 'scenes'."
        )
    manifest = CourseManifest.model_validate(data)
    return {
        "format": "legacy_course_manifest_v1",
        "course_id": manifest.course_id,
        "book_file": manifest.book_file,
        "scenes_count": len(manifest.scenes),
        "validated": True,
        "manifest": manifest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LITHOS T3 CLI («Глава → курс»)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_all = sub.add_parser("build-all", help="Собрать все 6 курсов Т3, ролики, паспорта, ZIP и протокол заморозки")
    p_all.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    p_all.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    p_all.add_argument("--no-video", action="store_true")

    p_one = sub.add_parser("build-course", help="Собрать один курс Т3 по книге и диапазону PDF")
    p_one.add_argument("--book", required=True)
    p_one.add_argument("--ranges", default=None, help="Диапазон PDF, например '9-14,20-30' или '200-222'")
    p_one.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    p_one.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    p_one.add_argument("--no-video", action="store_true")

    p_reg = sub.add_parser("verify-registry", help="Проверить двустороннюю сверку независимого реестра и слоя")
    p_reg.add_argument("--book", default="all")
    p_reg.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))

    p_bm = sub.add_parser("verify-bookmarks", help="Запустить калибровку или проверку внешнего пакета «закладок» (Этап 4)")
    p_bm.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    p_bm.add_argument("--input", default="", help="Путь к внешнему JSON-пакету закладок организаторов")
    p_bm.add_argument("--book", default="", help="Целевой файл книги для внешнего пакета закладок")

    p_reb = sub.add_parser("rebuild-fact", help="Проверить реактивную пересборку шага, заданий, субтитров и ролика от правки факта")
    p_reb.add_argument("--book", default="train_latyshova.md")
    p_reb.add_argument("--layer-json", default="", help="Путь к уже сохранённому (отредактированному) layer.json")
    p_reb.add_argument("--claim-id", default="")
    p_reb.add_argument("--old", default="2425")
    p_reb.add_argument("--new", default="2426")
    p_reb.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    p_reb.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "rebuild_verify"))

    p_asr = sub.add_parser("asr-check", help="Прогнать локальный ASR (faster-whisper) на MP4/MP3 ролике курса")
    p_asr.add_argument("--course-dir", required=True)

    p_cmp = sub.add_parser("check-compat", help="Проверить обратную совместимость сохранённого курса JSON")
    p_cmp.add_argument("--manifest", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "build-all":
        res = build_all_six_t3_courses(
            data_dir=Path(args.data_dir),
            output_dir=Path(args.output_dir),
            render_mp4=not args.no_video,
        )
        fr = res["freeze_report"]
        print(json.dumps(fr["recounted_t3_metrics"], ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "build-course":
        pkg = build_t3_course_package(
            data_dir=Path(args.data_dir),
            output_dir=Path(args.output_dir),
            book_file=args.book,
            pdf_ranges=args.ranges,
            render_mp4=not args.no_video,
        )
        print(
            json.dumps(
                {
                    "course_id": pkg.course_id,
                    "steps": len(pkg.steps),
                    "tasks": len(pkg.tasks),
                    "registry_passed": pkg.registry_report.passed,
                    "offline_html": pkg.offline_html_url,
                    "offline_zip": pkg.offline_zip_url,
                    "zip_size_mb": pkg.offline_package_size_mb,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.cmd == "verify-registry":
        data_dir = Path(args.data_dir)
        books = list(BOOK_CATALOG.keys()) if args.book == "all" else [args.book]
        for bf in books:
            reg = build_independent_registry(data_dir, bf)
            layer, _ = build_study_layer(data_dir, bf, registry=reg)
            rep = verify_registry_against_layer(reg, layer)
            print(
                f"[Registry] {bf}: passed={rep.passed}, total={rep.total_registry_units}, "
                f"covered={rep.covered_units_count}, excluded={rep.excluded_units_count}, "
                f"manual_check={rep.manual_verification_required_count}"
            )
            if not rep.passed:
                return 1
        return 0

    if args.cmd == "verify-bookmarks":
        if args.input:
            rep = verify_external_bookmark_package(
                data_dir=Path(args.data_dir),
                input_path=Path(args.input),
                book_file=args.book or None,
            )
            print(rep.model_dump_json(indent=2))
            return 0 if rep.passed else 1
        cal = run_internal_calibration_benchmark(Path(args.data_dir))
        print(
            json.dumps(
                {
                    "evaluation_mode": cal["evaluation_mode"],
                    "false_positives_on_valid_count": cal["false_positives_on_valid_count"],
                    "detected_bookmarks_count": cal["detected_bookmarks_count"],
                    "total_injected_bookmarks": cal["total_injected_bookmarks"],
                    "recall_pct": cal["recall_pct"],
                    "fix_with_page_accuracy_pct": cal["fix_with_page_accuracy_pct"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if cal["recall_pct"] == 100.0 and cal["false_positives_on_valid_count"] == 0 else 1

    if args.cmd == "rebuild-fact":
        out_dir = Path(args.output_dir)
        layer_json_p = Path(args.layer_json) if args.layer_json else None
        if layer_json_p and layer_json_p.exists():
            from backend.t3.models import StudyCoursePackage

            pkg_json_p = layer_json_p.parent / "t3_course_package.json"
            if pkg_json_p.exists():
                pkg = StudyCoursePackage.model_validate_json(pkg_json_p.read_text(encoding="utf-8"))
            else:
                pkg = build_t3_course_package(
                    data_dir=Path(args.data_dir),
                    output_dir=out_dir,
                    book_file=args.book,
                    render_mp4=False,
                )
        else:
            pkg = build_t3_course_package(
                data_dir=Path(args.data_dir),
                output_dir=out_dir,
                book_file=args.book,
                render_mp4=True,
            )
        cid = args.claim_id or pkg.layer.claims[0].claim_id
        diff = rebuild_t3_from_layer_fact_edit(
            package=pkg,
            course_dir=out_dir / pkg.course_id,
            claim_id=cid,
            old_fact_substring=args.old,
            new_fact_substring=args.new,
            render_mp4=True,
            saved_layer_path=layer_json_p,
        )
        summary = {k: v for k, v in diff.items() if k != "updated_package"}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "asr-check":
        from backend.t3.asr_check import run_asr_verification
        from backend.t3.models import StudyCoursePackage
        from backend.t3.voice import Cue

        cdir = Path(args.course_dir)
        pkg = StudyCoursePackage.model_validate_json((cdir / "t3_course_package.json").read_text(encoding="utf-8"))
        if not pkg.media_passports:
            print(json.dumps({"status": "no_media_passport"}, ensure_ascii=False))
            return 0
        mp = pkg.media_passports[0]
        mp4 = cdir / "media" / Path(mp.video_rel_path).name
        ref_text = " ".join(sc.narration_text for sc in mp.scenes)
        cues = [Cue(i, w.word, w.start_sec, w.end_sec) for i, w in enumerate(mp.audio_report.word_timecodes)]
        res = run_asr_verification(
            mp4,
            reference_text=ref_text,
            cues=cues,
            key_terms=["сопротивление", "пласт", "нефть"] if "latyshova" in pkg.course_id else ["давления", "Дарси", "Дюпюи"],
            speech_duration_sec=mp.audio_report.speech_duration_sec or mp.duration_sec,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "check-compat":
        p = Path(args.manifest)
        res = validate_or_migrate_legacy_course(p.read_text(encoding="utf-8"))
        print(json.dumps({k: v for k, v in res.items() if k not in ("manifest", "package")}, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
