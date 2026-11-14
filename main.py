"""CLI entry point.

Usage:
    python main.py "https://www.youtube.com/watch?v=..." \
        --num-clips 3 --aspect-ratio 9:16
"""
import argparse
import json
import sys

# Windows uses 'charmap' by default, which can't encode Unicode characters
# like →. Reconfigure stdout/stderr to UTF-8 so output works on all platforms.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from shorts_generator import generate_shorts
from shorts_generator.settings import load_settings


def main() -> int:
    # Pengaturan dari pengaturan.json; opsi baris perintah menimpanya.
    settings = load_settings()

    parser = argparse.ArgumentParser(description="AI YouTube Shorts Generator")
    parser.add_argument("url", help="YouTube URL, file:// URL, or local file path")
    parser.add_argument(
        "--mode",
        choices=["api", "local"],
        default="api",
        help="api (default, MuAPI) or local (remote URL, file://, or local path + faster-whisper + LLM provider + ffmpeg).",
    )
    parser.add_argument("--num-clips", type=int, default=None, help="How many shorts to render (default: from pengaturan.json)")
    parser.add_argument("--aspect-ratio", default="9:16", help="Output aspect ratio (default: 9:16)")
    parser.add_argument("--format", default="720", help="Source download resolution: 360 / 480 / 720 / 1080 (default: 720)")
    parser.add_argument("--language", default=None, help="Force Whisper language code, e.g. 'en' (default: from pengaturan.json, 'auto' = auto-detect)")
    parser.add_argument("--clip-duration", type=int, default=None, help="Target length of each clip in seconds, e.g. 30 / 45 / 60 (local mode only; default: from pengaturan.json)")
    parser.add_argument("--subtitle-lang", default=None, help="Language of burned-in subtitles: id / en / none (local mode only; default: from pengaturan.json)")
    parser.add_argument("--watermark-box", default=None, help="Watermark box to remove, x:y:w:h in source pixels, e.g. 10:2:28:120 (local mode only; default: from pengaturan.json; empty = keep watermark)")
    parser.add_argument("--output-json", default=None, help="Write the full result JSON to this path")
    args = parser.parse_args()

    num_clips = args.num_clips if args.num_clips is not None else int(settings["jumlah_klip"])
    clip_duration = args.clip_duration if args.clip_duration is not None else int(settings["durasi_klip_detik"])
    subtitle_lang = (args.subtitle_lang or str(settings["bahasa_subtitle"])).strip().lower()
    language = args.language
    if language is None:
        configured = str(settings["bahasa_transkrip"]).strip().lower()
        language = None if configured in ("auto", "") else configured
    watermark_box = args.watermark_box
    if watermark_box is None:
        watermark_box = settings.get("kotak_watermark")
    elif isinstance(watermark_box, str):
        parts = watermark_box.strip().split(":")
        try:
            watermark_box = tuple(int(p) for p in parts) if len(parts) == 4 else None
        except ValueError:
            watermark_box = None

    try:
        result = generate_shorts(
            youtube_url=args.url,
            num_clips=num_clips,
            aspect_ratio=args.aspect_ratio,
            download_format=args.format,
            language=language,
            mode=args.mode,
            clip_duration=clip_duration,
            subtitle_lang=subtitle_lang,
            watermark_box=watermark_box,
        )
    except Exception as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        return 1

    print("\n" + "=" * 72)
    print(f"Mode:          {result.get('mode', args.mode)}")
    print(f"Source video:  {result['source_video_url']}")
    print(f"Highlights:    {len(result['highlights'])} candidates → kept top {len(result['shorts'])}")
    print("=" * 72)
    for i, s in enumerate(result["shorts"], 1):
        print(f"\n#{i}  score={s.get('score')}  {s.get('start_time'):.1f}s → {s.get('end_time'):.1f}s")
        print(f"     title:  {s.get('title')}")
        print(f"     hook:   {s.get('hook_sentence')}")
        if s.get("clip_url"):
            print(f"     clip:   {s['clip_url']}")
        else:
            print(f"     clip:   FAILED ({s.get('error')})")

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nFull JSON written to {args.output_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
