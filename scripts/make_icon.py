"""Generate the JailForge app icon (PNG + multi-size ICO) with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
SIZE = 512


def gradient(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size))
    pixels = image.load()
    start = (103, 232, 249)   # cyan
    middle = (165, 180, 252)  # indigo
    end = (249, 168, 212)     # pink
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            if t < 0.55:
                local = t / 0.55
                color = tuple(int(start[i] + (middle[i] - start[i]) * local) for i in range(3))
            else:
                local = (t - 0.55) / 0.45
                color = tuple(int(middle[i] + (end[i] - middle[i]) * local) for i in range(3))
            pixels[x, y] = color
    return image


def shield_mask(size: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    # Shield outline, scaled from the SVG viewBox.
    points = [
        (size * 0.50, size * 0.14),
        (size * 0.22, size * 0.27),
        (size * 0.22, size * 0.53),
        (size * 0.50, size * 0.86),
        (size * 0.78, size * 0.53),
        (size * 0.78, size * 0.27),
    ]
    draw.polygon(points, fill=255)
    return mask


def build() -> None:
    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    radius = int(SIZE * 0.24)
    draw.rounded_rectangle((0, 0, SIZE, SIZE), radius=radius, fill=(11, 18, 32, 255))

    gradient_image = gradient(SIZE).convert("RGBA")
    mask = shield_mask(SIZE)
    shield = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shield.paste(gradient_image, (0, 0), mask)
    canvas.alpha_composite(shield)

    # Check mark inside the shield.
    check = ImageDraw.Draw(canvas)
    width = max(10, int(SIZE * 0.055))
    check.line(
        [
            (SIZE * 0.37, SIZE * 0.51),
            (SIZE * 0.47, SIZE * 0.61),
            (SIZE * 0.65, SIZE * 0.41),
        ],
        fill=(6, 18, 31, 255),
        width=width,
        joint="curve",
    )

    png_path = ASSETS / "icon.png"
    ico_path = ASSETS / "icon.ico"
    canvas.save(png_path)
    canvas.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"written: {png_path}")
    print(f"written: {ico_path}")


if __name__ == "__main__":
    build()
