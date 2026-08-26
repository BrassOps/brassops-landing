#!/usr/bin/env python3
"""
Quarter page magazine ad, built at 300 dpi with bleed.

Trim   4.25 x 5.5 in   (quarter of a US Letter page, portrait)
Bleed  0.125 in all round
Safe   0.25 in inside trim

Rendered rather than laid out in a page tool so the output is exact and
font independent: whatever appears in the PNG is what prints.
"""
from PIL import Image, ImageDraw, ImageFont
import segno

DPI = 300
def IN(x): return int(round(x * DPI))

TRIM_W, TRIM_H = 4.25, 5.5
BLEED = 0.125
SAFE = 0.25

W, H = IN(TRIM_W + BLEED * 2), IN(TRIM_H + BLEED * 2)
BX, BY = IN(BLEED), IN(BLEED)                       # trim origin
SX, SY = BX + IN(SAFE), BY + IN(SAFE)               # safe origin
SW = IN(TRIM_W) - IN(SAFE) * 2                      # safe width
SAFE_BOTTOM = BY + IN(TRIM_H) - IN(SAFE)

BLACK = (10, 10, 10)
WHITE = (245, 245, 245)
RED = (239, 68, 68)
GREY = (150, 150, 156)
DIM = (95, 95, 102)

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

img = Image.new("RGB", (W, H), BLACK)
d = ImageDraw.Draw(img)

def font(path, size): return ImageFont.truetype(path, size)

def measure(text, f):
    b = d.textbbox((0, 0), text, font=f)
    return b[2] - b[0], b[3] - b[1]

def fit(text, path, target_w, start=200):
    """Largest size at which text fits target_w."""
    s = start
    while s > 8:
        if measure(text, font(path, s))[0] <= target_w:
            return s
        s -= 1
    return 8

def tracked(draw, xy, text, f, fill, track=0):
    """Draw text with manual letterspacing. Returns width drawn."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + track
    return x - xy[0] - (track if text else 0)

def tracked_width(draw, text, f, track=0):
    w = sum(draw.textlength(c, font=f) for c in text)
    return w + track * max(0, len(text) - 1)

# ── Background motif ────────────────────────────────────────────────────
# Concentric rings bleeding off the right edge, echoing the site's crosshair
# field. Drawn onto the background so it never dulls the accent colours.
_cx, _cy = int(W * 1.02), int(H * 0.74)
for _r_in, _col in [(2.15, (24, 24, 27)), (1.72, (30, 24, 26)),
                    (1.30, (38, 25, 27)), (0.92, (47, 26, 29)),
                    (0.58, (58, 27, 31))]:
    _r = IN(_r_in)
    d.ellipse([_cx - _r, _cy - _r, _cx + _r, _cy + _r], outline=_col, width=IN(0.020))

# ── Full bleed accents ──────────────────────────────────────────────────
d.rectangle([0, 0, W, IN(0.055)], fill=RED)                    # top bar
d.rectangle([0, H - IN(0.02), W, H], fill=(26, 26, 28))        # base shadow

y = SY + IN(0.10)

# ── Eyebrow ─────────────────────────────────────────────────────────────
f_eye = font(BOLD, 30)
tracked(d, (SX, y), "FOR FIREARMS INSTRUCTORS", f_eye, RED, track=6)
y += IN(0.32)

# ── Headline. Sized so the longest line fills the safe width. ───────────
head = ["YOU FIXED", "THE FLINCH.", "THE RECORD", "SAYS NOTHING."]
hsize = min(fit(l, BOLD, SW, start=220) for l in head)
f_head = font(BOLD, hsize)
line_h = int(hsize * 1.02)

for i, line in enumerate(head):
    # Final line carries the turn, so it takes the accent colour.
    d.text((SX, y), line, font=f_head, fill=RED if i == 3 else WHITE)
    y += line_h

y += IN(0.16)
d.rectangle([SX, y, SX + IN(0.62), y + IN(0.035)], fill=RED)   # rule
y += IN(0.30)

# ── Body ────────────────────────────────────────────────────────────────
f_body = font(REG, 43)
body = [
    "BrassOps records the coaching, not",
    "just the score. Photograph a target",
    "and get the drill that fixes the group.",
]
for line in body:
    d.text((SX, y), line, font=f_body, fill=(205, 205, 210))
    y += int(43 * 1.40)

# ── QR block, anchored to the bottom ────────────────────────────────────
QR_PX = IN(1.02)
qr = segno.make("https://brassops.com/demo", error="h")
import io
_buf = io.BytesIO()
qr.save(_buf, kind="png", scale=20, border=2, dark="#000000", light="#ffffff")
_buf.seek(0)
qr_img = Image.open(_buf).convert("RGB").resize((QR_PX, QR_PX), Image.NEAREST)

foot_h = IN(0.42)
qr_y = SAFE_BOTTOM - foot_h - QR_PX - IN(0.20)

pad = IN(0.055)
d.rectangle([SX - pad, qr_y - pad, SX + QR_PX + pad, qr_y + QR_PX + pad], fill=WHITE)
img.paste(qr_img, (SX, qr_y))

tx = SX + QR_PX + IN(0.26)
f_cta = font(BOLD, 44)
f_sub = font(REG, 31)
d.text((tx, qr_y + IN(0.02)), "SCAN FOR", font=f_cta, fill=WHITE)
d.text((tx, qr_y + IN(0.02) + int(44 * 1.12)), "A DEMO", font=f_cta, fill=WHITE)
d.text((tx, qr_y + IN(0.02) + int(44 * 2.30)), "brassops.com/demo", font=f_sub, fill=GREY)

# Booth number. Replace the underscores before sending to the printer.
f_booth = font(BOLD, 36)
booth_y = qr_y + QR_PX - IN(0.20)
bw = tracked_width(d, "BOOTH ____", f_booth, 3)
d.rectangle([tx - IN(0.045), booth_y - IN(0.045),
             tx + bw + IN(0.075), booth_y + IN(0.20)],
            outline=RED, width=IN(0.012))
tracked(d, (tx + IN(0.015), booth_y), "BOOTH ____", f_booth, RED, track=3)

# ── Footer wordmark ─────────────────────────────────────────────────────
f_mark = font(BOLD, 52)
mark_y = SAFE_BOTTOM - IN(0.235)
d.line([SX, mark_y - IN(0.14), SX + SW, mark_y - IN(0.14)], fill=(48, 48, 52), width=3)
w1 = d.textlength("Brass", font=f_mark)
d.text((SX, mark_y), "Brass", font=f_mark, fill=WHITE)
d.text((SX + w1, mark_y), "Ops", font=f_mark, fill=RED)

f_tag = font(REG, 27)
tag = "Firearms qualification, training, and records"
d.text((SX + SW - d.textlength(tag, font=f_tag), mark_y + IN(0.055)),
       tag, font=f_tag, fill=DIM)

img.save("brassops-quarter-page-ad.png", dpi=(DPI, DPI))
img.convert("CMYK").save("brassops-quarter-page-ad-CMYK.jpg", dpi=(DPI, DPI), quality=97)

# Trim-only version for printers that do not want bleed.
img.crop((BX, BY, BX + IN(TRIM_W), BY + IN(TRIM_H))).save(
    "brassops-quarter-page-ad-NOBLEED.png", dpi=(DPI, DPI))

print(f"canvas {W}x{H}px  headline {hsize}px  qr {QR_PX}px")
