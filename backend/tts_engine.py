"""
TTS Engine: русская озвучка через edge-tts (ru-RU-DmitryNeural / ru-RU-SvetlanaNeural)
с извлечением таймкодов слов/фраз, генерацией .srt и точным расчётом длительности сцен.
При отсутствии интернета создаёт корректную синхронизированную аудиодорожку (fallback),
чтобы пайплайн сборки MP4 никогда не падал.
"""

from __future__ import annotations

import math
import re
import subprocess
import wave
from pathlib import Path

from backend.schemas import CourseManifest, SubtitleCue


def _format_srt_ts(sec: float) -> str:
    ms_total = max(0, int(round(sec * 1000)))
    h = ms_total // 3_600_000
    m = (ms_total % 3_600_000) // 60_000
    s = (ms_total % 60_000) // 1000
    ms = ms_total % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _group_words_into_cues(word_events: list[dict], max_words: int = 6) -> list[SubtitleCue]:
    """Группирует word-level таймкоды edge-tts в читаемые плашки субтитров."""
    if not word_events:
        return []
    cues: list[SubtitleCue] = []
    buf: list[dict] = []

    for ev in word_events:
        buf.append(ev)
        text = ev["text"]
        if len(buf) >= max_words or text.endswith((".", "!", "?", ";", ":")):
            cues.append(
                SubtitleCue(
                    index=len(cues) + 1,
                    start_sec=round(buf[0]["start"], 3),
                    end_sec=round(max(buf[-1]["end"], buf[0]["start"] + 0.4), 3),
                    text=" ".join(item["text"] for item in buf),
                )
            )
            buf = []

    if buf:
        cues.append(
            SubtitleCue(
                index=len(cues) + 1,
                start_sec=round(buf[0]["start"], 3),
                end_sec=round(max(buf[-1]["end"], buf[0]["start"] + 0.4), 3),
                text=" ".join(item["text"] for item in buf),
            )
        )
    return cues


def _fallback_phrase_cues(narration: str) -> tuple[list[SubtitleCue], float]:
    """Оценка таймкодов по числу слов (~2.3 слова/сек для русской речи)."""
    tokens = [t for t in re.split(r"\s+", narration.strip()) if t]
    if not tokens:
        return [], 6.0

    sec_per_word = 0.42
    cues: list[SubtitleCue] = []
    t_cur = 0.25
    chunk_size = 5
    for i in range(0, len(tokens), chunk_size):
        chunk = tokens[i : i + chunk_size]
        dur = max(1.0, len(chunk) * sec_per_word)
        cues.append(
            SubtitleCue(
                index=len(cues) + 1,
                start_sec=round(t_cur, 3),
                end_sec=round(t_cur + dur, 3),
                text=" ".join(chunk),
            )
        )
        t_cur += dur + 0.08
    return cues, round(t_cur + 0.8, 2)


def _write_silent_audio(out_mp3: Path, duration_sec: float) -> None:
    """Создаёт тихий аудиофайл (MP3 через ffmpeg или WAV при отсутствии ffmpeg)."""
    out_wav = out_mp3.with_suffix(".wav")
    sample_rate = 24000
    n_frames = int(max(1.0, duration_sec) * sample_rate)
    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames)

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(out_wav), "-c:a", "libmp3lame", "-b:a", "128k", str(out_mp3)],
            check=True,
            capture_output=True,
            timeout=30,
        )
        out_wav.unlink(missing_ok=True)
    except Exception:
        # Если ffmpeg недоступен, оставляем wav как запасной вариант
        if not out_mp3.exists():
            out_wav.replace(out_mp3)


def _probe_audio_duration(audio_path: Path) -> float | None:
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        val = float(proc.stdout.strip())
        if math.isfinite(val) and val > 0.5:
            return val
    except Exception:
        return None
    return None


async def synthesize_scene_tts(
    narration: str,
    voice: str,
    out_mp3: Path,
) -> tuple[list[SubtitleCue], float]:
    """Генерирует MP3 через edge-tts и возвращает список субтитров + точную длительность."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    word_events: list[dict] = []

    try:
        import edge_tts

        communicate = edge_tts.Communicate(narration, voice=voice)
        with open(out_mp3, "wb") as audio_file:
            async for chunk in communicate.stream():
                ctype = chunk.get("type")
                if ctype == "audio":
                    audio_file.write(chunk["data"])
                elif ctype in ("WordBoundary", "SentenceBoundary"):
                    # edge-tts отдает offset/duration в 100-наносекундных тиках
                    start_s = float(chunk.get("offset", 0)) / 10_000_000.0
                    dur_s = float(chunk.get("duration", 3_000_000)) / 10_000_000.0
                    text = str(chunk.get("text", "")).strip()
                    if text:
                        word_events.append(
                            {"start": start_s, "end": start_s + max(dur_s, 0.15), "text": text}
                        )

        probed_dur = _probe_audio_duration(out_mp3)
        cues = _group_words_into_cues(word_events)
        if not cues:
            cues, est_dur = _fallback_phrase_cues(narration)
            total_dur = probed_dur or est_dur
        else:
            total_dur = probed_dur or (cues[-1].end_sec + 0.8)
        return cues, round(max(total_dur + 0.6, 5.0), 2)
    except Exception:
        cues, est_dur = _fallback_phrase_cues(narration)
        _write_silent_audio(out_mp3, est_dur)
        return cues, est_dur


async def generate_course_audio_and_srt(
    manifest: CourseManifest,
    course_dir: Path,
    public_prefix: str,
) -> CourseManifest:
    """Синтезирует озвучку для каждой сцены, собирает общий .srt и обновляет тайминги манифеста."""
    audio_dir = course_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    srt_lines: list[str] = []
    srt_idx = 1
    global_offset = 0.0

    for scene in manifest.scenes:
        mp3_name = f"{scene.scene_id}.mp3"
        mp3_path = audio_dir / mp3_name
        cues, dur_sec = await synthesize_scene_tts(scene.narration, manifest.voice, mp3_path)
        scene.duration_sec = dur_sec
        scene.audio_path = f"{public_prefix}/audio/{mp3_name}"
        scene.subtitles = cues

        for cue in cues:
            srt_lines.append(str(srt_idx))
            srt_lines.append(
                f"{_format_srt_ts(global_offset + cue.start_sec)} --> {_format_srt_ts(global_offset + cue.end_sec)}"
            )
            srt_lines.append(cue.text)
            srt_lines.append("")
            srt_idx += 1

        global_offset += dur_sec

    srt_path = course_dir / "subtitles.srt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    manifest.srt_url = f"{public_prefix}/subtitles.srt"
    manifest.total_duration_sec = round(global_offset, 2)
    return manifest
