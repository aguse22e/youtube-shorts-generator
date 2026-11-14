# Catatan Instalasi — YouTube Shorts Generator (Anil-matcha)

Diinstal 13 Nov 2026 di mesin ini, folder `~/workspace/youtube-shorts-generator`.

## Lingkungan
- Python 3.12.3 (venv `.venv` di folder repo), ffmpeg 8.1.2 + ffprobe tersedia di PATH.
- Dependensi terpasang: `requirements.txt` + `requirements-local.txt` (faster-whisper 1.2.1, yt-dlp 2026.10.26, opencv-python **4.10.0.84** — lihat bawah, openai 3.50.0, google-genai 3.3.0), ditambah `llama-cpp-python[server]` 0.3.36 untuk model lokal.

## Perbaikan yang diperlukan agar jalan
- Pemasangan awal gagal saat transkripsi: `open() got an unexpected keyword argument 'metadata_errors'`.
  Penyebab: `faster-whisper` memanggil `av.open(..., metadata_errors="ignore")`, tetapi PyAV 19.0.2 sudah
  menghapus parameter itu. Perbaikan: turunkan PyAV ke **15.1.0** (`pip install "av==15.1.0"`),
  versi terakhir yang masih menerima parameter tersebut dan punya wheel untuk Python 3.12.
  Jangan naikkan lagi ke 19.x tanpa menguji ulang.
- `av==14.4.0` TIDAK bisa dipakai di sini: tidak ada wheel untuk Python 3.12 dan build dari source gagal.

## Uji yang sudah dilakukan (13 Nov 2026)
- `python main.py --help` tampil benar; modul `shorts_generator` bisa diimpor.
- Video uji 20 detik tanpa ucapan: transkripsi jalan (0 segmen), lalu berhenti dengan pesan repo sendiri
  bahwa tidak ada segmen ucapan — perilaku yang diharapkan.
- Video uji 37 detik berisi ucapan Bahasa Indonesia (dibuat dengan gTTS): transkripsi jalan,
  **8 segmen** dikenali, cache SRT tertulis di `output/uji-ucapan.srt`. Langkah berikutnya berhenti
  karena kunci belum diisi (lihat bawah). Jadi alur unduh/transkripsi terverifikasi bekerja.

## Kunci layanan — SUDAH TERISI (13 Nov 2026)
- Kunci Gemini dibuat via Google AI Studio, akun agusekurnia@gmail.com, proyek
  "shorts-generator", free tier, tanpa billing. Nilai kunci HANYA ada di berkas `.env`
  (jangan pernah disalin ke chat, catatan, atau ingatan).
- `.env` berisi: `LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`, `GEMINI_MODEL=gemini-3.8-flash`.
- Model bawaan repo (`gemini-2.5-flash`) SUDAH TIDAK TERSEDIA untuk pengguna baru
  (404, pesan layanan menyarankan gemini-3.8-flash). `gemini-2.0-flash` juga sudah
  tidak tersedia (404 yang sama). Jadi model yang benar saat ini: **gemini-3.8-flash**.
- STATUS UJI 13 Nov 2026 (13.06–13.23 WIB): kunci dikenali dan permintaan sampai ke
  layanan (autentikasi jalan), tetapi `gemini-3.8-flash` menjawab **503 UNAVAILABLE
  ("high demand") dua kali** berselang ±15 menit — kapasitas free tier sedang penuh,
  bukan salah kunci. Coba lagi nanti; bila terus penuh, alternatifnya kunci penyedia
  lain (OpenAI untuk `LLM_PROVIDER=openai`, atau `MUAPI_API_KEY=...` untuk `--mode api`).
- PERCOBAAN ULANG TERJADWAL 13 Nov 2026 14.30 WIB (satu kali, sesuai jadwal):
  video uji /tmp/uji-ucapan.mp4 sudah hilang, dibuat ulang (gTTS Bahasa Indonesia,
  teks sama seperti transkrip, audio 36,7 dtk di atas assets/video-demo-thumb.png,
  hasil 38,5 dtk 1280x720). Transkripsi jalan normal (8 segmen, cache SRT ditulis
  ulang). Langkah penilaian momen (highlights) **GAGAL LAGI dengan 503 UNAVAILABLE
  yang sama** — "This model is currently experiencing high demand... Please try
  again later." — exit code 1, tidak ada klip dan tidak ada output/hasil-uji.json.
  Ini kegagalan 503 ketiga hari ini untuk gemini-3.8-flash. Tidak ada percobaan ulang
  berikutnya yang dijadwalkan; keputusan ada di user (coba lagi nanti, atau pakai
  penyedia lain).
