"""End-to-end orchestrator.

Two modes:
  * mode="api"   (default) — MuAPI does download / transcribe / LLM / autocrop.
                              Fast, no local deps, pay-per-call.
  * mode="local"            — yt-dlp + faster-whisper + OpenAI or Gemini + ffmpeg/opencv.
                              Self-hosted, LLM_PROVIDER selects OpenAI or Gemini.
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .clipper import crop_highlights
from .downloader import download_youtube
from .highlights import call_muapi_llm, get_highlights
from .transcriber import transcribe


def _normalize_clip_durations(
    highlights: List[Dict],
    target_seconds: float,
    video_duration: float,
    segments: Optional[List[Dict]] = None,
) -> List[Dict]:
    """Samakan durasi tiap momen ke target (pengaturan durasi_klip_detik).

    Hook 1-5 detik: awal tiap klip dijepret (snap) ke awal kalimat
    transkrip yang sedang berjalan, supaya klip tidak mulai di tengah
    kata atau kalimat. Kalau awal momen jatuh di jeda hening, dijepret
    maju ke awal kalimat berikutnya (maks. 3 detik) supaya klip mulai
    tepat di kata pertama. Momen yang lebih pendek diperpanjang dari awal
    momennya; momen yang lebih panjang dipotong ke target (hook selalu
    di awal, jadi tetap utuh). Momen yang berdekatan (jeda < 5 detik,
    misalnya satu adegan yang sama) digabung dulu supaya tidak jadi dua
    klip yang hampir identik. Tidak pernah memotong momen yang sudah
    dipilih, dan tidak menabrak awal momen berikutnya.
    """
    seg_bounds = sorted(
        (float(s["start"]), float(s["end"]))
        for s in (segments or [])
        if "start" in s and "end" in s
    )

    def _snap_hook(start: float) -> float:
        """Jepret awal klip ke awal kalimat terdekat."""
        for s_start, s_end in seg_bounds:
            if s_end <= start:
                continue
            if s_start <= start < s_end:
                # Di tengah kalimat: mundur ke awal kalimatnya (maks. 6 dtk).
                return s_start if start - s_start <= 6.0 else start
            # Di jeda hening: maju ke awal kalimat berikutnya (maks. 3 dtk).
            return s_start if s_start - start <= 3.0 else start
        return start

    snapped = [
        {**h, "start_time": _snap_hook(float(h["start_time"]))} for h in highlights
    ]
    ordered = sorted(snapped, key=lambda h: float(h["start_time"]))
    merged: List[Dict] = []
    for h in ordered:
        if merged and float(h["start_time"]) - float(merged[-1]["end_time"]) < 5:
            prev = merged[-1]
            prev = {
                **prev,
                "end_time": max(float(prev["end_time"]), float(h["end_time"])),
                "title": prev.get("title") or h.get("title"),
            }
            merged[-1] = prev
        else:
            merged.append(dict(h))
    out: List[Dict] = []
    for i, h in enumerate(merged):
        start = float(h["start_time"])
        end = float(h["end_time"])
        new_end = start + target_seconds
        new_end = min(new_end, video_duration)
        if i + 1 < len(merged):
            new_end = min(new_end, float(merged[i + 1]["start_time"]) - 0.5)
        if new_end < end:
            new_end = end
        out.append({**h, "end_time": new_end})
    return out


def _run_local(
    youtube_url: str,
    num_clips: int,
    aspect_ratio: str,
    download_format: str,
    language: Optional[str],
    clip_duration: Optional[float] = None,
    subtitle_lang: Optional[str] = None,
    watermark_box: Optional[Tuple[int, int, int, int]] = None,
) -> Dict:
    from .local.clipper import crop_highlights_local
    from .local.downloader import download_youtube_local
    from .local.llm import call_local_llm
    from .local.subtitles import add_subtitles
    from .local.transcriber import transcribe_local

    source_path = download_youtube_local(youtube_url, fmt=download_format)

    transcript = transcribe_local(source_path, language=language)
    if not transcript["segments"]:
        raise RuntimeError(
            "Whisper produced no segments. The video may have no detectable speech."
        )

    highlights_result = get_highlights(
        transcript,
        num_clips=num_clips,
        llm_fn=call_local_llm,
        # Simpan tiap chunk yang selesai dinilai, supaya video panjang bisa
        # dilanjutkan dari chunk terakhir bila proses terputus (mis. restart).
        progress_path=str(Path(source_path).with_suffix(".highlights-progress.json")),
    )
    all_highlights: List[Dict] = highlights_result.get("highlights", [])
    if not all_highlights:
        raise RuntimeError("Highlight generator returned zero clips.")

    top = sorted(all_highlights, key=lambda h: int(h.get("score", 0)), reverse=True)[:num_clips]
    if clip_duration:
        video_duration = float(transcript.get("duration") or 0) or max(
            float(h["end_time"]) for h in top
        )
        top = _normalize_clip_durations(
            top, float(clip_duration), video_duration,
            segments=transcript.get("segments"),
        )
        print(f"[pipeline/local] clip duration set to {clip_duration:.0f}s each", flush=True)
    print(f"[pipeline/local] cropping {len(top)} of {len(all_highlights)} candidates", flush=True)

    shorts = crop_highlights_local(
        source_path, top, aspect_ratio=aspect_ratio, watermark_box=watermark_box,
    )

    if subtitle_lang and subtitle_lang != "none":
        source_lang = str(transcript.get("language") or "id").strip().lower()
        for s in shorts:
            if s.get("clip_url"):
                add_subtitles(
                    s["clip_url"],
                    transcript["segments"],
                    float(s["start_time"]),
                    float(s["end_time"]),
                    source_lang,
                    subtitle_lang,
                    call_local_llm,
                )

    # Periksa hook 1-5 detik tiap klip final (suara ada, tidak hening di
    # awal, gambar tidak hitam). Hasilnya menempel di tiap short.
    from .local.hookcheck import verify_hook

    for s in shorts:
        if s.get("clip_url"):
            hook = verify_hook(s["clip_url"])
            s["hook"] = hook
            status = "OK" if hook["ok"] else "PERIKSA"
            print(
                f"[hook] {Path(s['clip_url']).name}: 5 dtk pertama "
                f"mean {hook['first5_mean_db']} dB, "
                f"hening awal {hook['leading_silence_s']} dtk, "
                f"kecerahan frame pertama {hook['first_frame_yavg']} — {status}",
                flush=True,
            )

    return {
        "mode": "local",
        "source_video_url": source_path,
        "transcript": transcript,
        "highlights": all_highlights,
        "shorts": shorts,
    }


def _run_api(
    youtube_url: str,
    num_clips: int,
    aspect_ratio: str,
    download_format: str,
    language: Optional[str],
) -> Dict:
    source_url = download_youtube(youtube_url, fmt=download_format)

    transcript = transcribe(source_url, language=language)
    if not transcript["segments"]:
        raise RuntimeError(
            "Whisper produced no segments. The video may have no detectable speech."
        )

    highlights_result = get_highlights(transcript, num_clips=num_clips, llm_fn=call_muapi_llm)
    all_highlights: List[Dict] = highlights_result.get("highlights", [])
    if not all_highlights:
        raise RuntimeError("Highlight generator returned zero clips.")

    top = sorted(all_highlights, key=lambda h: int(h.get("score", 0)), reverse=True)[:num_clips]
    print(f"[pipeline] cropping {len(top)} of {len(all_highlights)} candidates", flush=True)

    shorts = crop_highlights(source_url, top, aspect_ratio=aspect_ratio)

    return {
        "mode": "api",
        "source_video_url": source_url,
        "transcript": transcript,
        "highlights": all_highlights,
        "shorts": shorts,
    }


def generate_shorts(
    youtube_url: str,
    num_clips: int = 3,
    aspect_ratio: str = "9:16",
    download_format: str = "720",
    language: Optional[str] = None,
    mode: str = "api",
    clip_duration: Optional[float] = None,
    subtitle_lang: Optional[str] = None,
    watermark_box: Optional[Tuple[int, int, int, int]] = None,
) -> Dict:
    """Run the full pipeline and return a structured result.

    Args:
        youtube_url: source URL.
        num_clips: how many shorts to render.
        aspect_ratio: e.g. "9:16", "1:1".
        download_format: source resolution ("360" / "480" / "720" / "1080").
        language: ISO-639-1 to force Whisper language detection.
        mode: "api" (default, MuAPI) or "local" (yt-dlp + faster-whisper +
            OpenAI or Gemini + ffmpeg).
        clip_duration: target length of each clip in seconds (local mode
            only; None = keep the model's chosen lengths).
        subtitle_lang: language of burned-in subtitles (local mode only):
            "id", "en", or "none" for no subtitles.
        watermark_box: (x, y, lebar, tinggi) dalam piksel video sumber
            untuk watermark yang dihapus tiap klip (local mode only;
            None = tidak ada yang dihapus).

    Returns:
        {
          "mode": "api" | "local",
          "source_video_url": str,   # hosted URL (api) or local path (local)
          "transcript": {...},
          "highlights": [...],       # all candidates ranked
          "shorts": [...],           # top `num_clips` with clip_url / local path
        }
    """
    mode = (mode or "api").lower()
    if mode == "local":
        return _run_local(
            youtube_url, num_clips, aspect_ratio, download_format, language,
            clip_duration=clip_duration, subtitle_lang=subtitle_lang,
            watermark_box=watermark_box,
        )
    if mode == "api":
        return _run_api(youtube_url, num_clips, aspect_ratio, download_format, language)
    raise ValueError(f"Unknown mode: {mode!r}. Use 'api' or 'local'.")
