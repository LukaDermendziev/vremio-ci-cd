"""Build rounded Vremio favicon assets from the circular logo source PNG."""
from __future__ import annotations

import base64
import io
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
IMAGES = STATIC / "images"

# Prefer a repo-local source; fall back to Cursor chat asset path.
SRC_CANDIDATES = [
    IMAGES / "vremio-logo-source.png",
    Path(
        r"C:\Users\User\.cursor\projects\c-Users-User-Desktop-salon-scheduler-system"
        r"\assets\c__Users_User_AppData_Roaming_Cursor_User_workspaceStorage"
        r"_empty-window_images_ChatGPT_Image_Jul_16__2026__01_50_27_PM"
        r"-eb89bc1e-b18c-407e-9c94-83919bbb6b21.png"
    ),
]


def circular_crop(img: Image.Image) -> Image.Image:
    """Crop the white disc and make corners outside the circle transparent."""
    w, h = img.size
    cx, cy = w / 2, h / 2
    radius = min(w, h) * 0.48
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).ellipse(
        (cx - radius, cy - radius, cx + radius, cy + radius),
        fill=255,
    )
    circ = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    circ.paste(img, (0, 0))
    circ.putalpha(mask)

    pad = int(min(w, h) * 0.02)
    return circ.crop(
        (
            int(cx - radius - pad),
            int(cy - radius - pad),
            int(cx + radius + pad),
            int(cy + radius + pad),
        )
    )


def rounded_square(size: int, radius_ratio: float = 0.22) -> Image.Image:
    """Opaque white rounded square (good for Apple touch / tab fallbacks)."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    r = int(size * radius_ratio)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=(255, 255, 255, 255))
    return canvas


def composite_on_rounded(circ: Image.Image, size: int, inset_ratio: float = 0.06) -> Image.Image:
    base = rounded_square(size)
    inset = int(size * inset_ratio)
    icon = circ.resize((size - 2 * inset, size - 2 * inset), Image.Resampling.LANCZOS)
    base.paste(icon, (inset, inset), icon)
    return base


def save_ico(circ: Image.Image, path: Path) -> None:
    sizes = [16, 32, 48]
    images = [circ.resize((s, s), Image.Resampling.LANCZOS) for s in sizes]
    # Pillow writes a multi-size ICO more reliably via save(..., sizes=...).
    images[-1].save(
        path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
    )


def main() -> None:
    src = next((p for p in SRC_CANDIDATES if p.exists()), None)
    if src is None:
        raise FileNotFoundError(
            "Vremio logo source not found. Expected one of:\n"
            + "\n".join(str(p) for p in SRC_CANDIDATES)
        )

    local_src = IMAGES / "vremio-logo-source.png"
    if src.resolve() != local_src.resolve():
        local_src.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, local_src)
        src = local_src

    # Preserve Fancy Fingers icons for salon domains (once).
    salon_svg = IMAGES / "salon-favicon.svg"
    salon_ico = STATIC / "salon-favicon.ico"
    salon_apple = IMAGES / "salon-apple-touch-icon.png"
    if not salon_svg.exists() and (IMAGES / "favicon.svg").exists():
        shutil.copy2(IMAGES / "favicon.svg", salon_svg)
    if not salon_ico.exists() and (STATIC / "favicon.ico").exists():
        shutil.copy2(STATIC / "favicon.ico", salon_ico)
    if not salon_apple.exists() and (IMAGES / "apple-touch-icon.png").exists():
        shutil.copy2(IMAGES / "apple-touch-icon.png", salon_apple)

    circ = circular_crop(Image.open(src).convert("RGBA"))

    # Transparent circular mark (browser tabs / SVG).
    circ.resize((512, 512), Image.Resampling.LANCZOS).save(IMAGES / "vremio-icon.png", "PNG")
    circ.resize((32, 32), Image.Resampling.LANCZOS).save(IMAGES / "favicon-32.png", "PNG")
    circ.resize((16, 16), Image.Resampling.LANCZOS).save(IMAGES / "favicon-16.png", "PNG")
    save_ico(circ, STATIC / "favicon.ico")
    # Named copy for clarity in templates / docs.
    shutil.copy2(STATIC / "favicon.ico", STATIC / "vremio-favicon.ico")

    # Apple touch: opaque rounded square (iOS ignores transparency).
    apple = composite_on_rounded(circ, 180, inset_ratio=0.04)
    apple.save(IMAGES / "apple-touch-icon.png", "PNG")
    apple.save(IMAGES / "vremio-apple-touch-icon.png", "PNG")

    buf = io.BytesIO()
    circ.resize((128, 128), Image.Resampling.LANCZOS).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" '
        'width="128" height="128">\n'
        f'  <image href="data:image/png;base64,{b64}" width="128" height="128" />\n'
        "</svg>\n"
    )
    (IMAGES / "favicon.svg").write_text(svg, encoding="utf-8")
    (IMAGES / "vremio-favicon.svg").write_text(svg, encoding="utf-8")

    print("Built Vremio favicon assets in", STATIC)
    print("ICO bytes:", (STATIC / "favicon.ico").stat().st_size)


if __name__ == "__main__":
    main()
