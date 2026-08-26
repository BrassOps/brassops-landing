#!/usr/bin/env python3
"""
Quarter page magazine ad, 300 dpi with bleed.

Trim 4.25 x 5.5 in, 0.125 in bleed, 0.25 in safe margin.

The hero is the product doing its job: a photographed target with every shot
detected, the group diagnosed, and a drill prescribed. An instructor reads a
shot group faster than they read a headline, so the picture carries the pitch
and the type stays short.
"""
from PIL import Image, ImageDraw, ImageFont
import io
import segno

DPI = 300
def IN(x): return int(round(x * DPI))

TRIM_W, TRIM_H, BLEED, SAFE = 4.25, 5.5, 0.125, 0.25
W, H = IN(TRIM_W + BLEED * 2), IN(TRIM_H + BLEED * 2)
BX, BY = IN(BLEED), IN(BLEED)
SX, SY = BX + IN(SAFE), BY + IN(SAFE)
SW = IN(TRIM_W) - IN(SAFE) * 2
SB = BY + IN(TRIM_H) - IN(SAFE)

BLACK = (10, 10, 10)
PANEL = (22, 22, 25)
WHITE = (247, 247, 248)
RED = (239, 68, 68)
GREEN = (34, 197, 94)
GREY = (150, 150, 158)
DIM = (98, 98, 106)
PAPER = (196, 196, 202)

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

img = Image.new("RGB", (W, H), BLACK)
d = ImageDraw.Draw(img)
F = lambda p, s: ImageFont.truetype(p, s)


def condensed(text, size, fill, squeeze=0.82):
    """No condensed face is installed, so squeeze a wide one horizontally.
    Gives the headline a technical feel closer to the brand face."""
    f = F(BOLD, size)
    w = int(d.textlength(text, font=f)) + size
    h = int(size * 1.45)
    tmp = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((0, 0), text, font=f, fill=fill + (255,))
    return tmp.resize((max(1, int(w * squeeze)), h), Image.LANCZOS)


def fit_condensed(text, target_w, squeeze=0.82, start=190):
    s = start
    while s > 10:
        if d.textlength(text, font=F(BOLD, s)) * squeeze <= target_w:
            return s
        s -= 1
    return 10


def tracked(draw, xy, text, f, fill, track=0):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + track
    return x - xy[0]


def tracked_w(text, f, track=0):
    return sum(d.textlength(c, font=f) for c in text) + track * max(0, len(text) - 1)


# ── Accents ─────────────────────────────────────────────────────────────
d.rectangle([0, 0, W, IN(0.055)], fill=RED)

y = SY + IN(0.06)

# ── Eyebrow ─────────────────────────────────────────────────────────────
tracked(d, (SX, y), "FOR FIREARMS INSTRUCTORS", F(BOLD, 29), RED, track=6)
y += IN(0.30)

# ── Headline, two lines ─────────────────────────────────────────────────
head = ["YOU SAW THE FLINCH.", "NOW THE RECORD DOES."]
hs = min(fit_condensed(l, SW) for l in head)
for i, line in enumerate(head):
    layer = condensed(line, hs, WHITE if i == 0 else RED)
    img.paste(layer, (SX, y), layer)
    y += int(hs * 1.06)

y += IN(0.14)

# ── Hero: the analysis view ─────────────────────────────────────────────
PANEL_H = IN(1.80)
panel_top = y
d.rectangle([SX, panel_top, SX + SW, panel_top + PANEL_H], fill=PANEL)
d.rectangle([SX, panel_top, SX + IN(0.035), panel_top + PANEL_H], fill=RED)

# Target, left side of the panel
tcx = SX + IN(0.88)
tcy = panel_top + PANEL_H // 2
R = IN(0.66)

for i, rr in enumerate([1.0, 0.76, 0.53, 0.31]):
    r = int(R * rr)
    d.ellipse([tcx - r, tcy - r, tcx + r, tcy + r],
              outline=(128, 128, 136) if i == 0 else (99, 99, 107), width=IN(0.010))
r = int(R * 0.31)
d.ellipse([tcx - r, tcy - r, tcx + r, tcy + r], fill=(38, 38, 42))

# Detected shots. Deliberately grouped low and left: textbook anticipation
# for a right handed shooter, which every instructor reads instantly. Eight
# sit inside the dashed group ring and two do not, so the picture and the
# "8 of 10 low left" readout agree if anyone stops to count.
shots = [(-0.30, 0.26), (-0.44, 0.38), (-0.22, 0.44), (-0.38, 0.16),
         (-0.52, 0.29), (-0.26, 0.34), (-0.41, 0.49), (-0.33, 0.55),
         (0.05, -0.08), (0.16, 0.04)]