- 9router: TIDAK ditemukan di mesin ini (tidak terpasang, port 20128 kosong, tidak ada
  kunci tersimpan di workspace) — jadi kunci dibuat baru, bukan diambil dari 9router.

## Model lokal gratis — BERHASIL 13 Nov 2026 (17.32 WIB)
User memilih model lokal setelah 503 ketiga. Jalur yang ditempuh:
- **Ollama dicoba dulu, GAGAL di mesin ini:** biner 0.40.16 terpasang (dari GitHub
  releases, 1,5 GB; /tmp hanya 512 MB jadi unduhan harus ke `~/workspace/tools`),
  server jalan, tetapi `ollama pull` mentok 10 menit di "pulling manifest" lalu
  `EOF` dari registry.ollama.ai, dan ulangan kedua juga mandek. Lalu VM restart
  menghapus `/usr/local` (di luar home tidak persisten) sehingga biner Ollama
  hilang. Ollama TIDAK dipakai lagi di sini.
- **Pengganti: llama.cpp lewat `llama-cpp-python[server]` 0.3.36** (dibangun dari
  source di venv, ±10 menit) + model **Qwen2.5-3B-Instruct Q4_K_M** (GGUF 2,1 GB,
  dari Hugging Face `Qwen/Qwen2.5-3B-Instruct-GGUF`,
  `~/workspace/tools/llama-models/qwen2.5-3b-instruct-q4_k_m.gguf`).
  Server jalan di `http://127.0.0.1:8080` (`python -m llama_cpp.server --model
  ... --n_ctx 2048 --n_threads 4`), menyediakan endpoint OpenAI-compatible.
- **Tambalan kecil di repo** (bukan upstream): `shorts_generator/config.py` dan
  `shorts_generator/local/llm.py` kini membaca `OPENAI_BASE_URL` dari `.env`;
  bila terisi, kunci OpenAI tidak diwajibkan (dipakai placeholder "ollama").
  `.env` sekarang: `LLM_PROVIDER=openai`, `OPENAI_BASE_URL=http://127.0.0.1:8080/v1`,
  `OPENAI_MODEL=qwen2.5:3b`. Kunci Gemini tetap tersimpan untuk kembali ke
  `LLM_PROVIDER=gemini` bila perlu.
- **OpenCV diturunkan 5.0.0.93 -> 4.10.0.84.** OpenCV 5 menghapus
  `cv2.CascadeClassifier` (dan modul `objdetect`), sehingga langkah pemotongan
  klip gagal dengan `module 'cv2' has no attribute 'CascadeClassifier'`.
  Di 4.10.0 API itu ada lagi. Jangan naikkan ke 5.x.
- **UJI END-TO-END BERHASIL 17.32 WIB** (video uji dibuat ulang 48,1 dtk karena
  /tmp dibersihkan saat restart): transkripsi 9 segmen, penilaian momen oleh
  model lokal jalan (3 momen, skor 95/90/85), **2 klip vertikal jadi**:
  `output/short_01.mp4` (404x720, 14,1 dtk, skor 95) dan `output/short_02.mp4`
  (404x720, 4,8 dtk, skor 90). Satu cacat kosmetik: model kecil mengisi kolom
  `title` dengan kata "string" (placeholder dari skema JSON) — waktu, skor,
  hook, dan isi klipnya benar. Judul klip sebaiknya diganti manual bila dipakai.
- **Unduhan YouTube — dua tambalan di `shorts_generator/local/downloader.py`
  (13 Nov 2026, 18.44 WIB):** (1) `nocheckcertificate: True` — mesin keluar
  lewat proxy egress bersertifikat self-signed dan certifi bawaan yt-dlp tidak
  mengenal CA-nya, jadi unduhan gagal `CERTIFICATE_VERIFY_FAILED`; (2)
  `extractor_args youtube player_client android,web` — YouTube memblokir
  yt-dlp dari IP ini dengan "Sign in to confirm you're not a bot"; klien
  android lolos tanpa login. Keduanya hanya memengaruhi unduhan video publik.
- **UJI VIDEO ASLI 18.46 WIB:** Shorts `youtube.com/shorts/_S7mul4ljEc`
  (360x640, 10,9 dtk, isi ucapan hanya "I'm standing" 3x) berhasil diunduh,
  ditranskrip (3 segmen), dinilai, dan dipotong jadi **1 klip**
  (`output/short_01.mp4`, 360x640, 9,0 dtk, skor 100, 0,0–9,0 dtk) —
  hanya 1 dari 3 yang diminta karena videonya sendiri cuma 11 detik.
  Hasil: `output/hasil-shorts.json`, sumber: `output/source__S7mul4ljEc.mp4`.
