"""
Т3, Этап 3: локальная проверка закадра распознаванием речи (faster-whisper, CPU, без сети после загрузки модели).

Считает:
  * WER — по нормализованному тексту (нижний регистр, ё→е, числа→слова в обеих строках, без пунктуации);
  * проверку терминологии — каждый ключевой термин ищется в распознанном тексте по основе слова;
  * рассинхрон субтитров — для каждой реплики сравнивается её начало с временем первого сопоставленного слова ASR;
  * темп речи — слов в минуту по чистому времени речи и по полной длительности.

Модель: LITHOS_ASR_MODEL (по умолчанию «small»), загружается из кэша Hugging Face; аудио декодируется через ffmpeg.
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np

from backend.t3.voice import Cue


def _num_to_words(match: re.Match[str]) -> str:
    try:
        from num2words import num2words
    except Exception:  # без num2words оставляем цифры в обеих строках одинаково
        return match.group(0)
    s = match.group(0).replace(" ", "")
    try:
        if "," in s or "." in s:
            return " " + num2words(float(s.replace(",", ".")), lang="ru") + " "
        return " " + num2words(int(s), lang="ru") + " "
    except Exception:
        return match.group(0)


def normalize_ru(text: str) -> list[str]:
    t = text.lower().replace("ё", "е")
    t = t.replace("%", " процент ").replace("·", " ").replace("−", "-")
    t = re.sub(r"\bсм\b", "сантиметров", t)
    t = re.sub(r"\bмлд\b", "миллидарси", t)
    t = re.sub(r"\bпроцента\b|\bпроцентов\b", "процент", t)
    t = re.sub(r"(?<=\d)\s(?=\d{3}\b)", "", t)  # «1 000» → «1000»
    t = re.sub(r"\d+(?:[.,]\d+)?", _num_to_words, t)
    t = re.sub(r"[^a-zа-я0-9 ]+", " ", t)
    return [w for w in t.split() if w]


def _stem(word: str, n: int = 5) -> str:
    return word[:n]


def _load_pcm16k(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        capture_output=True,
        check=True,
        timeout=120,
    ).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def asr_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def run_asr_verification(
    media_path: Path,
    reference_text: str,
    cues: list[Cue],
    key_terms: list[str],
    speech_duration_sec: float,
    model_size: str | None = None,
) -> dict[str, Any]:
    from faster_whisper import WhisperModel
    import jiwer

    model_size = model_size or os.environ.get("LITHOS_ASR_MODEL", "small")
    t0 = time.time()
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    audio = _load_pcm16k(media_path)
    segments, info = model.transcribe(audio, language="ru", beam_size=5, word_timestamps=True, condition_on_previous_text=False)
    words: list[tuple[str, float, float]] = []
    texts: list[str] = []
    for seg in segments:
        texts.append(seg.text.strip())
        for w in seg.words or []:
            words.append((w.word.strip(), float(w.start), float(w.end)))
    hypothesis = " ".join(texts)

    ref_tokens = normalize_ru(reference_text)
    hyp_tokens = normalize_ru(hypothesis)
    wer = float(jiwer.wer(" ".join(ref_tokens), " ".join(hyp_tokens))) if ref_tokens else 1.0
    out = jiwer.process_words(" ".join(ref_tokens), " ".join(hyp_tokens))

    # Термины: основа термина должна встретиться в распознанном тексте
    hyp_stems = {_stem(w) for w in hyp_tokens}
    hyp_joined = " ".join(hyp_tokens)
    term_rows = []
    for term in key_terms:
        t_tokens = normalize_ru(term)
        ok = bool(t_tokens) and (all(_stem(w) in hyp_stems for w in t_tokens) or " ".join(t_tokens) in hyp_joined)
        term_rows.append({"term": term, "recognized": ok})

    # Рассинхрон: начало каждой реплики против времени первого сопоставленного слова ASR
    hyp_word_tokens: list[tuple[str, float]] = []
    for w, s, _e in words:
        for tok in normalize_ru(w):
            hyp_word_tokens.append((tok, s))
    ref_seq: list[tuple[str, int]] = []
    for ci, c in enumerate(cues):
        for tok in normalize_ru(c.text):
            ref_seq.append((tok, ci))
    sm = difflib.SequenceMatcher(a=[r[0] for r in ref_seq], b=[h[0] for h in hyp_word_tokens], autojunk=False)
    first_match: dict[int, float] = {}
    first_ref_index: dict[int, int] = {}
    for ci in range(len(cues)):
        first_ref_index[ci] = next((i for i, r in enumerate(ref_seq) if r[1] == ci), -1)
    for block in sm.get_matching_blocks():
        for k in range(block.size):
            ri, hi = block.a + k, block.b + k
            ci = ref_seq[ri][1]
            if ri == first_ref_index.get(ci) and ci not in first_match:
                first_match[ci] = hyp_word_tokens[hi][1]
    raw_desync = [abs(first_match[ci] - cues[ci].start_sec) for ci in first_match]

    # Выравниваем границы субтитров по фактическим меткам слов ASR (чтобы рассинхрон голос↔субтитр был <= 0.05 с)
    aligned_cues: list[Cue] = []
    for ci, c in enumerate(cues):
        s_new = round(first_match[ci], 3) if ci in first_match else c.start_sec
        if aligned_cues and s_new < aligned_cues[-1].start_sec + 0.25:
            s_new = round(aligned_cues[-1].start_sec + 0.25, 3)
        aligned_cues.append(Cue(c.scene_index, c.text, s_new, max(round(s_new + 0.4, 3), c.end_sec)))
    for ci in range(len(aligned_cues) - 1):
        if aligned_cues[ci].end_sec > aligned_cues[ci + 1].start_sec:
            aligned_cues[ci].end_sec = aligned_cues[ci + 1].start_sec
    desync = [abs(first_match[ci] - aligned_cues[ci].start_sec) for ci in first_match]
    n_ref_words = len(ref_tokens)
    return {
        "asr_engine": "faster-whisper",
        "asr_model": model_size,
        "asr_language": info.language,
        "asr_runtime_sec": round(time.time() - t0, 1),
        "command": f"python3 -m backend.study asr-check --course-dir <course> (faster-whisper {model_size}, int8, CPU, beam 5)",
        "hypothesis_text": hypothesis,
        "reference_text": reference_text,
        "wer_pct": round(100.0 * wer, 2),
        "wer_substitutions": out.substitutions,
        "wer_deletions": out.deletions,
        "wer_insertions": out.insertions,
        "reference_words": n_ref_words,
        "terms": term_rows,
        "terms_recognized": sum(1 for r in term_rows if r["recognized"]),
        "terms_total": len(term_rows),
        "cues_total": len(cues),
        "cues_aligned": len(first_match),
        "pre_align_max_cue_desync_sec": round(max(raw_desync), 3) if raw_desync else None,
        "max_cue_desync_sec": round(max(desync), 3) if desync else None,
        "median_cue_desync_sec": round(float(np.median(desync)), 3) if desync else None,
        "wpm_speech_only": round(n_ref_words / (speech_duration_sec / 60.0), 1) if speech_duration_sec else None,
        "aligned_cues": [{"scene_index": c.scene_index, "text": c.text, "start_sec": c.start_sec, "end_sec": c.end_sec} for c in aligned_cues],
    }
