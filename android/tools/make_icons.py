"""Generate launcher icons and the default splash artwork (build-time only)."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app" / "src" / "main" / "res"
SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def draw_icon(size: int) -> Image.Image:
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    radius = int(canvas * 0.22)
    draw.rounded_rectangle((0, 0, canvas - 1, canvas - 1), radius=radius, fill=(15, 118, 110, 255))

    # Bowl
    margin = canvas * 0.22
    bowl_top = canvas * 0.52
    draw.pieslice(
        (margin, bowl_top - canvas * 0.18, canvas - margin, canvas * 0.86),
        start=0,
        end=180,
        fill=(255, 255, 255, 255),
    )
    draw.rectangle(
        (margin + canvas * 0.02, bowl_top - canvas * 0.02, canvas - margin - canvas * 0.02, bowl_top + canvas * 0.06),
        fill=(15, 118, 110, 255),
    )
    draw.rounded_rectangle(
        (margin + canvas * 0.06, canvas * 0.78, canvas - margin - canvas * 0.06, canvas * 0.83),
        radius=int(canvas * 0.02),
        fill=(255, 255, 255, 255),
    )

    # Leaf
    leaf = (canvas * 0.40, canvas * 0.22, canvas * 0.66, canvas * 0.50)
    draw.pieslice(leaf, start=270, end=90, fill=(134, 239, 172, 255))
    draw.pieslice((canvas * 0.34, canvas * 0.22, canvas * 0.60, canvas * 0.50), start=90, end=270,
                  fill=(15, 118, 110, 255))
    draw.line(
        (canvas * 0.50, canvas * 0.46, canvas * 0.56, canvas * 0.30),
        fill=(15, 118, 110, 255),
        width=max(2, int(canvas * 0.018)),
    )

    return image.resize((size, size), Image.LANCZOS)


def main() -> None:
    for density, size in SIZES.items():
        folder = RES / f"mipmap-{density}"
        folder.mkdir(parents=True, exist_ok=True)
        icon = draw_icon(size)
        icon.save(folder / "ic_launcher.png")
        icon.save(folder / "ic_launcher_round.png")
    print("icons written")


if __name__ == "__main__":
    main()
