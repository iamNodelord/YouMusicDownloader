# YouMusicDownloader

A Windows desktop app (Tkinter) that turns **YouTube**, **SoundCloud** and **Apple Music** links into **MP3 320 kbps** files.

Apple Music streams are DRM-protected and cannot be downloaded directly, so the app reads the track metadata (iTunes Lookup API), then downloads the matching track from YouTube in the best available audio quality.

## Features

- **Three sources:** YouTube, SoundCloud, Apple Music (via metadata + YouTube search)
- **MP3 320 kbps**, converted with FFmpeg (shipped inside the build — nothing to install)
- **English / Russian UI**, switchable on the fly — including already written log lines
- **Async downloads** in a worker thread; the window never freezes
- **Live status log** with progress, conversion and error messages
- **Diagnostics mode:** `YouMusicDownloader.exe --selftest`

## Download

Grab the latest build from the [Releases](../../releases) page, unpack and run
`YouMusicDownloader\YouMusicDownloader.exe`. The `_internal` folder next to the exe is required.

## Run from source

```powershell
pip install -U yt-dlp
python music_downloader.py
```

FFmpeg must be available: either in `PATH`, or as `ffmpeg.exe` next to the script / in `vendor\`.

## Build a release

```powershell
pip install -U pyinstaller yt-dlp pillow imageio-ffmpeg

# folder build — starts almost instantly (recommended)
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1 -Mode onedir

# single-file build — ~5 s startup, one file to copy
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

`prepare_ffmpeg.py` fetches `ffmpeg.exe` into `vendor\` (from `imageio-ffmpeg` or the system `PATH`), and PyInstaller packs it into the app, so end users don't need FFmpeg installed.

## Project layout

| File | Purpose |
|---|---|
| `music_downloader.py` | the whole application (GUI, i18n, yt-dlp integration) |
| `build_exe.ps1` | PyInstaller build (`-Mode onefile\|onedir`) |
| `prepare_ffmpeg.py` | puts `ffmpeg.exe` into `vendor\` for bundling |
| `make_icon.py` | generates `app_icon.ico` (Pillow) |

## License

MIT — see [LICENSE](LICENSE).

Bundled third-party components keep their own licenses:

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Unlicense
- FFmpeg — LGPL/GPL depending on the build, see [ffmpeg.org/legal](https://ffmpeg.org/legal.html)
- Python and Tcl/Tk — PSF / Tcl licenses

---

Created by iamNodelord
