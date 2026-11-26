"""
Т3, Этап 3 (ролики): реальный синтез русской речи для закадра, таймлайн сцен по фактической длительности речи,
субтитры SRT/VTT по фактическим границам фраз и честное измерение громкости (EBU R128) готового трека.

Порядок движков (переменная окружения LITHOS_TTS_ENGINE):
  auto   (по умолчанию) — edge-tts (нейронный голос Microsoft, требуется сеть), при недоступности — espeak-ng (локально);
  edge   — только edge-tts;
  espeak — только локальный espeak-ng (текст закадра не покидает машину);
  none   — синтез отключён (используется в тестах отказа).

Если ни один движок не дал речь, трек заполняется тишиной ТОЛЬКО как заглушкой, а отчёт помечается
synthesis_mode="silence_fallback_error", audio_ready=False с явной ошибкой. Тихий трек никогда не выдаётся за готовый.

Сетевая операция: при edge-tts на сервис синтеза Microsoft передаётся ТОЛЬКО текст закадра (сценарий ролика,
~120–260 слов), без текста главы и PDF. TLS-проверка не отключается.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SAMPLE_RATE = 24000
PAUSE_MARK = "⏸"  # маркер паузы предсказания в тексте закадра: «⏸1.3»
DEFAULT_EDGE_VOICE = "ru-RU-DmitryNeural"
DEFAULT_EDGE_RATE = "+0%"
SILENCE_RMS_DBFS = -45.0  # ниже этого уровня фрагмент считается тишиной (синтез не удался)


class TTSUnavailableError(RuntimeError):
    """Ни один движок синтеза речи не дал разборчивую речь."""


@dataclass
class Cue:
    scene_index: int
    text: str
    start_sec: float
    end_sec: float


@dataclass
class VoiceTimeline:
    engine: str
    engine_detail: str
    audio_ready: bool
    error: str | None
    scene_bounds: list[tuple[float, float]]
    pause_windows: list[tuple[int, float, float]]  # (scene_index, start, end)
    cues: list[Cue]
    speech_duration_sec: float
    total_duration_sec: float
    reference_text: str
    clause_log: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------- движки синтеза


def _decode_to_pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
        capture_output=True,
        check=True,
        timeout=60,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _rms_dbfs(x: np.ndarray) -> float:
    if x.size == 0:
        return -120.0
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    return 20.0 * np.log10(max(rms, 1e-6))


def _trim_silence(x: np.ndarray, thr: float = 0.0018) -> np.ndarray:
    idx = np.where(np.abs(x) > thr)[0]
    if idx.size == 0:
        return x[:0]
    pad = int(0.08 * SAMPLE_RATE)
    out = x[max(0, idx[0] - pad) : min(x.size, idx[-1] + pad)].copy()
    fade = min(int(0.015 * SAMPLE_RATE), out.size // 4)
    if fade > 1:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        out[:fade] *= ramp
        out[-fade:] *= ramp[::-1]
    return out


def _edge_synth(text: str, out_mp3: Path, voice: str, rate: str) -> None:
    import time
    import edge_tts  # noqa: WPS433 (опциональная зависимость)

    async def _run() -> None:
        comm = edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(str(out_mp3))

    last_exc: Exception | None = None
    for attempt in range(6):
        try:
            out_mp3.unlink(missing_ok=True)
            asyncio.run(asyncio.wait_for(_run(), timeout=45))
            if out_mp3.exists() and out_mp3.stat().st_size >= 1000:
                return
        except Exception as exc:
            last_exc = exc
            out_mp3.unlink(missing_ok=True)
            time.sleep(1.2 * (attempt + 1))
    if last_exc is not None:
        raise last_exc


def _espeak_synth(text: str, out_wav: Path) -> None:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        raise TTSUnavailableError("espeak-ng не установлен (sudo apt-get install espeak-ng)")
    subprocess.run([exe, "-v", "ru", "-s", "150", "-w", str(out_wav), text], check=True, capture_output=True, timeout=60)


def _engine_order() -> list[str]:
    pref = os.environ.get("LITHOS_TTS_ENGINE", "auto").strip().lower()
    if pref == "none":
        return []
    if pref == "edge":
        return ["edge"]
    if pref == "espeak":
        return ["espeak"]
    return ["edge", "espeak"]


def synthesize_clause(text: str, cache_dir: Path, engines: list[str], voice: str = DEFAULT_EDGE_VOICE, rate: str = DEFAULT_EDGE_RATE) -> tuple[np.ndarray, str]:
    """Синтезирует одну фразу; возвращает PCM (24 кГц, моно, обрезанный по тишине) и имя сработавшего движка."""
    import hashlib

    cache_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    for eng in engines:
        key = hashlib.sha256(f"{eng}|{voice}|{rate}|{text}".encode("utf-8")).hexdigest()[:20]
        try:
            if eng == "edge":
                path = cache_dir / f"edge_{key}.mp3"
                if not path.exists() or path.stat().st_size < 1000:
                    _edge_synth(text, path, voice, rate)
            else:
                path = cache_dir / f"espeak_{key}.wav"
                if not path.exists() or path.stat().st_size < 1000:
                    _espeak_synth(text, path)
            pcm = _trim_silence(_decode_to_pcm(path))
            level = _rms_dbfs(pcm)
            if pcm.size < int(0.2 * SAMPLE_RATE) or level < SILENCE_RMS_DBFS:
                path.unlink(missing_ok=True)
                raise TTSUnavailableError(f"{eng}: получена тишина (RMS {level:.1f} dBFS)")
            return pcm, eng
        except Exception as exc:  # сеть, отсутствие бинарника, тишина
            errors.append(f"{eng}: {type(exc).__name__}: {str(exc)[:160]}")
    raise TTSUnavailableError("; ".join(errors) or "синтез отключён (LITHOS_TTS_ENGINE=none)")


# ---------------------------------------------------------------- таймлайн


def split_clauses(narration: str) -> list[str]:
    """Делит текст закадра на фразы по концу предложения и маркеру паузы; маркер паузы — отдельный элемент."""
    parts: list[str] = []
    for chunk in re.split(rf"({PAUSE_MARK}[0-9.]+)", narration):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith(PAUSE_MARK):
            parts.append(chunk)
            continue
        for sent in re.split(r"(?<=[.!?])\s+", chunk):
            s = sent.strip()
            if s and re.search(r"[a-zа-яё0-9]", s, re.I):
                parts.append(s)
    return parts


def display_text(narration: str) -> str:
    return re.sub(rf"\s*{PAUSE_MARK}[0-9.]+\s*", " ", narration).strip()


def _chunk_cue(scene_index: int, text: str, start: float, end: float, max_words: int) -> list[Cue]:
    words = text.split()
    if len(words) <= max_words:
        return [Cue(scene_index, text, round(start, 3), round(end, 3))]
    n_chunks = int(np.ceil(len(words) / max_words))
    size = int(np.ceil(len(words) / n_chunks))
    chunks = [" ".join(words[i : i + size]) for i in range(0, len(words), size)]
    total_chars = sum(len(c) for c in chunks) or 1
    cues: list[Cue] = []
    t = start
    for c in chunks:
        d = (end - start) * len(c) / total_chars
        cues.append(Cue(scene_index, c, round(t, 3), round(t + d, 3)))
        t += d
    return cues


def build_voice_timeline(
    narrations: list[str],
    out_audio: Path,
    cache_dir: Path,
    min_scene_sec: list[float] | None = None,
    lead_sec: float = 0.35,
    gap_sec: float = 0.18,
    tail_sec: float = 0.55,
    max_words_per_cue: int = 7,
) -> VoiceTimeline:
    """
    Синтезирует закадр по фразам, собирает сцены встык по фактической длительности речи,
    нормализует громкость (двухпроходный loudnorm до −16 LUFS, TP ≤ −1,5 dBTP) и пишет out_audio (.m4a/.mp3).
    """
    engines = _engine_order()
    pcm_parts: list[np.ndarray] = []
    cues: list[Cue] = []
    bounds: list[tuple[float, float]] = []
    pauses: list[tuple[int, float, float]] = []
    clause_log: list[dict] = []
    used: set[str] = set()
    error: str | None = None
    speech = 0.0
    t = 0.0

    def _silence(sec: float) -> np.ndarray:
        return np.zeros(int(round(sec * SAMPLE_RATE)), dtype=np.float32)

    for si, narration in enumerate(narrations):
        s_start = t
        pcm_parts.append(_silence(lead_sec))
        t += lead_sec
        for clause in split_clauses(narration):
            if clause.startswith(PAUSE_MARK):
                p = float(clause[len(PAUSE_MARK) :])
                pcm_parts.append(_silence(p))
                pauses.append((si, round(t, 3), round(t + p, 3)))
                t += p
                continue
            try:
                pcm, eng = synthesize_clause(clause, cache_dir, engines)
                used.add(eng)
            except TTSUnavailableError as exc:
                error = str(exc)
                est = max(0.6, len(clause.split()) / 2.2)  # ~130 слов/мин для заглушки
                pcm, eng = _silence(est), "none"
            d = pcm.size / SAMPLE_RATE
            pcm_parts.append(pcm)
            cues.extend(_chunk_cue(si, clause, t, t + d, max_words_per_cue))
            clause_log.append({"scene_index": si, "text": clause, "engine": eng, "start_sec": round(t, 3), "duration_sec": round(d, 3)})
            speech += d
            t += d
            pcm_parts.append(_silence(gap_sec))
            t += gap_sec
        pcm_parts.append(_silence(tail_sec))
        t += tail_sec
        if min_scene_sec and si < len(min_scene_sec) and t - s_start < min_scene_sec[si]:
            extra = min_scene_sec[si] - (t - s_start)
            pcm_parts.append(_silence(extra))
            t += extra
        bounds.append((round(s_start, 3), round(t, 3)))

    signal = np.concatenate(pcm_parts) if pcm_parts else _silence(1.0)
    raw_wav = out_audio.with_suffix(".raw.wav")
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(raw_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((np.clip(signal, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes())
    loudnorm_two_pass(raw_wav, out_audio)
    raw_wav.unlink(missing_ok=True)

    if error and used:
        engine = "mixed_with_errors"
    elif error:
        engine = "silence_fallback_error"
    elif used == {"edge"}:
        engine = "edge_tts_neural"
    elif used == {"espeak"}:
        engine = "espeak_ng_local"
    else:
        engine = "mixed_edge_espeak"
    detail = {
        "edge_tts_neural": f"edge-tts, голос {DEFAULT_EDGE_VOICE}, rate {DEFAULT_EDGE_RATE}",
        "espeak_ng_local": "espeak-ng -v ru -s 150 (локально)",
    }.get(engine, ", ".join(sorted(used)) or "нет")
    return VoiceTimeline(
        engine=engine,
        engine_detail=detail,
        audio_ready=error is None,
        error=(f"ОШИБКА СИНТЕЗА РЕЧИ: {error}" if error else None),
        scene_bounds=bounds,
        pause_windows=pauses,
        cues=cues,
        speech_duration_sec=round(speech, 2),
        total_duration_sec=round(t, 2),
        reference_text=" ".join(display_text(n) for n in narrations),
        clause_log=clause_log,
    )


# ---------------------------------------------------------------- громкость


def loudnorm_two_pass(src: Path, dst: Path, target_i: float = -16.0, target_tp: float = -1.5, lra: float = 11.0) -> None:
    """Двухпроходная нормализация EBU R128 (первый проход меряет, второй применяет линейно)."""
    p1 = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"loudnorm=I={target_i}:TP={target_tp}:LRA={lra}:print_format=json", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p1.stderr, re.S)
    af: str | None = f"loudnorm=I={target_i}:TP={target_tp}:LRA={lra}"
    if m:
        st = json.loads(m.group(0))
        if st.get("input_i") in ("-inf", "inf", "nan", None):
            af = None
        else:
            af = (
                f"loudnorm=I={target_i}:TP={target_tp}:LRA={lra}:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
                f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true"
            )
    codec = ["-c:a", "aac", "-b:a", "128k"] if dst.suffix in (".m4a", ".aac") else ["-c:a", "libmp3lame", "-b:a", "128k"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if af:
        cmd += ["-af", af]
    cmd += ["-ar", "48000", *codec, str(dst)]
    subprocess.run(cmd, check=True, timeout=120)


def measure_loudness(path: Path) -> dict[str, float]:
    """Меряет готовый файл фильтром ebur128 (integrated LUFS, true peak dBTP) и долю клиппированных отсчётов."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    tail = proc.stderr[proc.stderr.rfind("Summary:") :]
    m_i = re.search(r"I:\s+(-?[0-9.]+) LUFS", tail)
    m_tp = re.search(r"True peak:\s+Peak:\s+(-?[0-9.]+|-inf) dBFS", tail, re.S)
    pcm = _decode_to_pcm(path)
    clipped = int(np.sum(np.abs(pcm) >= 0.999))
    return {
        "integrated_lufs": float(m_i.group(1)) if m_i else float("nan"),
        "true_peak_dbtp": float(m_tp.group(1)) if m_tp and m_tp.group(1) != "-inf" else -120.0,
        "clipped_samples": clipped,
        "rms_dbfs": round(_rms_dbfs(pcm), 2),
    }


# ---------------------------------------------------------------- субтитры


def _ts(sec: float, sep: str) -> str:
    ms = max(0, int(round(sec * 1000)))
    return f"{ms // 3600000:02d}:{(ms % 3600000) // 60000:02d}:{(ms % 60000) // 1000:02d}{sep}{ms % 1000:03d}"


def write_subtitles(cues: list[Cue], srt_path: Path, vtt_path: Path) -> None:
    srt_lines: list[str] = []
    vtt_lines: list[str] = ["WEBVTT", ""]
    for i, c in enumerate(cues, start=1):
        srt_lines += [str(i), f"{_ts(c.start_sec, ',')} --> {_ts(c.end_sec, ',')}", c.text, ""]
        vtt_lines += [f"{_ts(c.start_sec, '.')} --> {_ts(c.end_sec, '.')}", c.text, ""]
    srt_path.parent.mkdir(parents=True, exist_ok=True)
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    vtt_path.write_text("\n".join(vtt_lines), encoding="utf-8")
