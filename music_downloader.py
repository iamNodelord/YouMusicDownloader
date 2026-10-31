"""
YouMusic Downloader — единый файл Tkinter-приложения для скачивания аудио.

Поддерживаемые источники:
  * YouTube (видео → аудио)
  * SoundCloud
  * Apple Music (DRM-защищённый поток скачать нельзя, поэтому берём название
    трека и исполнителя из метаданных и ищем тот же трек на YouTube)

Движок: yt-dlp + системный FFmpeg (постпроцессор извлекает MP3 320 кбит/с).

Запуск:
    python music_downloader.py

Зависимости:
    pip install -U yt-dlp
    FFmpeg должен быть доступен в PATH (https://ffmpeg.org/download.html)
"""

from __future__ import annotations

import ctypes
import html
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import traceback
import urllib.parse
import urllib.request
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

# ---------------------------------------------------------------------------
# Необязательная зависимость: yt-dlp.
# Импортируем «мягко», чтобы приложение всё равно запускалось и могло
# показать пользователю понятную ошибку вместо трейсбека.
# ---------------------------------------------------------------------------
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError as _YtDlpDownloadError
except Exception:  # pragma: no cover — зависит от окружения
    yt_dlp = None  # type: ignore[assignment]

    class _YtDlpDownloadError(Exception):  # type: ignore[no-redef]
        """Заглушка, чтобы остальной модуль импортировался без yt-dlp."""

DownloadError = _YtDlpDownloadError


# ---------------------------------------------------------------------------
# Локализация: одна таблица строк на каждый язык.
# Все элементы интерфейса и сообщения берут текст отсюда по ключу,
# поэтому смена языка не требует перезапуска приложения.
# ---------------------------------------------------------------------------
STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "app_title": "YouMusic Downloader — MP3 320 kbps",
        "header": "YouMusic Downloader",
        "subtitle": "YouTube · SoundCloud · Apple Music → MP3 320 kbps",
        "url_label": "Link:",
        "url_placeholder": "Paste a YouTube, SoundCloud or Apple Music link…",
        "folder_label": "Save to:",
        "browse": "Browse…",
        "download": "Download",
        "downloading": "Downloading…",
        "clear": "Clear",
        "log_label": "Status log",
        "lang_label": "Language:",
        "status_idle": "Ready.",
        "status_working": "Working…",
        "status_progress": "Downloading… {percent}%",
        "status_converting": "Converting to MP3 (320 kbps)…",
        "status_done": "Finished successfully.",
        "status_failed": "Failed — see the log for details.",
        "tip_url": "Supported: YouTube, SoundCloud and Apple Music links.\n"
                   "Apple Music links are matched to the same track on YouTube (DRM-free audio).",
        "tip_folder": "Folder where the MP3 files will be saved.",
        "tip_browse": "Choose the destination folder.",
        "tip_download": "Download the audio and convert it to MP3 320 kbps.",
        "tip_lang": "Switch the interface language instantly.",
        "tip_clear": "Clear the status log.",
        "err_empty_url": "Paste a link first.",
        "err_invalid_url": "This is not a valid link (http/https expected).",
        "err_unsupported": "Unsupported site. Only YouTube, SoundCloud and Apple Music links are accepted.",
        "err_no_folder": "Choose an existing destination folder.",
        "err_missing_ytdlp": "The 'yt-dlp' package is not installed. Run: pip install -U yt-dlp",
        "err_missing_ffmpeg": "FFmpeg was not found in PATH. Install FFmpeg and restart the app.",
        "err_apple_album": "This Apple Music link points to an album. Open the specific song "
                           "and copy its link (it contains “?i=...”).",
        "dlg_error_title": "Download error",
        "dlg_warning_title": "Warning",
        "log_backend": "yt-dlp {version} is ready.",
        "log_ffmpeg_ok": "FFmpeg found: {path}",
        "log_ffmpeg_missing": "FFmpeg not found in PATH — MP3 conversion will fail.",
        "log_start": "Starting: {url}",
        "log_apple_detect": "Apple Music link detected.",
        "log_apple_meta": "Track found: {track} — {artist}",
        "log_apple_meta_no_artist": "Track found: {track}",
        "log_apple_fallback": "Metadata unavailable, falling back to search: “{query}”",
        "log_apple_search": "Searching YouTube: “{query}”",
        "log_downloading": "Downloading… {percent}%",
        "log_converting": "Converting to MP3 320 kbps…",
        "log_success": "Saved: {title}",
        "log_saved": "File: {path}",
        "log_error": "Error: {msg}",
    },
    "ru": {
        "app_title": "YouMusic Downloader — MP3 320 кбит/с",
        "header": "YouMusic Downloader",
        "subtitle": "YouTube · SoundCloud · Apple Music → MP3 320 кбит/с",
        "url_label": "Ссылка:",
        "url_placeholder": "Вставьте ссылку YouTube, SoundCloud или Apple Music…",
        "folder_label": "Куда сохранять:",
        "browse": "Обзор…",
        "download": "Скачать",
        "downloading": "Загрузка…",
        "clear": "Очистить",
        "log_label": "Журнал состояния",
        "lang_label": "Язык:",
        "status_idle": "Готово к работе.",
        "status_working": "Выполняется…",
        "status_progress": "Скачивание… {percent}%",
        "status_converting": "Конвертация в MP3 (320 кбит/с)…",
        "status_done": "Успешно завершено.",
        "status_failed": "Ошибка — подробности в журнале.",
        "tip_url": "Поддерживаются ссылки YouTube, SoundCloud и Apple Music.\n"
                   "Ссылки Apple Music сопоставляются с тем же треком на YouTube.",
        "tip_folder": "Папка, в которую будут сохранены MP3-файлы.",
        "tip_browse": "Выбрать папку назначения.",
        "tip_download": "Скачать звук и конвертировать в MP3 320 кбит/с.",
        "tip_lang": "Мгновенно переключить язык интерфейса.",
        "tip_clear": "Очистить журнал состояния.",
        "err_empty_url": "Сначала вставьте ссылку.",
        "err_invalid_url": "Это не похоже на корректную ссылку (нужен http/https).",
        "err_unsupported": "Сайт не поддерживается. Допустимы только YouTube, SoundCloud и Apple Music.",
        "err_no_folder": "Выберите существующую папку для сохранения.",
        "err_missing_ytdlp": "Пакет 'yt-dlp' не установлен. Выполните: pip install -U yt-dlp",
        "err_missing_ffmpeg": "FFmpeg не найден в PATH. Установите FFmpeg и перезапустите приложение.",
        "err_apple_album": "Ссылка Apple Music ведёт на альбом. Откройте нужный трек "
                           "и скопируйте его ссылку (в ней есть «?i=...»).",
        "dlg_error_title": "Ошибка загрузки",
        "dlg_warning_title": "Предупреждение",
        "log_backend": "yt-dlp {version} готов к работе.",
        "log_ffmpeg_ok": "FFmpeg найден: {path}",
        "log_ffmpeg_missing": "FFmpeg не найден в PATH — конвертация в MP3 не сработает.",
        "log_start": "Запуск: {url}",
        "log_apple_detect": "Обнаружена ссылка Apple Music.",
        "log_apple_meta": "Найден трек: {track} — {artist}",
        "log_apple_meta_no_artist": "Найден трек: {track}",
        "log_apple_fallback": "Метаданные недоступны, ищем по строке: «{query}»",
        "log_apple_search": "Поиск на YouTube: «{query}»",
        "log_downloading": "Скачивание… {percent}%",
        "log_converting": "Конвертация в MP3 320 кбит/с…",
        "log_success": "Сохранено: {title}",
        "log_saved": "Файл: {path}",
        "log_error": "Ошибка: {msg}",
    },
}