- **Klip tanpa gambar — diperbaiki 18.54 WIB:** klip hasil pemotongan ditulis
  OpenCV dengan fourcc `mp4v` (MPEG-4 Part 2) dan langkah penggabungan audio
  memakai `-c:v copy`, sehingga berkas akhir tetap MPEG-4 Part 2 — format
  yang tidak bisa diputar pemutar peramban/HP (suara ada, gambar hitam).
  Perbaikan di `shorts_generator/local/clipper.py`: langkah penggabungan kini
  meng-encode ulang ke `libx264` (`-pix_fmt yuv420p`). Klip dari Shorts di atas sudah di-encode ulang ke H.264
  dan dicek isi gambarnya (bingkai detik ke-3: karakter kartun bunga di bawah
  pohon — gambar ada). Klip-klip berikutnya otomatis H.264.
- **PENTING — server harus jalan sebelum memakai repo:** server berjalan sebagai
  proses latar dan MATI bila VM restart. Menyalakan ulang:
  `bash ~/workspace/tools/llama-server-start.sh`
  (menunggu sampai `curl http://127.0.0.1:8080/v1/models` menjawab).
  Berkas model dan venv tersimpan di `~/workspace` jadi aman dari restart;
  yang hilang hanya proses servernya.

## Cara pakai (setelah kunci terisi)
```
source .venv/bin/activate
python main.py "https://www.youtube.com/watch?v=VIDEO_ID" --mode local --num-clips 3
python main.py /path/ke/video.mp4 --mode local --num-clips 3
```
Hasil klip vertikal 9:16 tersimpan di `output/`.

## Video panjang (98 menit, 13 Nov 2026 — video UbZ4rOXPzD4)
- Transkripsi video 98 menit dengan faster-whisper `base` butuh memori besar:
  jalan pertama gagal OOM karena server model lokal ikut jalan. Solusi:
  matikan server saat transkripsi, nyalakan lagi untuk penilaian momen.
  Transkrip tersimpan sebagai cache `.srt` dan dipakai ulang bila diulang.
- Penilaian momen video panjang dipecah jadi chunk. Chunk 1200 detik
  menghasilkan prompt ~9.700 token, melebihi konteks server (2048) dan
  menggagalkan seluruh proses. Konteks server TIDAK bisa dibesarkan:
  vocab Qwen2.5 151.936 token membuat array logits 9,27 GB pada n_ctx 16384.
  Perbaikan di `shorts_generator/highlights.py`: `CHUNK_SIZE_SECONDS` 1200
  menjadi 120, `CHUNK_OVERLAP_SECONDS` 60 menjadi 15 (57 chunk untuk 98 menit),
  dan satu chunk yang gagal dilewati tanpa menggagalkan proses.
- Proses 57 chunk memakan waktu ~2 jam dan DUA KALI terputus oleh restart VM
  tanpa hasil tersimpan. Perbaikan: `get_highlights()` kini menerima
  `progress_path` dan menyimpan tiap chunk yang selesai dinilai ke
  `<sumber>.highlights-progress.json` (tulis atomik); proses berikutnya
  melewati chunk yang sudah dinilai. Jalur ini dipasang di `_run_local`
  (`shorts_generator/pipeline.py`). Mulai ulang proses yang terputus dengan
  perintah yang sama — ia melanjutkan dari chunk terakhir yang tersimpan.

## Pengaturan durasi & bahasa (14 Nov 2026)
- File `pengaturan.json` di root repo (nilai bawaan):
  `durasi_klip_detik` 45, `jumlah_klip` 3, `bahasa_transkrip` "auto",
  `bahasa_subtitle` "id". Ubah nilainya lalu jalankan `main.py` seperti biasa.
- Opsi baris perintah (menimpa file, sekali jalan):
  `--clip-duration 30`, `--subtitle-lang en`, `--language id`,
  `--num-clips 2`. Contoh:
  `python main.py "<url>" --mode local --clip-duration 30 --subtitle-lang en`
- Durasi: momen yang lebih pendek diperpanjang dari awal momennya, momen yang
  lebih panjang dipotong ke target; momen berdekatan (jeda < 5 detik) digabung
  dulu supaya tidak jadi dua klip hampir identik. Implementasi:
  `_normalize_clip_durations` di `shorts_generator/pipeline.py`.
  Batas Shorts 60 detik; nilai yang disarankan 30/45/60.
