"""Генерация brand icon.ico из spec в BrandMark.tsx.

Spec (из .brand/BRAND.md):
  - squircle: rounded rect, radius ~18%, fill #15161A (ink)
  - буква «А»: IBM Plex Mono 700 (fallback Consolas Bold), белая, ~50% размера
  - маркер: #FF6A3D, 14% размера, offset 13% от верхнего левого угла, rx ~18% от размера маркера

Outputs:
  desktop/icon.ico — multi-size (16, 24, 32, 48, 64, 128, 256)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

INK = (0x15, 0x16, 0x1A, 255)
SIGNAL = (0xFF, 0x6A, 0x3D, 255)
WHITE = (0xFF, 0xFF, 0xFF, 255)
BORDER = (255, 255, 255, int(0.08 * 255))

SIZES = [16, 24, 32, 48, 64, 128, 256]

# Fallback ladder: ищем bold mono шрифт системы
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consolab.ttf",  # Consolas Bold — основной fallback
    r"C:\Windows\Fonts\courbd.ttf",    # Courier New Bold
    r"C:\Windows\Fonts\arialbd.ttf",   # Arial Bold — крайний случай
]


def find_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Squircle ink
    radius = max(2, round(size * 0.18))
    draw.rounded_rectangle(
        [(0, 0), (size - 1, size - 1)],
        radius=radius,
        fill=INK,
    )

    # 2. Letter «А» (cyrillic A) — центр, ~50% размера
    font_size = max(8, round(size * 0.55))
    font = find_font(font_size)
    text = "А"

    # textbbox returns (x0, y0, x1, y1) — пиксели от 0,0 для glyph
    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    # Центрируем; bbox[0]/bbox[1] могут быть отрицательными (overflow)
    tx = (size - tw) / 2 - bbox[0]
    ty = (size - th) / 2 - bbox[1]
    draw.text((tx, ty), text, font=font, fill=WHITE)

    # 3. Оранжевый маркер (top-left)
    marker_size = max(3, round(size * 0.14))
    marker_offset = max(2, round(size * 0.135))
    marker_radius = max(1, round(marker_size * 0.18))
    draw.rounded_rectangle(
        [
            (marker_offset, marker_offset),
            (marker_offset + marker_size - 1, marker_offset + marker_size - 1),
        ],
        radius=marker_radius,
        fill=SIGNAL,
    )

    return img


def main() -> None:
    here = Path(__file__).resolve().parent
    icon_path = here.parent / "icon.ico"

    images = [make_icon(s) for s in SIZES]
    # PIL сохраняет multi-size .ico передав sizes (или append_images)
    images[-1].save(
        icon_path,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[:-1],
    )

    # PNG превью 256x256 — для удобства проверки в GitHub/README
    preview = here.parent / "icon-preview-256.png"
    images[-1].save(preview, format="PNG")

    size_kb = icon_path.stat().st_size / 1024
    print(f"OK -> {icon_path} ({size_kb:.1f} KB)")
    print(f"OK -> {preview} (preview 256x256)")


if __name__ == "__main__":
    main()
