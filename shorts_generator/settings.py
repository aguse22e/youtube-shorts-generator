"""Pengaturan yang mudah diubah untuk YouTube Shorts Generator.

File ini dibaca setiap kali `main.py` dijalankan (mode local). Ubah nilainya
di sini, atau timpa untuk sekali jalan lewat opsi baris perintah:
    python main.py <url> --mode local --clip-duration 30 --subtitle-lang en

Kunci yang diawali "_" hanya keterangan dan diabaikan oleh program.
"""
import json
import os
from typing import Dict, Optional

DEFAULTS: Dict[str, object] = {
    # Durasi tiap klip dalam detik. Momen yang lebih pendek dari ini akan
    # diperpanjang (dari awal momennya); momen yang lebih panjang dipotong.
    # Batas YouTube Shorts: 60 detik. Nilai yang disarankan: 30 / 45 / 60.
    "durasi_klip_detik": 45,
    # Jumlah klip yang dibuat dari satu video.
    "jumlah_klip": 3,
    # Bahasa ucapan di video untuk transkripsi: "auto" (ditebak otomatis),
    # atau kode bahasa: "id" (Indonesia), "en" (Inggris).
    "bahasa_transkrip": "auto",
    # Bahasa teks terjemahan yang ditempel di klip: "id" (Indonesia),
    # "en" (Inggris), atau "none" (tanpa teks terjemahan).
    "bahasa_subtitle": "id",
    # Kotak watermark yang dihapus dari tiap klip, format "x:y:lebar:tinggi"
    # dalam piksel video sumber (contoh: "10:2:28:120"). None atau "" =
    # tidak ada watermark yang dihapus.
    "kotak_watermark": None,
}

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pengaturan.json")


def load_settings(path: Optional[str] = None) -> Dict[str, object]:
    """Baca pengaturan.json (atau path lain) di atas nilai bawaan."""
    settings: Dict[str, object] = dict(DEFAULTS)
    target = path or _SETTINGS_PATH
    try:
        with open(target, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            for key, value in raw.items():
                if key.startswith("_"):
                    continue
                if key in DEFAULTS:
                    settings[key] = value
    except (OSError, ValueError):
        pass

    # Validasi ringan supaya nilai salah ketik tidak merusak proses.
    try:
        durasi = int(settings.get("durasi_klip_detik", 45))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        durasi = 45
    settings["durasi_klip_detik"] = max(5, min(180, durasi))
    try:
        jumlah = int(settings.get("jumlah_klip", 3))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        jumlah = 3
    settings["jumlah_klip"] = max(1, min(10, jumlah))
    settings["bahasa_transkrip"] = str(settings.get("bahasa_transkrip", "auto")).strip().lower() or "auto"
    settings["bahasa_subtitle"] = str(settings.get("bahasa_subtitle", "id")).strip().lower() or "id"
    settings["kotak_watermark"] = _parse_watermark_box(settings.get("kotak_watermark"))
    return settings


def _parse_watermark_box(value: object) -> Optional[tuple]:
    """Ubah "x:y:lebar:tinggi" menjadi tuple 4 angka; None bila kosong/salah."""
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) == 4:
        try:
            x, y, w, h = (int(v) for v in value)
        except (TypeError, ValueError):
            return None
        return (x, y, w, h) if x >= 0 and y >= 0 and w > 0 and h > 0 else None
    if isinstance(value, str):
        parts = value.strip().split(":")
        if len(parts) == 4:
            try:
                x, y, w, h = (int(p) for p in parts)
            except ValueError:
                return None
            return (x, y, w, h) if x >= 0 and y >= 0 and w > 0 and h > 0 else None
    return None