DEFAULT_LANG = "en"
# Коды языков и их самоназвания (в списке показываем родные названия).
LANG_CHOICES: List[Tuple[str, str]] = [("en", "English"), ("ru", "Русский")]

# ---------------------------------------------------------------------------
# Константы оформления
# ---------------------------------------------------------------------------
UI_FONT = "Segoe UI"
LOG_FONT = "Consolas"

BG = "#f6f7f9"
CARD = "#ffffff"
BORDER = "#dfe3e8"
TEXT = "#1f2328"
MUTED = "#6b7280"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
ACCENT_DISABLED = "#9db6ee"
SOFT = "#e5e7eb"
SOFT_HOVER = "#d1d5db"
GREEN = "#15803d"
RED = "#b91c1c"
LOG_BG = "#111827"
LOG_FG = "#e5e7eb"

# Подпись автора в правом нижнем углу окна (не зависит от языка интерфейса)
CREDIT_TEXT = "Created by iamNodelord"

STATUS_COLORS = {
    "status_idle": MUTED,
    "status_working": ACCENT,
    "status_progress": ACCENT,
    "status_converting": ACCENT,
    "status_done": GREEN,
    "status_failed": RED,
}

# Домены, которые явно поддерживаются приложением.
SUPPORTED_HOSTS = (
    "youtube.com",
    "youtu.be",
    "music.youtube.com",
    "soundcloud.com",
    "on.soundcloud.com",
    "music.apple.com",
    "itunes.apple.com",
)
APPLE_HOST = "music.apple.com"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Регулярки для разбора ссылок/страниц Apple Music.
_APPLE_PATH_ID_RE = re.compile(r"/(?:album|song)/[^/]*/(\d+)")
_OG_DESC_RE = re.compile(
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Пример og:description: "Listen to Song Name by Artist on Apple Music. ..."
_LISTEN_RE = re.compile(
    r"Listen to (?:the song )?(?P<track>.+?) by (?P<artist>.+?) on Apple Music",
    re.IGNORECASE,
)
# Пример og:title: "Song Name - Single by Artist"
_OG_TRACK_TITLE_RE = re.compile(
    r"^(?P<track>.+?)\s+-\s+(?:Single|EP|Album)\s+by\s+(?P<artist>.+)$",
    re.IGNORECASE,
)
# Пример og:title трека: "Song Name by Artist on Apple Music"
_OG_BY_ON_APPLE_RE = re.compile(
    r"^(?P<track>.+?)\s+by\s+(?P<artist>.+?)\s+on\s+Apple\s*Music$", re.IGNORECASE
)
# Название релиза из одного трека приходит как "Song Name - Single"
_SINGLE_SUFFIX_RE = re.compile(r"\s+-\s+(?:Single|EP)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------
def _is_compiled() -> bool:
    """True для любой frozen-сборки: PyInstaller (sys.frozen) или Nuitka (__compiled__)."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def _binary_dirs() -> List[str]:
    """
    Где искать ffmpeg. Порядок покрывает все варианты упаковки:
      * PyInstaller --onefile  → sys._MEIPASS
      * Nuitka --standalone    → папка рядом с .exe
      * Nuitka --onefile       → папка распаковки данных (рядом с __file__)
      * запуск из исходников   → папка скрипта и vendor/
    """
    candidates: List[str] = []

    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        candidates.append(bundle)

    if sys.argv and sys.argv[0]:
        candidates.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    candidates.append(os.path.dirname(sys.executable))

    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except NameError:  # pragma: no cover — окружение без __file__
        here = ""
    if here:
        candidates.append(here)
        candidates.append(os.path.join(here, "vendor"))

    unique: List[str] = []
    for directory in candidates:
        if directory and directory not in unique and os.path.isdir(directory):
            unique.append(directory)
    return unique


def find_ffmpeg() -> Optional[str]:
    """
    Путь к ffmpeg: сначала вшитый в программу / лежащий рядом, затем — из PATH.
    Вшитый бинарник нужен, чтобы работал один .exe без установленного FFmpeg.
    """
    names = ("ffmpeg.exe", "ffmpeg") if os.name == "nt" else ("ffmpeg",)
    for directory in _binary_dirs():
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("ffmpeg")


def ffmpeg_available() -> bool:
    """FFmpeg нужен постпроцессору yt-dlp для извлечения MP3."""
    return find_ffmpeg() is not None


def detect_js_runtimes() -> Optional[Dict[str, Any]]:
    """
    Свежие версии yt-dlp для YouTube используют JS-рантайм (по умолчанию только deno).
    Если в PATH есть deno/node/bun/quickjs — сообщаем о них yt-dlp, чтобы не терять форматы.
    Формат параметра: {runtime: {config}}; пустой config — настройки по умолчанию.
    """
    found = {name: {} for name in ("deno", "node", "bun", "quickjs") if shutil.which(name)}
    return found or None


def _host_supported(host: str) -> bool:
    host = (host or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in SUPPORTED_HOSTS)


def _is_apple_music(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host == APPLE_HOST or host.endswith("." + APPLE_HOST) or host.endswith("itunes.apple.com")


def _fetch_text(url: str, timeout: float = 12.0) -> str:
    """Простое GET-чтение текста (HTML/JSON) без сторонних библиотек."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(2_000_000)  # больше нам не нужно
        charset = response.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, "replace")


def _fetch_json(url: str, timeout: float = 10.0) -> Any:
    return json.loads(_fetch_text(url, timeout=timeout))


def _itunes_lookup(
    item_id: str,
    country: Optional[str] = None,
    entity: Optional[str] = "song",
) -> List[Dict[str, Any]]:
    """
    iTunes Lookup API — официальные метаданные без DRM и без ключей.
    entity="song" для id трека, entity=None для id коллекции (альбома/сингла).
    """
    suffix = f"&entity={entity}" if entity else ""
    endpoints = []
    if country:
        endpoints.append(f"https://itunes.apple.com/lookup?id={item_id}{suffix}&country={country}")
    endpoints.append(f"https://itunes.apple.com/lookup?id={item_id}{suffix}")

    for endpoint in endpoints:
        try:
            payload = _fetch_json(endpoint)
        except Exception:
            continue  # сеть/таймаут/лимит — пробуем следующий вариант
        results = [item for item in (payload.get("results") or []) if isinstance(item, dict)]
        if results:
            return results
    return []


def _clean_release_name(name: str) -> str:
    """Убирает хвост " - Single"/" - EP" из названия релиза."""
    return _SINGLE_SUFFIX_RE.sub("", name).strip()


def _scrape_apple_page(url: str) -> Optional[Tuple[str, str]]:
    """
    Запасной путь, если iTunes API не ответил: читаем og-теги страницы.
    Срабатывает только для страниц трека (og:description начинается с "Song").
    """
    try:
        page = _fetch_text(url)
    except Exception:
        return None

    def clean(value: str) -> str:
        # U+200E/U+200F часто встречаются в og-тегах Apple Music
        return html.unescape(value).replace("\u200e", "").replace("\u200f", "").strip()

    description = ""
    match = _OG_DESC_RE.search(page)
    if match:
        description = clean(match.group(1))

    title = ""
    match = _OG_TITLE_RE.search(page)
    if match:
        title = clean(match.group(1))

    # Старый формат описания: "Listen to <song> by <artist> on Apple Music. ..."
    listen = _LISTEN_RE.search(description)
    if listen:
        track = listen.group("track").strip()
        if track:
            return track, listen.group("artist").strip()

    # Текущий формат: og:description = "Song · 2020 · Duration 3:36"
    if title and description.lower().startswith("song"):
        by_on = _OG_BY_ON_APPLE_RE.match(title)
        if by_on:
            return by_on.group("track").strip(), by_on.group("artist").strip()

    # "Song Name - Single by Artist"
    release = _OG_TRACK_TITLE_RE.match(title) if title else None
    if release:
        return release.group("track").strip(), release.group("artist").strip()
    return None


def _apple_fallback_query(url: str) -> str:
    """Последний уровень: строим запрос из slug'а URL."""
    path = urllib.parse.urlparse(url).path
    segments = [segment for segment in path.split("/") if segment]
    slug = ""
    for marker in ("album", "song", "playlist", "music-video"):
        if marker in segments:
            index = segments.index(marker)
            if index + 1 < len(segments):
                slug = segments[index + 1]
                break
    slug = urllib.parse.unquote(slug).replace("-", " ").strip()
    return slug or "apple music"


class AppleTrack(NamedTuple):
    """Результат разбора ссылки Apple Music."""

    track: str
    artist: str = ""
    is_album: bool = False  # ссылка ведёт на полноценный альбом, а не на трек


def resolve_apple_music(url: str) -> Optional[AppleTrack]:
    """
    Достаёт название и исполнителя из ссылки Apple Music.
    
    * Ссылка вида /album/<slug>/<album_id>?i=<track_id> — это трек:
      спрашиваем iTunes API по track_id.
    * Ссылка вида /album/<slug>/<id> без ?i= — это релиз:
      если в нём один трек, берём его название, иначе честно сообщаем «это альбом».
    """
    parts = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parts.query)
    segments = [segment for segment in parts.path.split("/") if segment]
    country = None
    if segments and len(segments[0]) == 2 and segments[0].isalpha():
        country = segments[0].lower()

    # --- трек внутри альбома: id в параметре ?i= -------------------------
    track_id = (query.get("i") or [""])[0].strip()
    if track_id.isdigit():
        for item in _itunes_lookup(track_id, country, entity="song"):
            if item.get("wrapperType") == "track":
                name = (item.get("trackName") or "").strip()
                if name:
                    return AppleTrack(name, (item.get("artistName") or "").strip())
        scraped = _scrape_apple_page(url)  # API не ответил — читаем og-теги
        return AppleTrack(*scraped) if scraped else None

    # --- ссылка на релиз целиком ------------------------------------------
    path_match = _APPLE_PATH_ID_RE.search(parts.path)
    collection_id = path_match.group(1) if path_match else ""
    if collection_id.isdigit():
        for item in _itunes_lookup(collection_id, country, entity=None):
            if item.get("wrapperType") != "collection":
                continue
            name = _clean_release_name((item.get("collectionName") or "").strip())
            artist = (item.get("artistName") or "").strip()
            try:
                track_count = int(item.get("trackCount") or 1)
            except (TypeError, ValueError):
                track_count = 1
            if name and track_count <= 1:
                return AppleTrack(name, artist)
            return AppleTrack("", "", is_album=True)

    return None


