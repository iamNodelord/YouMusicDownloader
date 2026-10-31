"""
Генератор иконки приложения (app_icon.ico).

Нужен только для сборки .exe: python make_icon.py
Требует Pillow (pip install pillow). Если Pillow нет — сборка идёт без иконки.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
BLUE_TOP = (59, 130, 246)     # #3b82f6
BLUE_BOTTOM = (29, 78, 216)   # #1d4ed8
WHITE = (255, 255, 255, 255)

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")


def _gradient_background(size: int) -> Image.Image:
    """Вертикальный градиент в скруглённом квадрате."""
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(gradient)
    for y in range(size):
        t = y / max(1, size - 1)
        colour = tuple(
            int(BLUE_TOP[i] + (BLUE_BOTTOM[i] - BLUE_TOP[i]) * t) for i in range(3)
        ) + (255,)
        draw.line([(0, y), (size, y)], fill=colour)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=255)
    base.paste(gradient, (0, 0), mask)
    return base


def _draw_note_font(image: Image.Image) -> bool:
    """Пробуем отрисовать глиф ♪ системным шрифтом."""
    for font_name in ("seguisym.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            font = ImageFont.truetype(font_name, int(SIZE * 0.78))
        except OSError:
            continue
        draw = ImageDraw.Draw(image)
        text = "\u266a"  # ♪
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        x = (SIZE - (right - left)) / 2 - left
        y = (SIZE - (bottom - top)) / 2 - top
        draw.text((x, y), text, font=font, fill=WHITE)
        return True
    return False


def _draw_note_shapes(image: Image.Image) -> None:
    """Запасной вариант: нота из примитивов."""
    draw = ImageDraw.Draw(image)
    s = SIZE / 256  # масштаб относительно базовой сетки

    def rect(x0, y0, x1, y1):
        draw.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], fill=WHITE)

    def ellipse(x0, y0, x1, y1):
        draw.ellipse([x0 * s, y0 * s, x1 * s, y1 * s], fill=WHITE)

    def polygon(points):
        draw.polygon([(x * s, y * s) for x, y in points], fill=WHITE)

    rect(132, 78, 146, 168)        # левый штиль
    rect(204, 64, 218, 154)        # правый штиль
    polygon([(132, 78), (218, 54), (218, 88), (132, 112)])  # перекладина
    ellipse(96, 150, 160, 196)     # левая головка
    ellipse(168, 136, 232, 182)    # правая головка


def main() -> None:
    image = _gradient_background(SIZE)
    if not _draw_note_font(image):
        _draw_note_shapes(image)

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    image.save(OUT_PATH, format="ICO", sizes=sizes)
    print("icon:", OUT_PATH, os.path.getsize(OUT_PATH), "bytes")


if __name__ == "__main__":
    main()
