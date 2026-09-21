#!/usr/bin/env python3
"""
Generate the site's QR codes as SVG (vector, for print) and PNG (for screens).

Each target produces two files:
  <slug>-qr.svg/.png       bare code, drop into any layout
  <slug>-qr-card.svg/.png  branded card with wordmark, prompt, and the URL

The URLs use the bare brassops.com host that the sitemap and canonical tags
use. Encoding www. would cost modules for no benefit and add a redirect hop
before the page loads.

Error correction is H (~30% recoverable) so a code survives a scuffed badge,
a fold, or a poor phone camera.

  python3 qr/build_qr.py
"""
import io
import os
from urllib.parse import urlencode

import segno
from PIL import Image

RED = "#ef4444"
INK = "#0a0a0a"

# A QR scan carries no HTTP referrer, so without a tag every one of these
# lands in Google Analytics as plain "direct" traffic, indistinguishable
# from someone typing the URL in by hand or from a bookmark. UTM parameters
# are the fix: GA reads them automatically, no GA-side setup required. The
# printed card still shows the clean URL; only the encoded payload carries
# the tag. See utm_content in TARGETS to tell one physical code from another
# in GA even when several point at the same page.
UTM_SOURCE = "qr"
UTM_MEDIUM = "qr_code"
UTM_CAMPAIGN = "qr_codes"


def tagged(url, content):
    qs = urlencode({
        "utm_source": UTM_SOURCE,
        "utm_medium": UTM_MEDIUM,
        "utm_campaign": UTM_CAMPAIGN,
        "utm_content": content,
    })
    return f"{url}?{qs}"


# slug, base url (shown on the card), prompt, utm_content (what this scan
# shows up as in GA's Acquisition reports)
TARGETS = [
    ("brassops-contact", "https://brassops.com/contact", "Scan to get in touch", "contact"),
    ("brassops-why", "https://brassops.com/why-brassops", "Scan to see why agencies switch", "why-brassops"),
    # Public lead form only: no stats, no list of prior leads. That view lives
    # behind /booth, which is staff-only and separately gated by a key.
    ("brassops-demo", "https://brassops.com/demo", "Scan to see it in action", "demo"),
]

MODULE = 12      # SVG units per QR module
QUIET = 4        # quiet zone in modules, 4 is the spec minimum
PNG_SCALE = 20   # PNG pixels per module


def matrix(url):
    """Module rows as lists of 0/1, quiet zone already stripped."""
    qr = segno.make(url, error="h")
    rows = [list(r) for r in qr.matrix]
    return rows, len(rows)


def modules_svg(rows, x0, y0, size):
    """QR modules as one <g> of rects. Runs of dark modules are merged into a
    single rect per run, which keeps the file small and stops hairline seams
    from showing between adjacent squares in some PDF renderers."""
    out = []
    for r, row in enumerate(rows):
        c = 0
        while c < len(row):
            if not row[c]:
                c += 1
                continue
            start = c
            while c < len(row) and row[c]:
                c += 1
            out.append(
                f'<rect x="{x0 + start * size}" y="{y0 + r * size}" '
                f'width="{(c - start) * size}" height="{size}"/>'
            )
    return f'<g fill="{INK}">' + "".join(out) + "</g>"


def write_plain(slug, url):
    rows, n = matrix(url)
    side = (n + QUIET * 2) * MODULE
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{side}" height="{side}" '
        f'viewBox="0 0 {side} {side}">'
        f'<rect width="{side}" height="{side}" fill="#ffffff"/>'
        + modules_svg(rows, QUIET * MODULE, QUIET * MODULE, MODULE)
        + "</svg>"
    )
    with open(f"{slug}-qr.svg", "w") as f:
        f.write(svg)

    buf = io.BytesIO()
    segno.make(url, error="h").save(
        buf, kind="png", scale=PNG_SCALE, border=QUIET, dark=INK, light="#ffffff"
    )
    buf.seek(0)
    Image.open(buf).convert("RGB").save(f"{slug}-qr.png", dpi=(300, 300))
    return n


def fit_size(text, max_w, start, font_path="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
    """Largest size at or below `start` that keeps `text` inside `max_w`.

    Measured against DejaVu, the fallback a rasterizer actually reaches for
    when Barlow is absent. Barlow is the narrower face, so a line that fits
    here fits on a machine that has the real font too.
    """
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    s = start
    while s > 8 and d.textlength(text, font=ImageFont.truetype(font_path, s)) > max_w:
        s -= 1
    return s


def write_card(slug, encoded_url, display_url, prompt):
    rows, n = matrix(encoded_url)
    code = (n + QUIET * 2) * MODULE
    pad = 0
    w = code
    # Room below the code for wordmark, prompt line, and the URL.
    h = code + 210

    mid = w / 2
    # The card shows the clean, human-legible URL. The UTM tag lives only in
    # what the QR pattern above it actually encodes.
    shown_url = display_url.replace("https://", "")
    # Keep both lines inside a side margin so a long prompt cannot run to the
    # card edge, which reads as a crop rather than a design.
    inner = w * 0.84
    ps = fit_size(prompt, inner, 28)
    us = fit_size(shown_url, inner, 24)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">'
        f'<rect width="{w}" height="{h}" fill="#ffffff"/>'
        + modules_svg(rows, QUIET * MODULE + pad, QUIET * MODULE, MODULE)
        # The wordmark is two text elements meeting at the midpoint rather than
        # one element with a tspan, because tspan advance widths render with a
        # visible gap in some rasterizers.
        + f'<text x="{mid}" y="{code + 46}" text-anchor="end" '
          f'font-family="Rajdhani, Arial, sans-serif" font-size="46" '
          f'font-weight="700" fill="{INK}">Brass</text>'
        + f'<text x="{mid}" y="{code + 46}" text-anchor="start" '
          f'font-family="Rajdhani, Arial, sans-serif" font-size="46" '
          f'font-weight="700" fill="{RED}">Ops</text>'
        + f'<text x="{mid}" y="{code + 90}" text-anchor="middle" '
          f'font-family="Barlow, Arial, sans-serif" font-size="{ps}" '
          f'fill="#444444">{prompt}</text>'
        + f'<text x="{mid}" y="{code + 130}" text-anchor="middle" '
          f'font-family="Barlow, Arial, sans-serif" font-size="{us}" '
          f'fill="#777777">{shown_url}</text>'
        + "</svg>"
    )
    with open(f"{slug}-qr-card.svg", "w") as f:
        f.write(svg)
    return svg


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    import cairosvg

    for slug, url, prompt, utm_content in TARGETS:
        encoded = tagged(url, utm_content)
        n = write_plain(slug, encoded)
        svg = write_card(slug, encoded, url, prompt)
        cairosvg.svg2png(
            bytestring=svg.encode(),
            write_to=f"{slug}-qr-card.png",
            output_width=1200,
        )
        print(f"{slug}: {n}x{n} modules  {encoded}")


if __name__ == "__main__":
    main()