SPREAD = 1.10
hole = IN(0.038)
for sx_, sy_ in shots:
    px, py = tcx + int(sx_ * R * SPREAD), tcy + int(sy_ * R * SPREAD)
    d.ellipse([px - hole, py - hole, px + hole, py + hole], fill=(6, 6, 7))
    d.ellipse([px - hole, py - hole, px + hole, py + hole], outline=RED, width=IN(0.012))

# Detected group boundary, drawn as a dashed ring
gx = tcx + int(-0.32 * R * SPREAD)
gy = tcy + int(0.35 * R * SPREAD)
grx, gry = IN(0.33), IN(0.30)
for a in range(0, 360, 14):
    d.arc([gx - grx, gy - gry, gx + grx, gy + gry], a, a + 8, fill=RED, width=IN(0.010))

# Readout, right side of the panel
rx = SX + IN(1.78)
ry = panel_top + IN(0.26)

f_lbl = F(BOLD, 23)
f_sm = F(REG, 27)

tracked(d, (rx, ry), "DIAGNOSIS", f_lbl, DIM, track=4)
ry += IN(0.15)
lay = condensed("ANTICIPATION", 52, RED, squeeze=0.88)
img.paste(lay, (rx, ry), lay)
ry += IN(0.26)
d.text((rx, ry), "8 of 10 low left", font=f_sm, fill=PAPER)
ry += IN(0.29)

tracked(d, (rx, ry), "PRESCRIBED DRILL", f_lbl, DIM, track=4)
ry += IN(0.15)
lay = condensed("BALL AND DUMMY", 42, WHITE, squeeze=0.88)
img.paste(lay, (rx, ry), lay)
ry += IN(0.24)

d.ellipse([rx, ry + IN(0.015), rx + IN(0.065), ry + IN(0.08)], fill=GREEN)
d.text((rx + IN(0.105), ry), "Logged to the file", font=f_sm, fill=GREEN)

y = panel_top + PANEL_H + IN(0.19)

# ── One thought, two lines ──────────────────────────────────────────────
f_body = F(REG, 38)
d.text((SX, y), "Photograph the target. Brass Ops finds every", font=f_body, fill=(206, 206, 212))
d.text((SX, y + int(38 * 1.36)), "shot, names the fault, and records the fix.", font=f_body, fill=(206, 206, 212))

# ── QR block ────────────────────────────────────────────────────────────
QR = IN(0.88)
buf = io.BytesIO()
segno.make("https://brassops.com/demo", error="h").save(
    buf, kind="png", scale=20, border=2, dark="#000000", light="#ffffff")
buf.seek(0)
qr_img = Image.open(buf).convert("RGB").resize((QR, QR), Image.NEAREST)

foot_h = IN(0.40)
qy = SB - foot_h - QR - IN(0.14)
pad = IN(0.05)
d.rectangle([SX - pad, qy - pad, SX + QR + pad, qy + QR + pad], fill=WHITE)
img.paste(qr_img, (SX, qy))

tx = SX + QR + IN(0.24)
lay = condensed("SCAN FOR A DEMO", 40, WHITE, squeeze=0.86)
img.paste(lay, (tx, qy + IN(0.005)), lay)
d.text((tx, qy + IN(0.235)), "brassops.com/demo", font=F(REG, 29), fill=GREY)

f_booth = F(BOLD, 33)
by_ = qy + QR - IN(0.26)
bw = tracked_w("BOOTH ____", f_booth, 3)
d.rectangle([tx - IN(0.04), by_ - IN(0.04), tx + bw + IN(0.07), by_ + IN(0.185)],
            outline=RED, width=IN(0.011))
tracked(d, (tx + IN(0.015), by_), "BOOTH ____", f_booth, RED, track=3)

# ── Footer ──────────────────────────────────────────────────────────────
f_mark = F(BOLD, 48)
my = SB - IN(0.225)
d.line([SX, my - IN(0.12), SX + SW, my - IN(0.12)], fill=(46, 46, 50), width=3)
w1 = d.textlength("Brass", font=f_mark)
d.text((SX, my), "Brass", font=f_mark, fill=WHITE)
d.text((SX + w1, my), "Ops", font=f_mark, fill=RED)

f_tag = F(REG, 25)
tag = "Firearms qualification, training, and records"
d.text((SX + SW - d.textlength(tag, font=f_tag), my + IN(0.05)), tag, font=f_tag, fill=DIM)

img.save("brassops-quarter-page-ad.png", dpi=(DPI, DPI))
img.convert("CMYK").save("brassops-quarter-page-ad-CMYK.jpg", dpi=(DPI, DPI), quality=97)
img.crop((BX, BY, BX + IN(TRIM_W), BY + IN(TRIM_H))).save(
    "brassops-quarter-page-ad-NOBLEED.png", dpi=(DPI, DPI))

print(f"{W}x{H}px  headline {hs}px  panel {PANEL_H}px  qr {QR}px")