- Bahasa subtitle: "id" = tempel transkrip apa adanya, "en" = terjemahkan
  dulu lewat model lokal lalu tempel, "none" = tanpa subtitle.
  Implementasi: `shorts_generator/local/subtitles.py` (bakar dengan ffmpeg,
  H.264). Bahasa ucapan terdeteksi Whisper dan disimpan di transkrip
  (`transcript["language"]`); bila memakai cache `.srt` lama, bahasa
  diasumsikan dari pengaturan/bawaan "id".
- Catatan kualitas: model lokal kecil (Qwen2.5-3B) menerjemahkan kalimat
  biasa dengan cukup baik ("Oh, sorry, miss."), tapi sering salah pada
  umpatan/slang ("bajingan" pernah jadi "eye of a crow"). Untuk video yang
  penting, pakai subtitle "id" (tanpa terjemahan) yang selalu akurat.
- Opsi durasi & subtitle hanya berlaku untuk `--mode local` (mode api
  mengabaikannya).

## Aplikasi web (14 Nov 2026, 04:35 WIB)
- Space "YouTube Shorts Generator" (slug `youtube-shorts-generator`, fullstack): formulir tempel tautan YouTube, pengaturan durasi klip (30/45/60 dtk), jumlah klip, bahasa transkrip, bahasa subtitle (tersimpan sebagai bawaan); status server model lokal diperiksa langsung tiap halaman dibuka; pustaka klip berisi 7 klip nyata dari 2 video yang sudah dihasilkan (termasuk "Maaf, Nona" dan "Benarkah?" 45 dtk + "I'm standing" skor 100), bisa diputar dan diunduh dari halaman. Bagian "Analisa Kekurangan" memuat 12 temuan berbasis bukti dari catatan ini.
- Arsitektur jujur: pemrosesan berat (unduh, transkrip, scoring, potong) TETAP berjalan di VM ini lewat pipeline CLI, bukan di dalam aplikasi. Pekerjaan baru dari aplikasi berjalan di latar lewat alat aslinya dan hasilnya masuk ke pustaka yang sama. Jalur generate end-to-end belum pernah dijalankan live dari aplikasi (akan butuh berjam-jam untuk video nyata); jalur penyimpanan klipnya sama persis dengan jalur impor yang sudah terbukti bekerja.
- Space ini TIDAK bisa dibagikan sebagai tautan publik (fullstack tidak mendukung public link); hanya user yang bisa membukanya.

## Hapus watermark (14 Nov 2026, 17:17 WIB)
- Watermark video drama ini: teks vertikal Cina "影视效果 请勿模仿" di tepi kiri atas, posisi tetap sepanjang video (dicek di detik 10, 300, 2000), kotak ukur 10:2:28:120 piksel pada video sumber 202x360.
- Fitur baru: `kotak_watermark` di pengaturan.json (format "x:y:lebar:tinggi", null = tidak dihapus) + flag `--watermark-box` untuk sekali jalan. Diteruskan main.py → generate_shorts → _run_local → crop_highlights_local → crop_clip_local → `_remove_watermark()` (filter delogo ffmpeg, sebelum reframe supaya koordinatnya koordinat sumber; suara disalin utuh). Validasi di settings.py (`_parse_watermark_box`).
- Bukti: 2 klip 45 dtk dipotong ulang dengan watermark dihapus (`output/shorts-45s-nomark/short_01-45s-tanpa-watermark.mp4`, `short_02-45s-tanpa-watermark.mp4`); frame pertama dicek visual — teks Cina hilang, tersisa samar blur di sudut kiri atas; cek hook tetap OK (mean -21,1/-19,6 dB, hening awal 0 dtk, kecerahan 156/100).
- Catatan: video sumber ini SUDAH punya subtitle Indonesia bawaan (hardsub dari pengunggah), jadi subtitle bakar bahasa Indonesia akan menumpuk dua teks. Untuk video ini, subtitle bakar sebaiknya "none" atau biarkan hardsub aslinya saja.
- GitHub: repo `aguse22e/youtube-shorts-generator` BELUM terbuat — `create_repository` gagal 403 "Resource not accessible by integration" (aplikasi GitHub tidak diberi izin membuat repo). Manifest snapshot sudah siap (26 berkas teks, tanpa .env/output/*.mp4; thumbnail PNG `assets/video-demo-thumb.png` tidak bisa ikut karena snapshot hanya menerima teks UTF-8). Langkah lanjut: user buat repo kosong sendiri di github.com, pilih repo itu di instalasi aplikasi GitHub, lalu push snapshot dijalankan lagi.
