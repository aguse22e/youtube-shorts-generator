"""Tempel teks terjemahan (subtitle) ke klip yang sudah jadi (mode local).

Dipakai setelah klip dipotong: ambil segmen transkrip yang masuk dalam
rentang klip, terjemahkan bila bahasa subtitle berbeda dari bahasa ucapan
(melalui model lokal yang sama dengan penilaian momen), lalu bakar teksnya
ke video dengan ffmpeg (H.264, supaya tetap bisa diputar di peramban/HP).
"""
import json
import os
import re
import subprocess
from typing import Callable, Dict, List, Optional

from .transcriber import _format_srt_timestamp

LANG_NAMES = {
    "id": "Bahasa Indonesia",
    "en": "English",
    "zh": "Mandarin",
}


def _probe_height(clip_path: str) -> int:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=height", "-of", "csv=p=0", clip_path],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return int(out.splitlines()[0])
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return 640


def _extract_json_array(raw: str) -> Optional[List[str]]:
    """Ambil array JSON dari jawaban model (toleran terhadap teks tambahan)."""
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except ValueError:
        pass
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [str(x) for x in data]
        except ValueError:
            pass
    return None


def _translate_lines(
    lines: List[str],
    source_lang: str,
    target_lang: str,
    llm_fn: Callable[[str], str],
) -> List[str]:
    """Terjemahkan sejumlah baris pendek sekaligus lewat model lokal."""
    src_name = LANG_NAMES.get(source_lang, source_lang)
    tgt_name = LANG_NAMES.get(target_lang, target_lang)
    prompt = (
        f"Translate each of the following lines from {src_name} to {tgt_name}. "
        "Keep the meaning and the casual spoken tone. "
        "Return ONLY a JSON array of strings, in the same order and with the "
        "same number of items as the input. No explanation, no markdown.\n\n"
        + json.dumps(lines, ensure_ascii=False)
    )
    try:
        translated = _extract_json_array(llm_fn(prompt))
    except Exception as e:
        print(f"[subtitle] translation failed ({e}); keeping original text", flush=True)
        return lines
    if not translated or len(translated) != len(lines):
        print("[subtitle] translation returned wrong item count; keeping original text", flush=True)
        return lines
    return translated


def _build_clip_srt(
    segments: List[Dict],
    clip_start: float,
    clip_end: float,
    source_lang: str,
    target_lang: str,
    llm_fn: Optional[Callable[[str], str]],
) -> Optional[str]:
    """Bangun teks SRT untuk satu klip (waktu relatif terhadap awal klip)."""
    rows = []
    for seg in segments:
        start = max(float(seg["start"]), clip_start)
        end = min(float(seg["end"]), clip_end)
        if end - start < 0.2:
            continue
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        rows.append({"start": start - clip_start, "end": end - clip_start, "text": text})
    if not rows:
        return None

    if target_lang != "none" and target_lang != source_lang and llm_fn is not None:
        translated = _translate_lines([r["text"] for r in rows], source_lang, target_lang, llm_fn)
        for row, text in zip(rows, translated):
            row["text"] = text

    lines = []
    for i, row in enumerate(rows, 1):
        lines.append(str(i))
        lines.append(f"{_format_srt_timestamp(row['start'])} --> {_format_srt_timestamp(row['end'])}")
        lines.append(row["text"])
        lines.append("")
    return "\n".join(lines)


def add_subtitles(
    clip_path: str,
    segments: List[Dict],
    clip_start: float,
    clip_end: float,
    source_lang: str,
    target_lang: str,
    llm_fn: Optional[Callable[[str], str]] = None,
) -> str:
    """Tempel subtitle ke klip (di tempat). Kembalikan path klipnya.

    target_lang "none" berarti tidak ada subtitle: klip dibiarkan apa adanya.
    Berkas .srt klip disimpan di samping klip supaya bisa diedit manual.
    """
    if target_lang == "none":
        return clip_path
    srt_text = _build_clip_srt(segments, clip_start, clip_end, source_lang, target_lang, llm_fn)
    if srt_text is None:
        print(f"[subtitle] no speech in clip range, skipping: {clip_path}", flush=True)
        return clip_path

    srt_path = clip_path + ".srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_text)

    height = _probe_height(clip_path)
    font_size = 18 if height <= 400 else (26 if height <= 700 else 32)
    style = (
        f"FontName=DejaVu Sans,FontSize={font_size},"
        "PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
        "BorderStyle=1,Outline=2,Alignment=2,MarginV=32"
    )
    tmp_path = clip_path + ".sub.mp4"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", clip_path,
        "-vf", f"subtitles={srt_path}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        tmp_path,
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[subtitle] burn-in failed ({e}); keeping clip without subtitles", flush=True)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return clip_path
    os.replace(tmp_path, clip_path)
    print(f"[subtitle] burned {target_lang} subtitles onto {os.path.basename(clip_path)}", flush=True)
    return clip_path