# ---------------------------------------------------------------------------
# Всплывающие подсказки
# ---------------------------------------------------------------------------
class Tooltip:
    """Простой тултип: текст берётся через callback, поэтому переводится на лету."""

    def __init__(self, widget: tk.Widget, text_provider: Callable[[], str], delay: int = 450) -> None:
        self.widget = widget
        self.text_provider = text_provider
        self.delay = delay
        self._after_id: Optional[str] = None
        self._window: Optional[tk.Toplevel] = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: Optional[tk.Event] = None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        text = self.text_provider()
        if not text or self._window is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._window.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._window,
            text=text,
            justify="left",
            background="#1f2328",
            foreground="#f8f9fa",
            padx=8,
            pady=5,
            wraplength=380,
            font=(UI_FONT, 9),
        ).pack()

    def _hide(self, _event: Optional[tk.Event] = None) -> None:
        self._cancel()
        if self._window is not None:
            try:
                self._window.destroy()
            except Exception:
                pass
            self._window = None


class _YtDlpLogger:
    """Перенаправляет вывод yt-dlp в журнал приложения (через очередь)."""

    def __init__(self, emit: Callable[[str, Optional[str], Optional[dict], Optional[str]], None]) -> None:
        self._emit = emit

    def debug(self, msg: str) -> None:  # слишком шумно
        return

    def info(self, msg: str) -> None:
        return

    def warning(self, msg: str) -> None:
        text = str(msg).strip()
        if text and not text.startswith("[debug] "):
            self._emit("muted", None, None, text)

    def error(self, msg: str) -> None:
        # Дублирует текст исключения — пишем в журнал приглушённым цветом.
        text = str(msg).strip()
        if text:
            self._emit("muted", None, None, text)


