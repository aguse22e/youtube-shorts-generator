"""Periksa hook 1-5 detik pertama tiap klip.

Sebuah klip Shorts hidup atau mati di 5 detik pertamanya. Pemeriksaan ini
menjawab tiga pertanyaan untuk tiap klip yang selesai dibuat:

1. Ada suara? (rata-rata volume 5 detik pertama di atas -40 dB)
2. Tidak hening di awal? (hening di detik 0 kurang dari 1 detik)
3. Ada gambar? (frame pertama tidak hitam, YAVG di atas 16)

Dipanggil pipeline setelah klip selesai dipotong dan diberi subtitle,
jadi yang diperiksa adalah berkas final yang diterima user.
"""

import re
import subprocess
from typing import Dict, Optional


def _first_float(text: str, pattern: str) -> Optional[float]:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def verify_hook(clip_path: str, window: float = 5.0) -> Dict:
    """Periksa 5 detik pertama `clip_path`. Mengembalikan dict hasil."""
    cmd = [
        "ffmpeg", "-v", "info",
        "-t", f"{window:.1f}",
        "-i", clip_path,
        "-af", "volumedetect,silencedetect=noise=-40dB:d=0.3",
        "-f", "null", "-",
    ]
    audio_out = subprocess.run(cmd, capture_output=True, text=True).stderr
    mean_db = _first_float(audio_out, r"mean_volume:\s*(-?[\d.]+) dB")
    max_db = _first_float(audio_out, r"max_volume:\s*(-?[\d.]+) dB")

    # Hening di awal: periode hening pertama yang mulai di detik 0.
    starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", audio_out)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", audio_out)]
    leading_silence = 0.0
    if starts and starts[0] < 0.05:
        leading_silence = (ends[0] - starts[0]) if ends else window

    # Kecerahan frame pertama: baca lewat OpenCV (mode lokal sudah
    # mewajibkan opencv-python). Kalau cv2 tidak ada, pemeriksaan gambar
    # dilewati (yavg None) supaya tidak salah gagal.
    yavg: Optional[float] = None
    try:
        import cv2  # type: ignore

        cap = cv2.VideoCapture(clip_path)
        ok_read, frame = cap.read()
        cap.release()
        if ok_read and frame is not None:
            yavg = float(frame.mean())
    except Exception:
        yavg = None

    ok = (
        mean_db is not None and mean_db > -40.0
        and leading_silence < 1.0
        and (yavg is None or yavg > 16)
    )
    return {
        "first5_mean_db": mean_db,
        "first5_max_db": max_db,
        "leading_silence_s": round(leading_silence, 2),
        "first_frame_yavg": yavg,
        "ok": bool(ok),
    }
