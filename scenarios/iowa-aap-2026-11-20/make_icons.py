"""Site icons for iowaleadtracker.com: "Pb", the chemical symbol for lead.

The symbol is drawn in amber on the site's dark slate. The tab icon is the bare symbol,
which stays readable at 16 px; the 180 px home-screen icon adds lead's atomic number, 82,
so it reads as a periodic-table cell.

Letters are stroked paths, not text, so they look the same everywhere. PNGs are rendered
with headless Google Chrome (no Python imaging library needed).

    python3 make_icons.py

writes favicon.svg, favicon.ico and apple-touch-icon.png to outputs/site, and profile
images (social media, GitHub) to outputs/site/brand.

Profile images are full squares with the mark shrunk to fit inside a circle, because
X, Facebook, LinkedIn, and GitHub user avatars crop to a circle.
"""

from __future__ import annotations

import struct
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / "outputs" / "site"
BRAND = SITE / "brand"  # served at /brand/
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ICO_HEADER_BYTES = 6  # ICONDIR
ICO_ENTRY_BYTES = 16  # ICONDIRENTRY per image
BG, FG = "#1f2933", "#f5a524"  # page header slate; amber for caution without alarm


def svg(*, number: bool = False, rounded: bool = True, circle_safe: bool = False) -> str:
    """Return the mark as SVG on a 64-unit grid.

    Parameters
    ----------
    number
        Add lead's atomic number, 82, and make room for it.
    rounded
        Round the background square's corners.
    circle_safe
        Shrink the mark so a circular avatar crop doesn't cut it.
    """
    w = 6.0 if number else 6.5  # stroke width
    h = w / 2
    top, base = (21.0, 54.0) if number else (14.0, 50.0)
    bowl_r, ring_r = (8.25, 7.25) if number else (9.0, 8.0)
    straight, gap = (6.0, 4.5) if number else (7.0, 5.5)
    px = 9.5 + h  # P stem centerline
    y1 = top + h
    y2 = y1 + 2 * bowl_r
    bx = px + straight
    p = f"M{px} {top} V{base} M{px} {y1} H{bx} A{bowl_r} {bowl_r} 0 0 1 {bx} {y2} H{px}"
    sx = bx + bowl_r + h + gap + h  # b stem centerline
    cy = base - h - ring_r
    b = (
        f"M{sx} {top} V{base} M{sx} {cy} A{ring_r} {ring_r} 0 1 1 {sx + 2 * ring_r} {cy} "
        f"A{ring_r} {ring_r} 0 1 1 {sx} {cy}"
    )
    right = sx + 2 * ring_r + h
    off = (64 - (right - 9.5)) / 2 - 9.5  # center the pair
    num = (
        (
            f'<text x="9" y="15.5" fill="{FG}" font-family="Helvetica, Arial, sans-serif" '
            f'font-weight="700" font-size="10.5">82</text>'
        )
        if number
        else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="{13 if rounded else 0}" fill="{BG}"/>'
        + ('<g transform="translate(32 32) scale(0.76) translate(-32 -32)">' if circle_safe else "")
        + f'<g transform="translate({off:.2f} 0)" fill="none" stroke="{FG}" stroke-width="{w}">'
        f'<path d="{p}" stroke-linejoin="round"/><path d="{b}"/></g>{num}'
        + ("</g>" if circle_safe else "")
        + "</svg>\n"
    )


def render_png(svg_text: str, size: int, out: Path) -> None:
    """Rasterize SVG with headless Chrome at exactly size x size, transparent background."""
    with tempfile.TemporaryDirectory() as d:
        page = Path(d) / "i.html"
        page.write_text(
            '<html><body style="margin:0;background:transparent">'
            f'<div style="width:{size}px;height:{size}px">'
            + svg_text.replace("<svg ", f'<svg width="{size}" height="{size}" ', 1)
            + "</div></body></html>",
            encoding="utf-8",
        )
        subprocess.run(  # noqa: S603 - fixed local Chrome path, arguments built here
            [
                CHROME,
                "--headless",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--window-size={size},{size}",
                "--default-background-color=00000000",
                f"--screenshot={out}",
                page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
    with out.open("rb") as f:
        w, h = struct.unpack(">II", f.read(24)[16:24])  # PNG IHDR width and height
    if (w, h) != (size, size):
        raise SystemExit(f"{out}: rendered {w}x{h}, wanted {size}x{size}")


def write_ico(pngs: list[tuple[Path, int]], out: Path) -> None:
    """Write an ICO file holding PNG images (supported by every current browser).

    Parameters
    ----------
    pngs
        (PNG path, pixel size) pairs.
    out
        ICO file to write.
    """
    datas = [p.read_bytes() for p, _ in pngs]
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = ICO_HEADER_BYTES + ICO_ENTRY_BYTES * len(pngs)
    entries = b""
    for (_, s), data in zip(pngs, datas, strict=True):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    out.write_bytes(head + entries + b"".join(datas))


def main() -> None:
    """Write the tab icons, home-screen icon and profile images."""
    SITE.mkdir(parents=True, exist_ok=True)
    tab = svg()
    (SITE / "favicon.svg").write_text(tab, encoding="utf-8")
    with tempfile.TemporaryDirectory() as d:
        pngs = []
        for s in (16, 32, 48):
            p = Path(d) / f"{s}.png"
            render_png(tab, s, p)
            pngs.append((p, s))
        write_ico(pngs, SITE / "favicon.ico")
    # iOS rounds the corners itself and shows transparency as black, so use a full square.
    render_png(svg(number=True, rounded=False), 180, SITE / "apple-touch-icon.png")
    print("wrote favicon.svg, favicon.ico, apple-touch-icon.png to", SITE)
    BRAND.mkdir(parents=True, exist_ok=True)
    profile = svg(number=True, rounded=False, circle_safe=True)
    (BRAND / "profile.svg").write_text(profile, encoding="utf-8")
    for s in (400, 1024, 2048):
        render_png(profile, s, BRAND / f"profile-{s}.png")
    print("wrote profile.svg and profile-400/1024/2048.png to", BRAND)


if __name__ == "__main__":
    main()
