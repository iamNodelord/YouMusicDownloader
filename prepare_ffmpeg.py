"""
Готовит vendor\\ffmpeg.exe для вшивания в .exe.

Источник — пакет imageio-ffmpeg (в нём лежит полный статический бинарник ffmpeg).
Запуск:  python prepare_ffmpeg.py
"""

from __future__ import annotations

import os
import shutil
import sys

VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
TARGET = os.path.join(VENDOR_DIR, "ffmpeg.exe")


def main() -> int:
    if os.path.isfile(TARGET):
        print(f"ffmpeg уже на месте: {TARGET} ({os.path.getsize(TARGET)} bytes)")
        return 0

    # Если ffmpeg установлен в системе — можно взять оттуда.
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg and os.path.isfile(system_ffmpeg):
        os.makedirs(VENDOR_DIR, exist_ok=True)
        shutil.copy2(system_ffmpeg, TARGET)
        print(f"ffmpeg скопирован из PATH: {system_ffmpeg} -> {TARGET}")
        print(f"размер: {os.path.getsize(TARGET)} bytes")
        return 0

    try:
        import imageio_ffmpeg
    except ImportError:
        print(
            "Не найден ffmpeg. Поставьте пакет с бинарником:\n"
            "    pip install imageio-ffmpeg\n"
            "или установите FFmpeg в систему и добавьте его в PATH.",
            file=sys.stderr,
        )
        return 1

    os.makedirs(VENDOR_DIR, exist_ok=True)
    source = imageio_ffmpeg.get_ffmpeg_exe()
    shutil.copy2(source, TARGET)
    print(f"ffmpeg: {source} -> {TARGET}")
    print(f"размер: {os.path.getsize(TARGET)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