# ---------------------------------------------------------------------------
# Основное приложение
# ---------------------------------------------------------------------------
class MusicDownloaderApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.lang = DEFAULT_LANG

        # Очередь сообщений из рабочего потока в UI-поток (Tkinter не потокобезопасен).
        self.events: "queue.Queue[tuple]" = queue.Queue()

        # Журнал храним как структуры, чтобы перерисовывать его при смене языка.
        self.log_entries: List[Dict[str, Any]] = []

        self.status_key = "status_idle"
        self.status_kwargs: Dict[str, Any] = {}

        self._worker: Optional[threading.Thread] = None
        self._busy = False
        self._placeholder_on = False
        self._last_bucket = -1  # троттлинг прогресса (каждые 5 %)
        self._tooltips: List[Tooltip] = []

        self._build_ui()
        self._apply_language()
        self._install_placeholder()
        self._report_environment()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(120, self._poll_queue)

    # ------------------------------------------------------------------ i18n
    def t(self, key: str, **kwargs: Any) -> str:
        """Перевод по ключу с подстановкой параметров."""
        table = STRINGS.get(self.lang) or STRINGS[DEFAULT_LANG]
        text = table.get(key) or STRINGS[DEFAULT_LANG].get(key) or key
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                pass
        return text

    def _on_language_selected(self, _event: Optional[tk.Event] = None) -> None:
        label = self.lang_var.get()
        for code, name in LANG_CHOICES:
            if name == label:
                self.lang = code
                break
        self._apply_language()

    def _apply_language(self) -> None:
        """Обновляет ВСЕ тексты интерфейса текущим языком."""
        self.root.title(self.t("app_title"))

        self.title_label.configure(text=self.t("header"))
        self.subtitle_label.configure(text=self.t("subtitle"))
        self.lang_label.configure(text=self.t("lang_label"))
        self.url_label.configure(text=self.t("url_label"))
        self.folder_label.configure(text=self.t("folder_label"))
        self.browse_btn.configure(text=self.t("browse"))
        self.clear_btn.configure(text=self.t("clear"))
        self.log_label.configure(text=self.t("log_label"))
        self.download_btn.configure(text=self.t("downloading") if self._busy else self.t("download"))

        for code, name in LANG_CHOICES:
            if code == self.lang:
                self.lang_var.set(name)
                break

        # Плейсхолдер — часть интерфейса, тоже переводим.
        if self._placeholder_on:
            self.url_var.set(self.t("url_placeholder"))

        # Статус и журнал перерисовываем заново на новом языке.
        self._set_status(self.status_key, **self.status_kwargs)
        self._render_log()

    # ------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self.root.configure(background=BG)
        self.root.minsize(760, 540)
        self.root.geometry("820x600")

        # --- Шапка: заголовок + переключатель языка ------------------------
        outer = tk.Frame(self.root, background=BG, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, background=BG)
        header.pack(fill="x")

        titles = tk.Frame(header, background=BG)
        titles.pack(side="left", anchor="w")

        self.title_label = tk.Label(
            titles, background=BG, foreground=TEXT, font=(UI_FONT, 18, "bold"), anchor="w"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(
            titles, background=BG, foreground=MUTED, font=(UI_FONT, 10), anchor="w"
        )
        self.subtitle_label.pack(anchor="w", pady=(2, 0))

        lang_box = tk.Frame(header, background=BG)
        lang_box.pack(side="right", anchor="ne")

        self.lang_label = tk.Label(lang_box, background=BG, foreground=MUTED, font=(UI_FONT, 9))
        self.lang_label.pack(side="left", padx=(0, 6))

        self.lang_var = tk.StringVar(value=LANG_CHOICES[0][1])
        self.lang_combo = ttk.Combobox(
            lang_box,
            state="readonly",
            width=10,
            values=[name for _, name in LANG_CHOICES],
            textvariable=self.lang_var,
            font=(UI_FONT, 9),
        )
        self.lang_combo.pack(side="left")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language_selected)

        # --- Карточка ввода ------------------------------------------------
        card = tk.Frame(outer, background=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(14, 0))
        card_body = tk.Frame(card, background=CARD, padx=14, pady=12)
        card_body.pack(fill="x")
        card_body.columnconfigure(1, weight=1)

        self.url_label = tk.Label(
            card_body, background=CARD, foreground=TEXT, font=(UI_FONT, 10), anchor="w"
        )
        self.url_label.grid(row=0, column=0, sticky="w", padx=(0, 10), pady=(0, 8))

        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(
            card_body,
            textvariable=self.url_var,
            font=(UI_FONT, 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
            background=CARD,
            foreground=TEXT,
            insertbackground=TEXT,
        )
        self.url_entry.grid(row=0, column=1, columnspan=2, sticky="ew", ipady=5, pady=(0, 8))
        self.url_entry.bind("<FocusIn>", self._on_url_focus_in)
        self.url_entry.bind("<FocusOut>", self._on_url_focus_out)
        self.url_entry.bind("<Return>", lambda _e: self._start_download())

        self.folder_label = tk.Label(
            card_body, background=CARD, foreground=TEXT, font=(UI_FONT, 10), anchor="w"
        )
        self.folder_label.grid(row=1, column=0, sticky="w", padx=(0, 10))

        self.folder_var = tk.StringVar(value=self._default_folder())
        self.folder_entry = tk.Entry(
            card_body,
            textvariable=self.folder_var,
            font=(UI_FONT, 10),
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            background="#f3f4f6",
            foreground=MUTED,
            readonlybackground="#f3f4f6",
            state="readonly",
        )
        self.folder_entry.grid(row=1, column=1, sticky="ew", ipady=5)

        self.browse_btn = tk.Button(
            card_body,
            font=(UI_FONT, 10),
            relief="flat",
            background=SOFT,
            foreground=TEXT,
            activebackground=SOFT_HOVER,
            activeforeground=TEXT,
            cursor="hand2",
            padx=12,
            pady=4,
            command=self._choose_folder,
        )
        self.browse_btn.grid(row=1, column=2, sticky="e", padx=(8, 0))
        self._add_hover(self.browse_btn, SOFT, SOFT_HOVER)

        self.download_btn = tk.Button(
            card_body,
            font=(UI_FONT, 10, "bold"),
            relief="flat",
            background=ACCENT,
            foreground="#ffffff",
            activebackground=ACCENT_HOVER,
            activeforeground="#ffffff",
            disabledforeground="#f1f5ff",
            cursor="hand2",
            padx=20,
            pady=6,
            command=self._start_download,
        )
        self.download_btn.grid(row=2, column=0, columnspan=3, sticky="e", pady=(14, 0))
        self._add_hover(self.download_btn, ACCENT, ACCENT_HOVER)

        # --- Карточка журнала ----------------------------------------------
        log_card = tk.Frame(outer, background=CARD, highlightbackground=BORDER, highlightthickness=1)
        log_card.pack(fill="both", expand=True, pady=(12, 0))
        log_body = tk.Frame(log_card, background=CARD, padx=14, pady=10)
        log_body.pack(fill="both", expand=True)

        log_head = tk.Frame(log_body, background=CARD)
        log_head.pack(fill="x", pady=(0, 6))

        self.log_label = tk.Label(
            log_head, background=CARD, foreground=TEXT, font=(UI_FONT, 10, "bold")
        )
        self.log_label.pack(side="left")

        self.clear_btn = tk.Button(
            log_head,
            font=(UI_FONT, 9),
            relief="flat",
            background=SOFT,
            foreground=TEXT,
            activebackground=SOFT_HOVER,
            activeforeground=TEXT,
            cursor="hand2",
            padx=10,
            pady=2,
            command=self._clear_log,
        )
        self.clear_btn.pack(side="right")
        self._add_hover(self.clear_btn, SOFT, SOFT_HOVER)

        log_wrap = tk.Frame(log_body, background=LOG_BG)
        log_wrap.pack(fill="both", expand=True)

        self.log = tk.Text(
            log_wrap,
            height=12,
            wrap="word",
            relief="flat",
            background=LOG_BG,
            foreground=LOG_FG,
            insertbackground=LOG_FG,
            font=(LOG_FONT, 9),
            padx=10,
            pady=8,
            state="disabled",
        )
        scrollbar = ttk.Scrollbar(log_wrap, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for level, colour in (
            ("info", "#93c5fd"),
            ("ok", "#86efac"),
            ("err", "#fca5a5"),
            ("muted", "#9ca3af"),
        ):
            self.log.tag_configure(level, foreground=colour)

        # --- Нижняя строка: статус слева, подпись автора справа -----------
        bottom = tk.Frame(outer, background=BG)
        bottom.pack(fill="x", pady=(8, 0))

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            bottom, textvariable=self.status_var, background=BG, foreground=MUTED,
            font=(UI_FONT, 9), anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.credit_label = tk.Label(
            bottom, text=CREDIT_TEXT, background=BG, foreground=MUTED,
            font=(UI_FONT, 8), anchor="e",
        )
        self.credit_label.pack(side="right", padx=(12, 0))

        # --- Тултипы (текст переводится в момент показа) --------------------
        self._tooltips = [
            Tooltip(self.url_entry, lambda: self.t("tip_url")),
            Tooltip(self.url_label, lambda: self.t("tip_url")),
            Tooltip(self.folder_entry, lambda: self.t("tip_folder")),
            Tooltip(self.folder_label, lambda: self.t("tip_folder")),
            Tooltip(self.browse_btn, lambda: self.t("tip_browse")),
            Tooltip(self.download_btn, lambda: self.t("tip_download")),
            Tooltip(self.clear_btn, lambda: self.t("tip_clear")),
            Tooltip(self.lang_combo, lambda: self.t("tip_lang")),
            Tooltip(self.lang_label, lambda: self.t("tip_lang")),
        ]

    @staticmethod
    def _add_hover(button: tk.Button, normal: str, hover: str) -> None:
        def on_enter(_event: Optional[tk.Event] = None) -> None:
            if str(button["state"]) == "normal":
                button.configure(background=hover)

        def on_leave(_event: Optional[tk.Event] = None) -> None:
            if str(button["state"]) == "normal":
                button.configure(background=normal)

        button.bind("<Enter>", on_enter, add="+")
        button.bind("<Leave>", on_leave, add="+")

    # -------------------------------------------------------- плейсхолдер
    def _install_placeholder(self) -> None:
        self.url_var.set("")
        self._placeholder_on = False
        self._show_placeholder()

    def _show_placeholder(self) -> None:
        if self._placeholder_on or self.url_var.get().strip():
            return
        self._placeholder_on = True
        self.url_entry.configure(foreground=MUTED)
        self.url_var.set(self.t("url_placeholder"))

    def _on_url_focus_in(self, _event: Optional[tk.Event] = None) -> None:
        if self._placeholder_on:
            self._placeholder_on = False
            self.url_var.set("")
        self.url_entry.configure(foreground=TEXT)

    def _on_url_focus_out(self, _event: Optional[tk.Event] = None) -> None:
        if not self.url_var.get().strip():
            self._placeholder_on = False
            self._show_placeholder()

    def _current_url(self) -> str:
        if self._placeholder_on:
            return ""
        return self.url_var.get().strip()

    # -------------------------------------------------------------- статус
    def _set_status(self, key: str, **kwargs: Any) -> None:
        self.status_key = key
        self.status_kwargs = kwargs
        self.status_var.set(self.t(key, **kwargs))
        self.status_label.configure(foreground=STATUS_COLORS.get(key, MUTED))

    # ------------------------------------------------------------- журнал
    def _entry_text(self, entry: Dict[str, Any]) -> str:
        if entry["key"]:
            return self.t(entry["key"], **entry["kwargs"])
        return entry["raw"] or ""

    def _insert_entry(self, entry: Dict[str, Any]) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f'[{entry["time"]}] ', ("muted",))
        self.log.insert("end", self._entry_text(entry) + "\n", (entry["level"],))
        self.log.configure(state="disabled")
        self.log.see("end")

    def _append_log(
        self,
        level: str,
        key: Optional[str] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        raw: Optional[str] = None,
    ) -> None:
        """Добавляет запись и в хранилище (для смены языка), и в виджет."""
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "level": level,
            "key": key,
            "kwargs": dict(kwargs or {}),
            "raw": raw,
        }
        self.log_entries.append(entry)
        self._insert_entry(entry)

    def _render_log(self) -> None:
        """Полная перерисовка журнала (используется при смене языка)."""
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        for entry in self.log_entries:
            self._insert_entry(entry)

    def _clear_log(self) -> None:
        self.log_entries.clear()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        if not self._busy:  # во время загрузки статус не сбрасываем
            self._set_status("status_idle")

    # -------------------------------------------------- обмен с потоком
    def _emit_log(
        self,
        level: str,
        key: Optional[str] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        raw: Optional[str] = None,
    ) -> None:
        self.events.put(("log", level, key, dict(kwargs or {}), raw))

    def _emit_status(self, key: str, **kwargs: Any) -> None:
        self.events.put(("status", key, kwargs))

    def _poll_queue(self) -> None:
        """Опрос очереди сообщений в UI-потоке (единственное место правки виджетов)."""
        try:
            while True:
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    _, level, key, kwargs, raw = event
                    self._append_log(level, key, kwargs, raw)
                elif kind == "status":
                    _, key, kwargs = event
                    self._set_status(key, **kwargs)
                elif kind == "done":
                    self._set_busy(False)
                elif kind == "alert":
                    _, key, kwargs = event
                    messagebox.showerror(
                        self.t("dlg_error_title"), self.t(key, **kwargs), parent=self.root
                    )
        except queue.Empty:
            pass
        except tk.TclError:
            return  # окно уже закрыто

        try:
            self.root.after(120, self._poll_queue)
        except tk.TclError:
            pass

    # ------------------------------------------------------- папка/окружение
    @staticmethod
    def _default_folder() -> str:
        music = os.path.join(os.path.expanduser("~"), "Music")
        return music if os.path.isdir(music) else os.path.expanduser("~")

    def _choose_folder(self) -> None:
        initial = self.folder_var.get() or self._default_folder()
        path = filedialog.askdirectory(
            parent=self.root, initialdir=initial, mustexist=True, title=self.t("tip_folder")
        )
        if path:
            self.folder_var.set(os.path.normpath(path))

    def _report_environment(self) -> None:
        """Диагностика зависимостей при старте: видно сразу, что не так."""
        if yt_dlp is None:
            self._append_log("err", "err_missing_ytdlp")
            self._set_status("status_failed")
            self.download_btn.configure(state="disabled", background=ACCENT_DISABLED, cursor="arrow")
            messagebox.showerror(
                self.t("dlg_error_title"), self.t("err_missing_ytdlp"), parent=self.root
            )
            return

        version = getattr(getattr(yt_dlp, "version", None), "__version__", "?")
        self._append_log("muted", "log_backend", {"version": version})

        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            self._append_log("muted", "log_ffmpeg_ok", {"path": ffmpeg_path})
        else:
            self._append_log("err", "log_ffmpeg_missing")
            self._set_status("status_failed")

    # ---------------------------------------------------------- валидация
    def _validate_input(self, url: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        if not url:
            return "err_empty_url", {}
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return "err_invalid_url", {}
        if not _host_supported(parsed.hostname or ""):
            return "err_unsupported", {}
        if yt_dlp is None:
            return "err_missing_ytdlp", {}
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            return "err_no_folder", {}
        if not ffmpeg_available():
            return "err_missing_ffmpeg", {}
        return None

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self.download_btn.configure(
                state="disabled",
                background=ACCENT_DISABLED,
                cursor="arrow",
                text=self.t("downloading"),
            )
        else:
            self.download_btn.configure(
                state="normal",
                background=ACCENT,
                cursor="hand2",
                text=self.t("download"),
            )

    # ------------------------------------------------------------ действия
    def _start_download(self) -> None:
        if self._busy:
            return  # защита от повторного клика

        url = self._current_url()
        problem = self._validate_input(url)
        if problem is not None:
            key, kwargs = problem
            self._append_log("err", key, kwargs)
            self._set_status(key, **kwargs)
            messagebox.showerror(self.t("dlg_error_title"), self.t(key, **kwargs), parent=self.root)
            return

        folder = self.folder_var.get().strip()
        self._last_bucket = -1
        self._set_busy(True)
        self._set_status("status_working")

        # Вся тяжёлая работа — в отдельном потоке, GUI остаётся отзывчивым.
        self._worker = threading.Thread(
            target=self._download_worker,
            args=(url, folder),
            name="download-worker",
            daemon=True,
        )
        self._worker.start()

    def _download_worker(self, url: str, folder: str) -> None:
        ok = False
        try:
            target = url

            # --- Apple Music: метаданные → поиск того же трека на YouTube ---
            if _is_apple_music(url):
                self._emit_log("info", "log_apple_detect")
                meta = resolve_apple_music(url)
                if meta is not None and meta.is_album:
                    # Не угадываем трек в альбоме — просим ссылку на конкретную песню.
                    self._emit_log("err", "err_apple_album")
                    self._emit_status("status_failed")
                    self.events.put(("alert", "err_apple_album", {}))
                    return
                if meta is not None:
                    if meta.artist:
                        self._emit_log(
                            "info", "log_apple_meta", {"track": meta.track, "artist": meta.artist}
                        )
                        search = f"{meta.track} {meta.artist}"
                    else:
                        self._emit_log("info", "log_apple_meta_no_artist", {"track": meta.track})
                        search = meta.track
                else:
                    search = _apple_fallback_query(url)
                    self._emit_log("muted", "log_apple_fallback", {"query": search})

                query = f"{search} audio"
                self._emit_log("info", "log_apple_search", {"query": query})
                # ytsearch1: — заставляем yt-dlp взять первый результат поиска YouTube.
                target = f"ytsearch1:{query}"

            self._emit_log("info", "log_start", {"url": url})
            self._run_download(target, folder)
            ok = True
            self._emit_status("status_done")

        except DownloadError as exc:
            message = str(exc).strip() or exc.__class__.__name__
            self._emit_log("err", "log_error", {"msg": message})
            self._emit_status("status_failed")
        except Exception as exc:  # сеть, ФС, постпроцессор и т. п.
            self._emit_log("err", "log_error", {"msg": f"{exc.__class__.__name__}: {exc}"})
            self._emit_log("muted", None, None, traceback.format_exc().strip())
            self._emit_status("status_failed")
        finally:
            self.events.put(("done", ok))

    def _run_download(self, target: str, folder: str) -> None:
        """Непосредственный вызов yt-dlp (выполняется в рабочем потоке)."""
        conversion_logged = [False]  # чтобы не дублировать строку «конвертация»

        def on_progress(data: Dict[str, Any]) -> None:
            if data.get("status") != "downloading":
                return
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes") or 0
            if not total:
                return
            percent = max(0, min(100, int(done * 100 / total)))
            # Троттлинг: обновляем интерфейс не чаще, чем каждые 5 %.
            bucket = percent // 5
            if bucket != self._last_bucket:
                self._last_bucket = bucket
                self._emit_log("info", "log_downloading", {"percent": percent})
                self._emit_status("status_progress", percent=percent)

        def on_postprocessor(data: Dict[str, Any]) -> None:
            # Хук вызывается для каждого постпроцессора — пишем в журнал один раз.
            if data.get("status") == "started" and not conversion_logged[0]:
                conversion_logged[0] = True
                self._emit_log("info", "log_converting")
                self._emit_status("status_converting")

        options: Dict[str, Any] = {
            # Максимальное доступное аудио, иначе — лучшее из имеющегося.
            "format": "bestaudio/best",
            "outtmpl": os.path.join(folder, "%(title)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "noprogress": True,
            "no_color": True,
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "windowsfilenames": os.name == "nt",
            "ignoreerrors": False,
            # Конвертация в MP3 с постоянным битрейтом 320 кбит/с.
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }
            ],
            "progress_hooks": [on_progress],
            "postprocessor_hooks": [on_postprocessor],
            "logger": _YtDlpLogger(self._emit_log),
        }

        js_runtimes = detect_js_runtimes()
        if js_runtimes:
            options["js_runtimes"] = js_runtimes
            # yt-dlp скачивает официальный скрипт-решатель JS-задач (рекомендация апстрима);
            # если сети/зеркала нет — просто остаётся предупреждение, загрузка не падает.
            options["remote_components"] = {"ejs:github"}

        ffmpeg_path = find_ffmpeg()
        if ffmpeg_path:
            # Явно указываем папку с ffmpeg: вшитый в exe бинарник не виден через PATH.
            options["ffmpeg_location"] = os.path.dirname(ffmpeg_path)

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(target, download=True)
            prepared = ""
            if isinstance(info, dict):
                try:
                    # prepare_filename даёт путь до постпроцессинга — меняем расширение на mp3
                    prepared = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp3"
                except Exception:
                    prepared = ""

        if not isinstance(info, dict):
            return

        title = (info.get("title") or "").strip()
        if title:
            self._emit_log("ok", "log_success", {"title": title})

        # Путь к готовому файлу: сначала то, что вернул yt-dlp, потом догадка.
        candidates: List[str] = []
        downloads = info.get("requested_downloads") or []
        if downloads and isinstance(downloads[0], dict):
            candidates += [downloads[0].get("filepath") or "", downloads[0].get("_filename") or ""]
        candidates += [info.get("filepath") or "", info.get("_filename") or "", prepared]

        existing = [candidate for candidate in candidates if candidate and os.path.isfile(candidate)]
        path = existing[0] if existing else next((c for c in candidates if c), "")
        if path:
            self._emit_log("muted", "log_saved", {"path": path})

    def _on_close(self) -> None:
        # Рабочий поток демонический: при закрытии окна процесс просто завершится.
        try:
            self.root.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
def _app_dir() -> str:
    """Папка приложения: рядом с .exe в сборке, иначе — с файлом .py."""
    if _is_compiled():
        # В Nuitka --onefile sys.executable указывает во временную папку,
        # поэтому сначала берём оригинальный путь запуска (sys.argv[0]).
        if sys.argv and sys.argv[0]:
            directory = os.path.dirname(os.path.abspath(sys.argv[0]))
            if os.path.isdir(directory):
                return directory
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _enable_dpi_awareness() -> None:
    """Чёткие шрифты на HiDPI-мониторах Windows (безопасно на других ОС)."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # type: ignore[attr-defined]
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()  # type: ignore[attr-defined]
        except Exception:
            pass


def _write_crash_log() -> str:
    """В windowed-сборке консоли нет — падение сохраняем в файл рядом с .exe."""
    path = os.path.join(_app_dir(), f"crash_{time.strftime('%Y%m%d_%H%M%S')}.log")
    try:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
    except Exception:
        return ""
    return path


def _run_selftest() -> int:
    """
    Диагностика сборки без GUI: YouMusicDownloader.exe --selftest
    Пишет selftest.txt рядом с .exe (у windowed-приложения нет консоли).
    """
    report: List[str] = []
    problems: List[str] = []

    report.append(f"frozen: {bool(getattr(sys, 'frozen', False))}")
    report.append(f"python: {sys.version.split()[0]}")
    report.append(f"app dir: {_app_dir()}")

    if yt_dlp is None:
        problems.append("yt-dlp не импортируется")
        report.append("yt-dlp: FAILED")
    else:
        version = getattr(getattr(yt_dlp, "version", None), "__version__", "?")
        report.append(f"yt-dlp: {version}")
        try:
            # Извлекатели грузятся динамически — проверяем, что в сборке они есть.
            from yt_dlp.extractor import gen_extractor_classes

            extractors = sum(1 for _ in gen_extractor_classes())
            report.append(f"extractors: {extractors}")
            if extractors < 100:
                problems.append("мало извлекателей в сборке")
        except Exception as exc:
            report.append(f"extractors: FAILED ({exc})")
            problems.append("извлекатели yt-dlp недоступны")

    ffmpeg_path = find_ffmpeg()
    report.append(f"ffmpeg: {ffmpeg_path or 'NOT FOUND'}")
    if not ffmpeg_path:
        problems.append("ffmpeg не найден")
    else:
        # Настоящая конвертация: проверяет и сам бинарник, и наличие libmp3lame.
        probe_dir = ""
        try:
            probe_dir = tempfile.mkdtemp(prefix="ym_ffmpeg_")
            target = os.path.join(probe_dir, "probe.mp3")
            result = subprocess.run(
                [
                    ffmpeg_path, "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "libmp3lame", "-b:a", "320k", "-y", target,
                ],
                capture_output=True,
                timeout=60,
            )
            size = os.path.getsize(target) if os.path.isfile(target) else 0
            report.append(f"ffmpeg encode mp3: rc={result.returncode} size={size}")
            if result.returncode != 0 or size <= 0:
                problems.append("ffmpeg не кодирует MP3")
        except Exception as exc:
            report.append(f"ffmpeg encode mp3: FAILED ({exc})")
            problems.append("ошибка проверки ffmpeg")
        finally:
            shutil.rmtree(probe_dir, ignore_errors=True)

    try:
        # Проверяем, что сетевой разбор Apple Music работает и в упакованном виде.
        meta = resolve_apple_music(
            "https://music.apple.com/us/album/blinding-lights-remix/1542842760?i=1542842761"
        )
        report.append(f"apple lookup: {meta}")
        if meta is None:
            problems.append("Apple Lookup не вернул метаданные")
    except Exception as exc:
        report.append(f"apple lookup: FAILED ({exc})")
        problems.append("Apple Lookup упал с ошибкой")

    try:
        import tkinter  # noqa: F401  — проверяем, что Tk попал в сборку

        report.append("tkinter: OK")
    except Exception as exc:
        problems.append(f"tkinter: {exc}")

    # Реальный запрос к YouTube без скачивания: проверяет сеть и извлекатель.
    if yt_dlp is not None:
        try:
            with yt_dlp.YoutubeDL(
                {"quiet": True, "skip_download": True, "noprogress": True}
            ) as probe:
                found = probe.extract_info("ytsearch1:Me at the zoo", download=False)
            entries = (found or {}).get("entries") or []
            title = (entries[0].get("title") if entries else "") or "EMPTY"
            report.append(f"youtube search: {title}")
        except Exception as exc:
            report.append(f"youtube search: FAILED ({exc})")

    report.append("result: " + ("OK" if not problems else "PROBLEMS: " + "; ".join(problems)))

    try:
        with open(os.path.join(_app_dir(), "selftest.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(report) + "\n")
    except Exception:
        pass

    return 0 if not problems else 1


def main() -> None:
    if "--selftest" in sys.argv:
        raise SystemExit(_run_selftest())

    try:
        _enable_dpi_awareness()
        root = tk.Tk()
        MusicDownloaderApp(root)
        root.mainloop()
    except Exception:
        crash_path = _write_crash_log()
        try:
            messagebox.showerror(
                "YouMusic Downloader",
                f"Unexpected error.\n\n{crash_path or traceback.format_exc()}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
