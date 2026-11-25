"""
Video Assembler: детерминированный пайплайн рендера
1) Manim Community Edition -> MP4 для научных сцен (формулы LaTeX, профили, кривые ГИС)
2) Remotion Studio (npx remotion render) -> итоговый MP4 1920x1080 30fps
3) Надёжный FFmpeg fallback-композитор (объединение Manim-клипов + аудио + субтитры),
   если в окружении отсутствует headless Chromium для Remotion.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from backend.schemas import CourseManifest


def _run_cmd(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=merged_env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def render_manim_scenes(
    manifest: CourseManifest,
    project_root: Path,
    course_dir: Path,
    public_prefix: str,
    log: Callable[[str], None],
) -> CourseManifest:
    """Рендерит научные сцены через Manim, а при его отсутствии — через Matplotlib + FFmpeg fallback."""
    manim_dir = project_root / "manim_scenes"
    clips_dir = course_dir / "manim_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    # Записываем контекстный JSON для Manim-скриптов
    manim_ctx_path = course_dir / "manim_context.json"
    manim_ctx_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    manifest_dict = json.loads(manifest.model_dump_json())

    script_map = {
        "latyshova_gis": manim_dir / "render_latyshova.py",
        "basniev_hydro": manim_dir / "render_basniev.py",
        "generic_chapter": manim_dir / "render_generic.py",
    }
    script_path = script_map.get(manifest.module_type, manim_dir / "render_generic.py")
    has_manim = shutil.which("manim") is not None

    if not has_manim:
        log("Manim CLI не найден — включаю детерминированный Matplotlib + FFmpeg рендер.")

    from manim_scenes.fallback_matplotlib import render_scene_matplotlib

    for scene in manifest.scenes:
        out_name = f"{scene.scene_id}.mp4"
        out_clip = clips_dir / out_name
        rendered = False

        if has_manim and scene.visual_backend == "manim" and scene.manim_scene_class:
            media_dir = course_dir / "_manim_tmp"
            cmd = [
                "manim",
                "-qm",
                "--disable_caching",
                "--media_dir",
                str(media_dir),
                "-o",
                out_name,
                str(script_path),
                scene.manim_scene_class,
            ]
            log(f"Manim рендер сцены {scene.manim_scene_class}...")
            proc = _run_cmd(
                cmd,
                cwd=project_root,
                env={
                    "LITHOS_MANIFEST_PATH": str(manim_ctx_path),
                    "LITHOS_SCENE_ID": scene.scene_id,
                },
                timeout=240,
            )
            if proc.returncode == 0:
                found = list(media_dir.rglob(out_name))
                if found:
                    shutil.copy2(found[0], out_clip)
                    scene.manim_video_path = f"{public_prefix}/manim_clips/{out_name}"
                    log(f"Manim сцена {scene.scene_id} готова.")
                    rendered = True
            if not rendered:
                log(f"Manim fallback для {scene.scene_id} -> Matplotlib + FFmpeg.")

        if not rendered:
            scene_dict = json.loads(scene.model_dump_json())
            ok = render_scene_matplotlib(manifest_dict, scene_dict, out_clip, course_dir / "_mpl_tmp")
            if ok:
                scene.manim_video_path = f"{public_prefix}/manim_clips/{out_name}"
                log(f"Matplotlib+FFmpeg клип {scene.scene_id} готов.")
            else:
                log(f"Не удалось отрендерить клип {scene.scene_id} (проверьте ffmpeg).")

    return manifest


def assemble_final_video(
    manifest: CourseManifest,
    project_root: Path,
    course_dir: Path,
    public_prefix: str,
    log: Callable[[str], None],
) -> CourseManifest:
    """Собирает итоговый MP4 1920x1080 30fps через Remotion + FFmpeg (или FFmpeg fallback)."""
    final_mp4 = course_dir / "course_final.mp4"
    manifest_json_path = course_dir / "course_manifest.json"
    manifest_json_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    remotion_dir = project_root / "remotion_studio"
    remotion_props = course_dir / "remotion_props.json"

    # Подготавливаем локальные пути для Remotion/FFmpeg
    remotion_data = json.loads(manifest.model_dump_json())
    remotion_data["baseAssetUrl"] = f"http://127.0.0.1:8000"
    remotion_props.write_text(json.dumps(remotion_data, ensure_ascii=False, indent=2), encoding="utf-8")

    rendered_via_remotion = False
    if shutil.which("npx") and (remotion_dir / "node_modules").exists():
        log("Запуск Remotion render (1920x1080 @ 30fps)...")
        cmd = [
            "npx",
            "remotion",
            "render",
            "src/index.ts",
            "CourseVideo",
            str(final_mp4),
            "--props",
            str(remotion_props),
            "--width",
            "1920",
            "--height",
            "1080",
            "--fps",
            "30",
        ]
        proc = _run_cmd(cmd, cwd=remotion_dir, timeout=420)
        if proc.returncode == 0 and final_mp4.exists():
            rendered_via_remotion = True
            log("Remotion успешно собрал итоговый MP4.")
        else:
            log(f"Remotion завершился с кодом {proc.returncode}; переход на FFmpeg-сборку.")

    if not rendered_via_remotion and shutil.which("ffmpeg"):
        log("Сборка итогового MP4 через FFmpeg (Manim + аудио + титры)...")
        segment_files: list[Path] = []
        tmp_dir = course_dir / "_ffmpeg_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        for idx, scene in enumerate(manifest.scenes):
            seg_path = tmp_dir / f"seg_{idx:02d}.mp4"
            audio_file = course_dir / "audio" / f"{scene.scene_id}.mp3"
            manim_clip = course_dir / "manim_clips" / f"{scene.scene_id}.mp4"
            dur = max(float(scene.duration_sec), 3.0)

            if manim_clip.exists() and audio_file.exists():
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-stream_loop",
                    "-1",
                    "-i",
                    str(manim_clip),
                    "-i",
                    str(audio_file),
                    "-t",
                    f"{dur:.2f}",
                    "-vf",
                    "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=#0B1120,fps=30",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(seg_path),
                ]
            elif audio_file.exists():
                safe_title = scene.title.replace("'", "").replace(":", " -")[:60]
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    f"color=c=#0B1120:s=1920x1080:r=30:d={dur:.2f}",
                    "-i",
                    str(audio_file),
                    "-vf",
                    f"drawtext=text='{safe_title}':fontcolor=white:fontsize=46:x=(w-text_w)/2:y=(h-text_h)/2",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(seg_path),
                ]
            else:
                continue

            proc = _run_cmd(cmd, timeout=120)
            if proc.returncode == 0 and seg_path.exists():
                segment_files.append(seg_path)

        if segment_files:
            concat_txt = tmp_dir / "concat.txt"
            concat_txt.write_text(
                "\n".join(f"file '{p.as_posix()}'" for p in segment_files),
                encoding="utf-8",
            )
            raw_concat = tmp_dir / "concat.mp4"
            _run_cmd(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(raw_concat)],
                timeout=180,
            )
            srt_file = course_dir / "subtitles.srt"
            if raw_concat.exists() and srt_file.exists():
                # Наложение субтитров .srt через FFmpeg
                srt_escaped = srt_file.as_posix().replace(":", r"\:")
                proc_sub = _run_cmd(
                    [
                        "ffmpeg",
                        "-y",
                        "-i",
                        str(raw_concat),
                        "-vf",
                        "subtitles='{0}':force_style='FontSize=12,PrimaryColour=&H00F8FAFC,BackColour=&HBB0F172A,BorderStyle=4,Outline=0,MarginV=24'".format(srt_escaped),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "copy",
                        str(final_mp4),
                    ],
                    timeout=180,
                )
                if proc_sub.returncode != 0 or not final_mp4.exists():
                    shutil.copy2(raw_concat, final_mp4)
            elif raw_concat.exists():
                shutil.copy2(raw_concat, final_mp4)

    if final_mp4.exists():
        manifest.final_video_url = f"{public_prefix}/course_final.mp4"
    manifest_json_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest
