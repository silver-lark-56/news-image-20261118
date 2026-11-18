#!/usr/bin/env python3
"""news-image-20261118 v4 — one-page newspaper front page for
Wednesday 18 November 2026. 47 verified stories, 13 illustrated.

Pure standard-library program: draws the whole page with vector
primitives + embedded bitmap fonts into a 2x supersampled buffer,
downsamples to 1024x1024, and writes a PNG with a hand-rolled encoder
(zlib). No network, no files read, no randomness — two runs produce
byte-identical output.

v4 changes vs v3: illustrations ONLY — the 3 hero scenes and the 10
grid icons are redrawn as richer multi-element scenes (ships, jets,
arches, charts, maps, vehicles); every story, fact, headline, deck,
label position, font and layout coordinate is unchanged from v3.

v3 changes vs v2: real bitmap typography (Liberation Serif/Sans,
rasterized at build time, embedded as a compressed blob); 47 stories
(3 heroes + 10 grid + 34 briefs); hero 3 is Trump's tarmac welcome;
grid adds the 141-drone night and the Ethiopia-Eritrea build-up;
COP31 sharpened to the 35x35 pledge; DATE CHECK strip in the footer.
"""

import base64
import math
import os
import struct
import zlib

W, H = 1024, 1024
SS = 2
BW, BH = W * SS, H * SS

PAPER = (247, 242, 231)
NAVY = (20, 38, 74)
NAVY2 = (42, 58, 95)
GOLD = (201, 162, 39)
GOLD_DK = (150, 116, 22)
INK = (28, 28, 28)
GREY = (96, 94, 86)
RED = (179, 38, 30)
WHITE = (255, 255, 255)
BORDER = (200, 192, 170)
SEA = (191, 217, 232)
SKY = (220, 233, 242)
WATER = (127, 168, 201)
SAND = (232, 217, 176)
LAND = (214, 196, 150)
DARK = (52, 58, 66)

buf = bytearray(BW * BH * 3)


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def rect(x0, y0, x1, y1, color):
    """Filled rectangle, final-pixel coords (x1/y1 exclusive)."""
    ax = _clip(int(round(x0 * SS)), 0, BW)
    bx = _clip(int(round(x1 * SS)), 0, BW)
    ay = _clip(int(round(y0 * SS)), 0, BH)
    by = _clip(int(round(y1 * SS)), 0, BH)
    if bx <= ax or by <= ay:
        return
    row = bytes(color) * (bx - ax)
    for y in range(ay, by):
        o = (y * BW + ax) * 3
        buf[o:o + len(row)] = row


def frame(x0, y0, x1, y1, color, w=1):
    rect(x0, y0, x1, y0 + w, color)
    rect(x0, y1 - w, x1, y1, color)
    rect(x0, y0, x0 + w, y1, color)
    rect(x1 - w, y0, x1, y1, color)


def circle(cx, cy, r, color, fill=True, w=1.0):
    """Circle, final-pixel coords."""
    bcx, bcy, br = cx * SS, cy * SS, r * SS
    if fill:
        y0 = int(max(0, bcy - br))
        y1 = int(min(BH - 1, bcy + br))
        for y in range(y0, y1 + 1):
            dy = y - bcy
            rem = br * br - dy * dy
            if rem < 0:
                continue
            dx = rem ** 0.5
            ax = int(max(0, bcx - dx))
            bx = int(min(BW, bcx + dx + 1))
            if bx > ax:
                row = bytes(color) * (bx - ax)
                o = (y * BW + ax) * 3
                buf[o:o + len(row)] = row
    else:
        n = max(24, int(2 * math.pi * br))
        prev = None
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            p = (cx + r * math.cos(a), cy + r * math.sin(a))
            if prev is not None:
                line(prev[0], prev[1], p[0], p[1], color, w)
            prev = p


def fill_poly(points, color):
    """Scanline polygon fill, final-pixel coords."""
    pts = [(x * SS, y * SS) for x, y in points]
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = int(max(0, min(ys)))
    y1 = int(min(BH - 1, max(ys)))
    n = len(pts)
    for y in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x0, yy0 = pts[i]
            x1, yy1 = pts[(i + 1) % n]
            if (yy0 <= y < yy1) or (yy1 <= y < yy0):
                t = (y - yy0) / (yy1 - yy0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            ax = int(max(0, xs[j]))
            bx = int(min(BW, xs[j + 1] + 1))
            if bx > ax:
                row = bytes(color) * (bx - ax)
                o = (y * BW + ax) * 3
                buf[o:o + len(row)] = row


def line(x0, y0, x1, y1, color, w=1.0):
    """Thick line with round caps, final-pixel coords."""
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 0.01:
        circle(x0, y0, w / 2, color)
        return
    nx, ny = -dy / length * w / 2, dx / length * w / 2
    fill_poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
               (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color)
    circle(x0, y0, w / 2, color)
    circle(x1, y1, w / 2, color)


def polyline(points, color, w=1.0):
    for a, b in zip(points, points[1:]):
        line(a[0], a[1], b[0], b[1], color, w)


def dashed_line(x0, y0, x1, y1, color, w=1.0, dash=6, gap=4):
    length = math.hypot(x1 - x0, y1 - y0)
    if length < 0.01:
        return
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    d = 0.0
    while d < length:
        e = min(d + dash, length)
        line(x0 + dx * d, y0 + dy * d, x0 + dx * e, y0 + dy * e, color, w)
        d = e + gap


def burst(cx, cy, r, color):
    for i in range(8):
        a = math.pi * i / 4
        line(cx, cy, cx + r * math.cos(a), cy + r * math.sin(a), color, 2.0)
    circle(cx, cy, r * 0.35, color)


def downsample():
    out = bytearray(W * H * 3)
    for y in range(H):
        r0 = (y * 2) * BW * 3
        r1 = (y * 2 + 1) * BW * 3
        for x in range(W):
            o0 = r0 + x * 6
            o1 = r1 + x * 6
            oo = (y * W + x) * 3
            out[oo] = (buf[o0] + buf[o0 + 3] + buf[o1] + buf[o1 + 3] + 2) // 4
            out[oo + 1] = (buf[o0 + 1] + buf[o0 + 4] + buf[o1 + 1] + buf[o1 + 4] + 2) // 4
            out[oo + 2] = (buf[o0 + 2] + buf[o0 + 5] + buf[o1 + 2] + buf[o1 + 5] + 2) // 4
    return out


def encode_png(rgb, w, h):
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", comp)
            + chunk(b"IEND", b""))


# ---------------------------------------------------------------------------
# Bitmap font engine.
# Glyphs were rasterized at build time from the Liberation fonts
# (Serif Bold for headlines, Sans Bold/Regular for the rest) with PIL,
# thresholded to 1 bit at 2x the em size, and packed into FONT_BLOB
# (zlib + base64). At runtime only the standard library is used.
# A "size" is the em size in final pixels; cap height is ~0.73 * size.
# Blob format: u8 n_sets; per set: u8 name_len, name, u8 em,
# u16 ascent, u16 descent, u16 n_glyphs; per glyph: u16 codepoint,
# u16 advance, u16 w, u16 h, i16 xoff, i16 yoff, u16 data_len, data
# (1 bit/px, MSB first, row-major, in buffer pixels).
# ---------------------------------------------------------------------------

# Bitmap font blob (Liberation Serif Bold / Sans, rasterized at
# build time with PIL; 1-bit glyphs at 2x em size).
# Decoded at runtime with stdlib base64 + zlib.
FONT_BLOB = (
    "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"
)

_FONT_SETS = {
    ("serif", 60): "serif60", ("serif", 25): "serif25",
    ("serif", 19): "serif19",
    ("bold", 22): "sans22", ("bold", 18): "sans18", ("bold", 15): "sans15",
    ("bold", 12): "sans12", ("bold", 11): "sans11",
    ("reg", 15): "sansr15", ("reg", 14): "sansr14", ("reg", 12): "sansr12",
}


def _load_fonts():
    raw = zlib.decompress(base64.b64decode("".join(FONT_BLOB)))
    fonts = {}
    i = 0
    n_sets = raw[i]
    i += 1
    for _ in range(n_sets):
        nl = raw[i]
        i += 1
        name = raw[i:i + nl].decode("ascii")
        i += nl
        em = raw[i]
        i += 1
        ascent, descent, n = struct.unpack_from(">HHH", raw, i)
        i += 6
        glyphs = {}
        for _ in range(n):
            cp, adv, w, h, xo, yo, dl = struct.unpack_from(">HHHHhhH", raw, i)
            i += 14
            data = raw[i:i + dl]
            i += dl
            runs = []
            rb = (w + 7) // 8
            for yy in range(h):
                xx = 0
                base = yy * rb
                while xx < w:
                    if data[base + xx // 8] & (0x80 >> (xx % 8)):
                        x0 = xx
                        xx += 1
                        while xx < w and data[base + xx // 8] & (0x80 >> (xx % 8)):
                            xx += 1
                        runs.append((yy, x0, xx - x0))
                    else:
                        xx += 1
            glyphs[cp] = (adv, xo, yo, runs)
        fonts[name] = (em, ascent, descent, glyphs)
    return fonts


FONTS = _load_fonts()


def _font_for(size, bold, font):
    if font == "serif":
        key = ("serif", size)
    elif bold:
        key = ("bold", size)
    else:
        key = ("reg", size)
    name = _FONT_SETS.get(key)
    if name is None:  # nearest size in the same style (safety net)
        style = key[0]
        cands = [(abs(s - size), n) for (st, s), n in _FONT_SETS.items()
                 if st == style]
        name = min(cands)[1]
    return FONTS[name]


def text_width(s, size, bold=False, font="sans"):
    _em, _a, _d, glyphs = _font_for(size, bold, font)
    total = 0
    for ch in s:
        g = glyphs.get(ord(ch))
        if g:
            total += g[0]
    return total / SS


def _blit_run(bx, by, w, color):
    """Write one horizontal run of buffer pixels (buffer coords)."""
    if by < 0 or by >= BH or w <= 0:
        return
    ax = bx if bx > 0 else 0
    ex = bx + w if bx + w < BW else BW
    if ex <= ax:
        return
    o = (by * BW + ax) * 3
    buf[o:o + (ex - ax) * 3] = bytes(color) * (ex - ax)


def draw_text(x, y, s, size, color, bold=False, align="left", font="sans"):
    """Draw text; (x, y) is the top-left of the em box. Size is em size."""
    _em, _a, _d, glyphs = _font_for(size, bold, font)
    total = text_width(s, size, bold, font)
    if align == "center":
        x -= total / 2
    elif align == "right":
        x -= total
    pen = int(round(x * SS))
    top = int(round(y * SS))
    for ch in s:
        g = glyphs.get(ord(ch))
        if g:
            adv, xo, yo, runs = g
            gx = pen + xo
            gy = top + yo
            for dy, dx, w in runs:
                _blit_run(gx + dx, gy + dy, w, color)
            pen += adv
    return total


def wrap_text(s, size, max_w, bold=False, font="sans"):
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size, bold, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(x, y, s, size, max_w, color, bold=False, lh=None,
                 font="sans"):
    if lh is None:
        lh = size * 1.35
    lines = wrap_text(s, size, max_w, bold, font)
    for ln in lines:
        draw_text(x, y, ln, size, color, bold=bold, font=font)
        y += lh
    return y, lines


def badge(x, y, n, r=None):
    """Number badge: navy circle with a white number, centred at (x, y)."""
    s = str(n)
    if r is None:
        r = 10 if len(s) == 1 else 12
    circle(x, y, r, NAVY)
    circle(x, y, r, WHITE, fill=False, w=1.0)
    draw_text(x, y - 7, s, 15, WHITE, bold=True, align="center")


# ---------------------------------------------------------------------------
# Illustrations — enriched vector scenes, one per story (v4).
# Hero illustrations are 318x88; grid icons are 190x54. All label
# strings and positions are unchanged from v3; only the drawn
# graphics around them are richer.
# ---------------------------------------------------------------------------

def _flag(x, y, code):
    """Small 26x16 flag on a pole; pole top at (x, y), pole runs down 70px."""
    line(x, y, x, y + 70, DARK, 2.0)
    if code == "CN":
        rect(x + 2, y, x + 28, y + 16, (222, 41, 16))
        circle(x + 9, y + 8, 2.5, GOLD)
        circle(x + 16, y + 5, 1.2, GOLD)
        circle(x + 18, y + 9, 1.2, GOLD)
        circle(x + 15, y + 12, 1.2, GOLD)
    elif code == "US":
        rect(x + 2, y, x + 28, y + 16, WHITE)
        for i in range(3):
            rect(x + 2, y + 2 + i * 5, x + 28, y + 4 + i * 5, (178, 34, 52))
        rect(x + 2, y, x + 12, y + 8, NAVY)
    elif code == "RU":
        rect(x + 2, y, x + 28, y + 5, WHITE)
        rect(x + 2, y + 5, x + 28, y + 11, (0, 87, 184))
        rect(x + 2, y + 11, x + 28, y + 16, (215, 0, 0))


def ill_gulf(x, y, w, h):
    rect(x, y, x + w, y + h, SEA)
    # darker strait channel between Iran and the Arabian shore
    fill_poly([(x + 150, y), (x + 190, y), (x + 250, y + 40),
               (x + 260, y + h), (x + 210, y + h), (x + 150, y + 40)],
              (168, 200, 222))
    # wave marks on open water
    for wx, wy in [(30, 40), (60, 30), (120, 62), (140, 74), (250, 34),
                   (285, 44), (200, 70), (130, 78)]:
        line(x + wx, y + wy, x + wx + 8, y + wy, (230, 240, 248), 1.0)
    fill_poly([(x, y + h), (x, y + 55), (x + 55, y + 50), (x + 95, y + 68),
               (x + 110, y + h)], SAND)
    fill_poly([(x + 160, y), (x + w, y), (x + w, y + 30), (x + 215, y + 28),
               (x + 185, y + 12)], SAND)
    # UAE / Oman shore, lower right — narrows the strait at Hormuz
    fill_poly([(x + 235, y + h), (x + 250, y + 62), (x + 285, y + 58),
               (x + w, y + 66), (x + w, y + h)], SAND)
    fill_poly([(x + 178, y + 38), (x + 208, y + 34), (x + 218, y + 42),
               (x + 192, y + 48), (x + 175, y + 45)], LAND)
    # oil tanker threading the strait
    fill_poly([(x + 228, y + 48), (x + 272, y + 48), (x + 278, y + 56),
               (x + 222, y + 56)], DARK)
    rect(x + 252, y + 40, x + 262, y + 48, WHITE)
    rect(x + 256, y + 36, x + 260, y + 40, RED)
    # US jet with contrail, upper left
    dashed_line(x + 32, y + 26, x + 52, y + 30, WHITE, 1.0, dash=4, gap=3)
    fill_poly([(x + 52, y + 30), (x + 72, y + 27), (x + 78, y + 30),
               (x + 72, y + 33)], (90, 100, 115))
    fill_poly([(x + 60, y + 29), (x + 64, y + 24), (x + 67, y + 29)],
              (90, 100, 115))
    fill_poly([(x + 60, y + 31), (x + 64, y + 36), (x + 67, y + 31)],
              (90, 100, 115))
    # radar dome on Bahrain (the US site the drones targeted)
    circle(x + 70, y + 64, 6, WHITE)
    rect(x + 64, y + 64, x + 76, y + 70, SAND)
    line(x + 70, y + 58, x + 70, y + 52, DARK, 1.5)
    circle(x + 70, y + 51, 1.5, RED)
    dashed_line(x + 205, y + 22, x + 150, y + 50, DARK, 1.0)
    dashed_line(x + 185, y + 18, x + 132, y + 40, DARK, 1.0)
    dashed_line(x + 180, y + 15, x + 112, y + 52, DARK, 1.0)
    fill_poly([(x + 150, y + 46), (x + 144, y + 54), (x + 156, y + 54)], DARK)
    fill_poly([(x + 132, y + 36), (x + 126, y + 44), (x + 138, y + 44)], DARK)
    fill_poly([(x + 112, y + 48), (x + 106, y + 56), (x + 118, y + 56)], DARK)
    circle(x + 88, y + 60, 4, RED)
    circle(x + 130, y + 42, 4, RED)
    # smoke plume over the Qeshm strike, fire core below it
    circle(x + 192, y + 32, 8, (150, 150, 150))
    circle(x + 202, y + 30, 6, (170, 170, 170))
    circle(x + 198, y + 24, 5, (150, 150, 150))
    circle(x + 198, y + 40, 5, (255, 120, 40))
    burst(x + 198, y + 40, 9, RED)
    draw_text(x + 40, y + 6, "GULF", 12, NAVY, bold=True)
    draw_text(x + 250, y + 8, "IRAN", 11, GREY, bold=True)
    draw_text(x + 168, y + 52, "QESHM", 11, INK, bold=True)
    draw_text(x + 58, y + 70, "BAHRAIN", 11, INK, bold=True)
    draw_text(x + 108, y + 20, "KUWAIT", 11, INK, bold=True)
    draw_text(x + 262, y + 70, "HORMUZ", 11, INK, bold=True)


def ill_kerch(x, y, w, h):
    rect(x, y, x + w, y + h, SKY)
    rect(x, y + 68, x + w, y + h, WATER)
    # distant shores at the horizon
    fill_poly([(x, y + 68), (x, y + 60), (x + 40, y + 62), (x + 50, y + 68)],
              LAND)
    fill_poly([(x + w - 50, y + 68), (x + w - 40, y + 62), (x + w, y + 60),
               (x + w, y + 68)], LAND)
    # clouds
    for ccx, ccy in [(60, 26), (252, 28)]:
        circle(x + ccx, y + ccy, 6, WHITE)
        circle(x + ccx + 9, y + ccy + 2, 5, WHITE)
        circle(x + ccx - 9, y + ccy + 2, 4, WHITE)
    # birds
    for bx, by in [(30, 30), (46, 24), (282, 34)]:
        line(x + bx - 4, y + by, x + bx, y + by - 3, DARK, 1.0)
        line(x + bx, y + by - 3, x + bx + 4, y + by, DARK, 1.0)
    rect(x + 8, y + 46, x + 140, y + 56, DARK)
    rect(x + 192, y + 46, x + w - 8, y + 56, DARK)
    for px in (36, 108, 216, 276):
        rect(x + px, y + 56, x + px + 8, y + 76, DARK)
    # road centrelines + tiny cars on the decks
    dashed_line(x + 12, y + 51, x + 136, y + 51, WHITE, 1.0, dash=6, gap=6)
    dashed_line(x + 196, y + 51, x + 304, y + 51, WHITE, 1.0, dash=6, gap=6)
    rect(x + 66, y + 41, x + 78, y + 46, RED)
    rect(x + 69, y + 38, x + 75, y + 41, RED)
    rect(x + 240, y + 41, x + 252, y + 46, WHITE)
    rect(x + 243, y + 38, x + 249, y + 41, WHITE)
    # the Crimea bridge's white arch over the left deck
    arch = []
    for i in range(25):
        a = math.pi + math.pi * i / 24
        arch.append((x + 74 + 26 * math.cos(a), y + 46 + 26 * math.sin(a)))
    polyline(arch, WHITE, 3.0)
    line(x + 58, y + 30, x + 58, y + 46, WHITE, 1.5)
    line(x + 90, y + 30, x + 90, y + 46, WHITE, 1.5)
    # fallen span + second chunk + splash foam
    fill_poly([(x + 150, y + 60), (x + 186, y + 76), (x + 179, y + 84),
               (x + 145, y + 68)], (120, 126, 134))
    fill_poly([(x + 196, y + 68), (x + 210, y + 78), (x + 202, y + 84),
               (x + 192, y + 74)], (120, 126, 134))
    circle(x + 150, y + 82, 4, WHITE)
    circle(x + 170, y + 84, 5, WHITE)
    circle(x + 186, y + 82, 4, WHITE)
    line(x + 152, y + 84, x + 158, y + 76, WHITE, 2.0)
    line(x + 164, y + 86, x + 164, y + 78, WHITE, 2.0)
    line(x + 176, y + 84, x + 170, y + 77, WHITE, 2.0)
    # boat in the strait, lower right
    fill_poly([(x + 250, y + 76), (x + 282, y + 76), (x + 276, y + 82),
               (x + 256, y + 82)], WHITE)
    line(x + 266, y + 76, x + 266, y + 66, DARK, 1.5)
    rect(x + 260, y + 70, x + 270, y + 76, NAVY2)
    # smoke plume + fire at the gap
    circle(x + 152, y + 38, 8, (150, 150, 150))
    circle(x + 166, y + 30, 10, (170, 170, 170))
    circle(x + 180, y + 38, 7, (150, 150, 150))
    circle(x + 160, y + 22, 6, (170, 170, 170))
    circle(x + 174, y + 24, 7, (150, 150, 150))
    circle(x + 166, y + 46, 5, (255, 120, 40))
    burst(x + 166, y + 50, 8, RED)
    draw_text(x + 40, y + 6, "KERCH STRAIT", 12, NAVY, bold=True)
    draw_text(x + w - 82, y + 6, "SPAN DOWN", 12, RED, bold=True)


def ill_shenzhen(x, y, w, h):
    """Air Force One on the tarmac at Shenzhen; Xi's rare airport welcome."""
    rect(x, y, x + w, y + h, SKY)
    # clouds
    for ccx, ccy in [(36, 12), (168, 10)]:
        circle(x + ccx, y + ccy, 5, WHITE)
        circle(x + ccx + 8, y + ccy + 2, 4, WHITE)
        circle(x + ccx - 8, y + ccy + 2, 3.5, WHITE)
    for bx, top, bw in [(6, 40, 20), (30, 28, 24), (58, 44, 18), (80, 32, 22),
                        (106, 46, 20), (130, 26, 26), (160, 42, 18),
                        (182, 30, 24), (210, 46, 20), (234, 36, 22),
                        (260, 28, 24), (288, 44, 22)]:
        rect(x + bx, y + top, x + bx + bw, y + 62, NAVY2)
    # lit windows on the towers
    for wx, wy in [(36, 50), (42, 56), (116, 50), (136, 50), (142, 56),
                   (188, 36), (266, 34), (272, 42), (12, 46), (216, 52)]:
        rect(x + wx, y + wy, x + wx + 3, y + wy + 4, GOLD)
    # control tower, right
    rect(x + 300, y + 20, x + 306, y + 62, NAVY2)
    rect(x + 296, y + 14, x + 310, y + 22, NAVY2)
    rect(x + 298, y + 16, x + 308, y + 20, GOLD)
    rect(x, y + 62, x + w, y + h, (168, 170, 164))
    rect(x, y + 62, x + w, y + 64, WHITE)
    # runway centreline dashes (under the carpet)
    dashed_line(x + 8, y + 80, x + 310, y + 80, WHITE, 1.0, dash=8, gap=8)
    # plane: fuselage, wings, tail, engines
    fill_poly([(x + 16, y + 40), (x + 24, y + 32), (x + 150, y + 32),
               (x + 168, y + 38), (x + 150, y + 46), (x + 24, y + 46)],
              WHITE)
    fill_poly([(x + 150, y + 32), (x + 162, y + 18), (x + 170, y + 18),
               (x + 170, y + 36)], (40, 80, 160))
    fill_poly([(x + 70, y + 44), (x + 96, y + 58), (x + 108, y + 58),
               (x + 92, y + 44)], (200, 205, 210))
    rect(x + 16, y + 40, x + 168, y + 43, (40, 80, 160))
    for wx in range(30, 146, 10):
        circle(x + wx, y + 36, 1.2, NAVY2)
    # cockpit windows + engines + wheels
    fill_poly([(x + 18, y + 36), (x + 26, y + 33), (x + 30, y + 36),
               (x + 22, y + 39)], NAVY2)
    rect(x + 78, y + 56, x + 86, y + 60, DARK)
    rect(x + 100, y + 56, x + 108, y + 60, DARK)
    rect(x + 96, y + 46, x + 102, y + 58, DARK)
    rect(x + 40, y + 46, x + 46, y + 58, DARK)
    circle(x + 43, y + 60, 2.5, DARK)
    circle(x + 99, y + 60, 2.5, DARK)
    # red carpet from the plane door, gold edging
    rect(x + 104, y + 46, x + 128, y + h, (179, 38, 30))
    line(x + 105, y + 46, x + 105, y + h, GOLD, 1.0)
    line(x + 127, y + 46, x + 127, y + h, GOLD, 1.0)
    # two figures greeting on the carpet
    circle(x + 111, y + 68, 2.5, (220, 180, 140))
    rect(x + 108, y + 71, x + 114, y + 82, NAVY)
    circle(x + 121, y + 68, 2.5, (220, 180, 140))
    rect(x + 118, y + 71, x + 124, y + 82, (60, 60, 60))
    line(x + 114, y + 74, x + 118, y + 74, (220, 180, 140), 1.5)
    # limousine waiting by the flags
    rect(x + 178, y + 68, x + 208, y + 76, (20, 20, 20))
    rect(x + 184, y + 64, x + 202, y + 68, (20, 20, 20))
    circle(x + 184, y + 76, 2.5, DARK)
    circle(x + 202, y + 76, 2.5, DARK)
    _flag(x + 212, y + 8, "CN")
    _flag(x + 256, y + 8, "US")
    draw_text(x + 8, y + 68, "SHENZHEN", 12, NAVY, bold=True)


def icon_capitol(x, y, w, h):
    rect(x, y, x + w, y + h, (232, 228, 216))
    # flag on the dome
    line(x + 32, y + 8, x + 32, y + 15, DARK, 1.5)
    rect(x + 33, y + 8, x + 43, y + 13, WHITE)
    rect(x + 33, y + 10, x + 43, y + 11, (178, 34, 52))
    rect(x + 33, y + 8, x + 37, y + 11, NAVY)
    circle(x + 32, y + 28, 13, NAVY2)
    rect(x + 17, y + 28, x + 47, y + 30, (232, 228, 216))
    rect(x + 19, y + 28, x + 45, y + 32, NAVY2)
    for cx in (21, 30, 39):
        rect(x + cx, y + 32, x + cx + 4, y + 44, NAVY2)
    rect(x + 17, y + 44, x + 47, y + 48, NAVY2)
    rect(x + 13, y + 48, x + 51, y + 51, NAVY2)
    # ground line
    rect(x + 8, y + 51, x + 182, y + 53, (200, 192, 170))
    rect(x + 76, y + 10, x + 116, y + 20, (40, 80, 160))
    rect(x + 76, y + 24, x + 108, y + 34, RED)
    # Alaska map with a star, top right
    fill_poly([(x + 150, y + 14), (x + 168, y + 8), (x + 184, y + 12),
               (x + 180, y + 22), (x + 164, y + 27), (x + 150, y + 22)],
              (40, 80, 160))
    burst(x + 166, y + 16, 4, GOLD)
    draw_text(x + 120, y + 8, "56", 15, NAVY, bold=True)
    draw_text(x + 112, y + 22, "44", 15, NAVY, bold=True)
    draw_text(x + 76, y + 38, "SENATE", 11, GREY, bold=True)
    draw_text(x + 156, y + 28, "AK", 11, NAVY, bold=True)


def icon_ebola(x, y, w, h):
    rect(x, y, x + w, y + h, (242, 232, 220))
    blob = [(x + 10, y + 8), (x + 28, y + 5), (x + 48, y + 10),
            (x + 60, y + 20), (x + 54, y + 36), (x + 38, y + 46),
            (x + 24, y + 42), (x + 14, y + 32), (x + 6, y + 22)]
    fill_poly(blob, (180, 140, 100))
    polyline(blob + [blob[0]], (140, 100, 60), 1.0)
    # outbreak epicentres: Bunia and Beni
    circle(x + 34, y + 18, 2.5, RED)
    circle(x + 34, y + 18, 4.5, RED, fill=False, w=1.0)
    circle(x + 44, y + 30, 2.5, RED)
    circle(x + 44, y + 30, 4.5, RED, fill=False, w=1.0)
    # medical emblem on a white disc
    circle(x + 156, y + 18, 14, WHITE)
    circle(x + 156, y + 18, 14, RED, fill=False, w=1.0)
    rect(x + 152, y + 6, x + 160, y + 30, RED)
    rect(x + 144, y + 12, x + 168, y + 22, RED)
    # virus particles drifting from the map
    _virus(x + 92, y + 14, 5, (200, 90, 80))
    _virus(x + 110, y + 27, 4, (200, 90, 80))
    draw_text(x + 112, y + 36, "11,000+", 15, RED, bold=True)


def icon_chip(x, y, w, h):
    rect(x, y, x + w, y + h, (226, 240, 220))
    rect(x + 10, y + 10, x + 40, y + 44, (30, 130, 60))
    rect(x + 19, y + 19, x + 31, y + 35, (20, 100, 45))
    # circuit traces from the die to the edges
    line(x + 19, y + 22, x + 12, y + 22, (20, 100, 45), 1.0)
    line(x + 31, y + 22, x + 38, y + 22, (20, 100, 45), 1.0)
    line(x + 19, y + 32, x + 12, y + 32, (20, 100, 45), 1.0)
    line(x + 31, y + 32, x + 38, y + 32, (20, 100, 45), 1.0)
    for i in range(3):
        rect(x + 4, y + 14 + i * 9, x + 10, y + 18 + i * 9, (30, 130, 60))
        rect(x + 40, y + 14 + i * 9, x + 46, y + 18 + i * 9, (30, 130, 60))
        rect(x + 14 + i * 9, y + 4, x + 18 + i * 9, y + 10, (30, 130, 60))
        rect(x + 14 + i * 9, y + 44, x + 18 + i * 9, y + 50, (30, 130, 60))
    # rising sales chart, right
    line(x + 148, y + 50, x + 188, y + 50, GREY, 1.0)
    for bx, bh in [(150, 8), (160, 14), (170, 20)]:
        rect(x + bx, y + 50 - bh, x + bx + 7, y + 50, (30, 130, 60))
    rect(x + 180, y + 22, x + 187, y + 50, GOLD_DK)
    polyline([(x + 148, y + 44), (x + 163, y + 36), (x + 173, y + 30),
              (x + 186, y + 20)], (20, 100, 45), 1.5)
    fill_poly([(x + 186, y + 20), (x + 180, y + 22), (x + 184, y + 26)],
              (20, 100, 45))
    draw_text(x + 56, y + 8, "$115.8bn", 18, (20, 100, 45), bold=True)
    draw_text(x + 56, y + 32, "UP 103%", 12, INK, bold=True)


def icon_cyclone(x, y, w, h):
    rect(x, y, x + w, y + h, (220, 232, 240))
    # India's east coast, right — the landfall shore
    coast = [(x + 148, y + 54), (x + 156, y + 40), (x + 150, y + 28),
             (x + 160, y + 16), (x + 168, y + 8), (x + 190, y + 6),
             (x + 190, y + 54)]
    fill_poly(coast, SAND)
    polyline(coast, (170, 150, 110), 1.0)
    cx, cy = x + 30, y + 27
    pts = []
    for i in range(48):
        t = i / 48 * 4 * math.pi
        r = 2 + i * 0.35
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t) * 0.8))
    polyline(pts, NAVY2, 2.0)
    circle(cx, cy, 3, WHITE)
    # rain streaks around the storm
    for rx, ry in [(50, 8), (56, 22), (14, 40), (44, 44)]:
        line(x + rx, y + ry, x + rx + 4, y + ry + 6, (140, 170, 200), 1.5)
    # track to landfall, along the bottom
    dashed_line(x + 40, y + 48, x + 146, y + 48, RED, 1.5, dash=5, gap=3)
    fill_poly([(x + 146, y + 48), (x + 138, y + 44), (x + 138, y + 52)], RED)
    draw_text(x + 62, y + 10, "110 km/h", 18, NAVY, bold=True)
    draw_text(x + 62, y + 34, "GUSTS", 11, GREY, bold=True)
    draw_text(x + 158, y + 38, "INDIA", 11, INK, bold=True)


def icon_knesset(x, y, w, h):
    rect(x, y, x + w, y + h, (232, 228, 216))
    fill_poly([(x + 10, y + 14), (x + 66, y + 14), (x + 38, y + 4)], NAVY2)
    for i in range(3):
        rect(x + 14 + i * 17, y + 18, x + 21 + i * 17, y + 42, NAVY2)
    rect(x + 10, y + 42, x + 70, y + 47, NAVY2)
    rect(x + 6, y + 47, x + 74, y + 50, NAVY2)
    # Israeli flag on a pole beside the house
    line(x + 78, y + 8, x + 78, y + 42, DARK, 1.5)
    rect(x + 79, y + 8, x + 93, y + 16, WHITE)
    rect(x + 79, y + 8, x + 93, y + 10, (0, 87, 184))
    rect(x + 79, y + 14, x + 93, y + 16, (0, 87, 184))
    burst(x + 86, y + 12, 2.5, (0, 87, 184))
    rect(x + 96, y + 10, x + 180, y + 44, WHITE)
    frame(x + 96, y + 10, x + 180, y + 44, NAVY, 1)
    # the vote as bars: 66 blue, 52 grey
    rect(x + 96, y + 46, x + 151, y + 50, (40, 80, 160))
    rect(x + 96, y + 51, x + 140, y + 54, (150, 150, 150))
    draw_text(x + 108, y + 18, "66–52", 18, NAVY, bold=True)


def icon_cop(x, y, w, h):
    rect(x, y, x + w, y + h, (220, 235, 230))
    circle(x + 28, y + 27, 18, (80, 150, 200))
    circle(x + 28, y + 27, 18, NAVY2, fill=False, w=1.0)
    fill_poly([(x + 20, y + 18), (x + 30, y + 14), (x + 35, y + 22),
               (x + 26, y + 26)], (90, 180, 90))
    fill_poly([(x + 24, y + 32), (x + 38, y + 34), (x + 33, y + 42),
               (x + 24, y + 39)], (90, 180, 90))
    fill_poly([(x + 14, y + 26), (x + 20, y + 22), (x + 22, y + 30),
               (x + 16, y + 34)], (90, 180, 90))
    # cloud wisps on the globe
    circle(x + 20, y + 22, 2.5, WHITE)
    circle(x + 34, y + 36, 2.5, WHITE)
    # thermometer with ticks
    rect(x + 62, y + 8, x + 68, y + 36, WHITE)
    frame(x + 62, y + 8, x + 68, y + 36, INK, 1)
    rect(x + 63, y + 22, x + 67, y + 36, RED)
    circle(x + 65, y + 40, 5, RED)
    line(x + 62, y + 14, x + 65, y + 14, INK, 1.0)
    line(x + 62, y + 20, x + 65, y + 20, INK, 1.0)
    line(x + 62, y + 26, x + 65, y + 26, INK, 1.0)
    # rising-temperature arrow
    line(x + 74, y + 40, x + 74, y + 30, RED, 2.0)
    fill_poly([(x + 74, y + 27), (x + 70, y + 32), (x + 78, y + 32)], RED)
    # sun, top right
    circle(x + 170, y + 10, 5, GOLD)
    for a in range(4):
        ang = math.pi * a / 2 + math.pi / 4
        line(x + 170 + 7 * math.cos(ang), y + 10 + 7 * math.sin(ang),
             x + 170 + 10 * math.cos(ang), y + 10 + 10 * math.sin(ang),
             GOLD, 1.5)
    # solar panels along the bottom
    for px in (82, 104, 126):
        fill_poly([(x + px, y + 46), (x + px + 14, y + 44),
                   (x + px + 16, y + 50), (x + px + 2, y + 52)],
                  (40, 80, 160))
    # wind turbine, far right
    line(x + 182, y + 52, x + 182, y + 26, DARK, 2.0)
    for a in (-90, 30, 150):
        ang = math.radians(a)
        line(x + 182, y + 22, x + 182 + 7 * math.cos(ang),
             y + 22 + 7 * math.sin(ang), DARK, 2.0)
    circle(x + 182, y + 22, 2, DARK)
    draw_text(x + 80, y + 8, "COP31", 15, NAVY, bold=True)
    draw_text(x + 80, y + 28, "75 BACK 35x35", 12, RED, bold=True)


def icon_voyager(x, y, w, h):
    rect(x, y, x + w, y + h, (16, 24, 44))
    for sx, sy in [(10, 8), (22, 14), (52, 6), (62, 20), (150, 8),
                   (140, 36), (16, 40), (120, 44)]:
        circle(x + sx, y + sy, 1.5, WHITE)
    # Earth, left
    circle(x + 28, y + 27, 10, (70, 130, 200))
    circle(x + 28, y + 27, 10, WHITE, fill=False, w=1.0)
    fill_poly([(x + 22, y + 20), (x + 30, y + 18), (x + 33, y + 24),
               (x + 26, y + 27)], (90, 180, 90))
    fill_poly([(x + 24, y + 32), (x + 34, y + 33), (x + 31, y + 38),
               (x + 24, y + 37)], (90, 180, 90))
    # dashed trajectory along the bottom
    dashed_line(x + 40, y + 47, x + 150, y + 47, GOLD, 1.5, dash=5, gap=3)
    # Voyager spacecraft, bottom right
    rect(x + 158, y + 42, x + 168, y + 50, GOLD)
    circle(x + 172, y + 42, 5, GOLD)
    circle(x + 174, y + 41, 4, (16, 24, 44))
    line(x + 158, y + 46, x + 150, y + 42, GOLD, 1.5)
    line(x + 168, y + 44, x + 176, y + 36, GOLD, 1.5)
    circle(x + 176, y + 35, 1.5, GOLD)
    # a distant world, top right
    circle(x + 180, y + 10, 4, (150, 180, 220))
    line(x + 175, y + 12, x + 185, y + 8, (150, 180, 220), 1.0)
    draw_text(x + 70, y + 8, "1 LIGHT-DAY", 15, WHITE, bold=True)
    draw_text(x + 70, y + 30, "25.9bn km OUT", 11, (200, 200, 200), bold=True)


def _virus(cx, cy, r, color):
    for i in range(8):
        a = math.pi * i / 4
        line(cx + r * 0.8 * math.cos(a), cy + r * 0.8 * math.sin(a),
             cx + r * 1.4 * math.cos(a), cy + r * 1.4 * math.sin(a), color, 2.0)
    circle(cx, cy, r, color)


def icon_measles(x, y, w, h):
    rect(x, y, x + w, y + h, (240, 228, 228))
    _virus(x + 26, y + 26, 11, RED)
    _virus(x + 52, y + 36, 7, (200, 90, 80))
    _virus(x + 44, y + 12, 5, (200, 90, 80))
    _virus(x + 66, y + 46, 4, (200, 90, 80))
    _virus(x + 12, y + 44, 3.5, (200, 90, 80))
    # broken shield: the lost elimination status
    shield = [(x + 160, y + 6), (x + 182, y + 12), (x + 182, y + 30),
              (x + 160, y + 48), (x + 138, y + 30), (x + 138, y + 12)]
    fill_poly(shield, WHITE)
    polyline(shield + [shield[0]], NAVY2, 1.5)
    polyline([(x + 152, y + 14), (x + 158, y + 22), (x + 154, y + 28),
              (x + 160, y + 34), (x + 156, y + 42)], RED, 2.0)
    draw_text(x + 72, y + 10, "5,400", 18, RED, bold=True)
    draw_text(x + 72, y + 34, "CASES", 11, INK, bold=True)


def _drone(cx, cy, s, color):
    line(cx - s, cy - s * 0.6, cx + s, cy + s * 0.6, color, 1.5)
    line(cx - s, cy + s * 0.6, cx + s, cy - s * 0.6, color, 1.5)
    circle(cx, cy, s * 0.35, color)
    circle(cx - s, cy - s * 0.6, 1.2, RED)
    circle(cx + s, cy - s * 0.6, 1.2, RED)


def icon_drones(x, y, w, h):
    rect(x, y, x + w, y + h, (24, 32, 52))
    for sx, sy in [(14, 8), (40, 14), (88, 6), (120, 12), (168, 8),
                   (150, 26), (60, 26), (28, 30)]:
        circle(x + sx, y + sy, 1.2, WHITE)
    # moon
    circle(x + 95, y + 6, 5, (230, 230, 200))
    circle(x + 93, y + 5, 1.5, (200, 200, 170))
    _drone(x + 30, y + 16, 7, (200, 205, 215))
    _drone(x + 70, y + 10, 6, (200, 205, 215))
    _drone(x + 110, y + 18, 7, (200, 205, 215))
    _drone(x + 150, y + 10, 6, (200, 205, 215))
    _drone(x + 90, y + 24, 5, (200, 205, 215))
    burst(x + 168, y + 26, 7, (255, 150, 50))
    # interceptor rising to meet a drone, top right
    dashed_line(x + 189, y + 54, x + 178, y + 16, (255, 200, 100), 1.0,
                dash=4, gap=3)
    burst(x + 178, y + 18, 4, (255, 150, 50))
    _drone(x + 180, y + 28, 3.5, (200, 205, 215))
    circle(x + 178, y + 33, 1, (255, 150, 50))
    circle(x + 183, y + 35, 1, (255, 150, 50))
    # city silhouette along the bottom
    for bx, bw, bh in [(8, 16, 6), (30, 14, 8), (150, 14, 6), (170, 10, 7)]:
        rect(x + bx, y + 54 - bh, x + bx + bw, y + 54, (14, 20, 36))
    rect(x + 12, y + 50, x + 14, y + 52, GOLD)
    rect(x + 34, y + 48, x + 36, y + 50, GOLD)
    rect(x + 154, y + 50, x + 156, y + 52, GOLD)
    draw_text(x + 8, y + 32, "141 DRONES", 15, WHITE, bold=True)
    draw_text(x + 106, y + 34, "126 DOWNED", 11, GOLD, bold=True)


def icon_horn(x, y, w, h):
    rect(x, y, x + w, y + h, (238, 230, 205))
    # highland ridges, left and right
    fill_poly([(x + 5, y + 54), (x + 25, y + 40), (x + 45, y + 54)],
              (190, 175, 140))
    fill_poly([(x + 145, y + 54), (x + 165, y + 40), (x + 185, y + 54)],
              (190, 175, 140))
    fill_poly([(x + 20, y + 44), (x + 25, y + 40), (x + 30, y + 44)],
              WHITE)
    fill_poly([(x + 160, y + 44), (x + 165, y + 40), (x + 170, y + 44)],
              WHITE)
    dashed_line(x + 95, y + 4, x + 95, y + 50, DARK, 1.0, dash=4, gap=3)
    fill_poly([(x + 30, y + 20), (x + 62, y + 20), (x + 62, y + 15),
               (x + 78, y + 23), (x + 62, y + 31), (x + 62, y + 26),
               (x + 30, y + 26)], (30, 110, 60))
    fill_poly([(x + 160, y + 20), (x + 128, y + 20), (x + 128, y + 15),
               (x + 112, y + 23), (x + 128, y + 31), (x + 128, y + 26),
               (x + 160, y + 26)], (180, 40, 30))
    # tanks facing the border
    rect(x + 45, y + 37, x + 61, y + 43, DARK)
    rect(x + 49, y + 33, x + 57, y + 37, DARK)
    line(x + 61, y + 35, x + 69, y + 35, DARK, 2.0)
    rect(x + 129, y + 37, x + 145, y + 43, DARK)
    rect(x + 133, y + 33, x + 141, y + 37, DARK)
    line(x + 129, y + 35, x + 121, y + 35, DARK, 2.0)
    # Badme flashpoint star on the border
    burst(x + 95, y + 32, 3, RED)
    # flags beside the names
    rect(x + 82, y + 8, x + 94, y + 10, (30, 110, 60))
    rect(x + 82, y + 10, x + 94, y + 12, (240, 200, 40))
    rect(x + 82, y + 12, x + 94, y + 14, (180, 40, 30))
    fill_poly([(x + 118, y + 8), (x + 118, y + 14), (x + 124, y + 11)],
              (180, 40, 30))
    rect(x + 124, y + 8, x + 130, y + 11, (30, 110, 60))
    rect(x + 124, y + 11, x + 130, y + 14, (0, 87, 184))
    draw_text(x + 28, y + 6, "ETHIOPIA", 11, (30, 110, 60), bold=True)
    draw_text(x + 132, y + 6, "ERITREA", 11, (180, 40, 30), bold=True)
    draw_text(x + 95, y + 36, "BADME", 12, RED, bold=True, align="center")


# ---------------------------------------------------------------------------
# Dotted world map (coarse continent outlines, lon/lat).
# ---------------------------------------------------------------------------

CONTINENTS = [
    [(-168, 66), (-140, 70), (-125, 72), (-110, 73), (-95, 72), (-85, 70),
     (-80, 73), (-65, 62), (-60, 52), (-55, 47), (-70, 42), (-75, 35),
     (-80, 32), (-81, 25), (-90, 21), (-97, 26), (-105, 23), (-110, 24),
     (-114, 29), (-117, 33), (-124, 40), (-124, 48), (-130, 55), (-145, 60),
     (-158, 58)],
    [(-77, 8), (-72, 11), (-60, 8), (-50, 5), (-35, -8), (-38, -15),
     (-48, -27), (-52, -33), (-58, -38), (-65, -45), (-68, -52), (-70, -54),
     (-73, -45), (-73, -37), (-70, -30), (-70, -20), (-77, -12), (-80, -5),
     (-77, 4)],
    [(-17, 15), (-10, 6), (5, 4), (9, -1), (13, -12), (12, -18), (17, -29),
     (20, -35), (28, -33), (32, -29), (35, -23), (40, -15), (40, -10),
     (51, 10), (43, 12), (38, 18), (35, 28), (32, 31), (20, 32), (10, 37),
     (0, 36), (-6, 35), (-10, 31), (-15, 27), (-17, 21)],
    [(-10, 36), (-9, 43), (-2, 48), (0, 50), (3, 53), (8, 57), (10, 59),
     (18, 56), (21, 55), (24, 58), (28, 60), (30, 62), (28, 66), (32, 70),
     (40, 68), (45, 68), (48, 60), (40, 55), (35, 50), (30, 46), (28, 44),
     (23, 40), (19, 42), (15, 44), (12, 44), (10, 44), (7, 44), (3, 43),
     (-2, 37), (-6, 36)],
    [(30, 70), (40, 68), (48, 60), (55, 55), (60, 55), (68, 58), (75, 62),
     (85, 68), (95, 72), (105, 73), (115, 73), (125, 72), (135, 71),
     (145, 70), (155, 68), (162, 66), (170, 66), (178, 65), (178, 62),
     (170, 60), (162, 55), (158, 52), (155, 50), (150, 45), (142, 42),
     (135, 35), (130, 33), (127, 35), (122, 38), (122, 31), (120, 28),
     (115, 23), (110, 20), (108, 18), (105, 10), (100, 8), (98, 12),
     (95, 16), (92, 21), (88, 22), (85, 20), (80, 16), (77, 8), (75, 12),
     (72, 20), (68, 23), (66, 25), (61, 25), (57, 26), (52, 26), (50, 29),
     (48, 30), (44, 29), (40, 32), (36, 36), (35, 42), (32, 44), (30, 46),
     (35, 50), (40, 55), (45, 60), (48, 62), (40, 66), (35, 68)],
    [(113, -22), (114, -28), (115, -33), (118, -35), (124, -33), (129, -32),
     (132, -32), (135, -35), (138, -35), (140, -38), (145, -38), (147, -38),
     (150, -37), (153, -32), (153, -27), (151, -24), (146, -19), (142, -15),
     (142, -11), (137, -12), (135, -15), (132, -12), (130, -13), (126, -14),
     (122, -17), (118, -20)],
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (1, 51), (0, 50)],
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 36), (141, 39),
     (142, 42), (144, 44), (142, 45), (140, 40), (139, 37), (136, 34),
     (133, 34), (130, 33)],
    [(167, -45), (170, -42), (173, -39), (175, -37), (178, -38), (176, -40),
     (173, -42), (170, -44), (168, -46)],
    [(95, 5), (100, 0), (105, -5), (110, -7), (115, -8), (120, -10),
     (125, -9), (130, -3), (135, -2), (140, -8), (135, -8), (130, -5),
     (120, -5), (110, -7), (105, -5), (100, 0)],
]


def _in_poly(lon, lat, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > lat) != (y1 > lat):
            xin = x0 + (lat - y0) * (x1 - x0) / (y1 - y0)
            if lon < xin:
                inside = not inside
    return inside


def _on_land(lon, lat):
    return any(_in_poly(lon, lat, p) for p in CONTINENTS)


# (story number, lon, lat, label dx, label dy) — heroes 1-3 + grid 4-13.
# 10 (Voyager 1) is in space: shown as a star + label, not a pin.
PINS = [(1, 56.3, 26.9, 14, -10), (2, 36.6, 45.3, 12, -8),
        (3, 114.1, 22.5, 0, 0), (4, -152, 64, 0, 0), (5, 23, -2, 0, 0),
        (6, -122, 37.4, 0, 0), (7, 88, 16, 0, 0), (8, 35.2, 31.8, 10, 8),
        (9, 30.7, 36.9, -14, 0), (11, -98, 39.5, 0, 0), (12, 31, 49, 0, -10),
        (13, 39, 14.5, 12, 6)]

# Brief locations (lon, lat) — small dots, stories 14-47.
DOTS = [(87, 55), (34.5, 31.5), (96, 20), (35.2, 31.8), (-1, 52),
        (-67, 10.5), (-77, 39), (4.4, 50.8), (-2, 53), (-1, 51),
        (-160, -15), (30.2, 13.2), (106.8, -6.2), (149, -35.3),
        (44.2, 15.3), (121, 14.6), (90.4, 23.8), (-95, 32),
        (-57.6, -25.3), (151.2, -33.9), (46.7, 24.6), (28.2, -25.7),
        (8.5, 47.4), (114.1, 22.5), (-76, -15), (0.1, 52.2),
        (103.8, 1.35), (39, 45), (-122.4, 37.8), (74.3, 31.5)]


def draw_map(x0, y0, w, h):
    gy = y0 + 4
    while gy < y0 + h:
        gx = x0 + 4
        while gx < x0 + w:
            lon = (gx - x0) / w * 360 - 180
            lat = 90 - (gy - y0) / h * 150
            if _on_land(lon, lat):
                circle(gx, gy, 1.7, NAVY2)
            gx += 8
        gy += 8
    for lon, lat in DOTS:
        px = x0 + (lon + 180) / 360 * w
        py = y0 + (90 - lat) / 150 * h
        circle(px, py, 2.2, GOLD_DK)
    for num, lon, lat, dx, dy in PINS:
        px = x0 + (lon + 180) / 360 * w
        py = y0 + (90 - lat) / 150 * h
        lx, ly = px + dx, py + dy
        if dx or dy:
            line(px, py, lx, ly, RED, 1.0)
            circle(px, py, 2, RED)
        circle(lx, ly, 7.5, RED)
        circle(lx, ly, 7.5, WHITE, fill=False, w=1.0)
        draw_text(lx, ly - 5.5, str(num), 11, WHITE, bold=True, align="center")


# ---------------------------------------------------------------------------
# Content — every claim verified against reporting on 18 November 2026.
# 47 stories: 3 heroes + 10 grid + 34 briefs.
# ---------------------------------------------------------------------------

HEROES = [
    dict(num=1, kicker="GULF WAR · STRAIT OF HORMUZ",
         head="US jets hit Iran site; drones target Bahrain, Kuwait",
         deck="Drones targeted a US radar site and Ali Al Salem; "
              "both say intercepted.",
         ill=ill_gulf),
    dict(num=2, kicker="UKRAINE · CRIMEA",
         head="Kerch bridge span falls on second day of strikes",
         deck="Part of the road deck fell into the strait below.",
         ill=ill_kerch),
    dict(num=3, kicker="DIPLOMACY · SHENZHEN",
         head="Xi greets Trump on the tarmac in Shenzhen",
         deck="Rare airport hug; Putin shakes Trump's hand at the "
              "banquet. First trilateral on Thursday.",
         ill=ill_shenzhen),
]

GRID = [
    dict(num=4, kicker="ALASKA · POLITICS",
         head="Peltola wins Alaska; Senate turns blue",
         deck="Peltola unseats Dan Sullivan in Alaska.",
         ill=icon_capitol),
    dict(num=5, kicker="HEALTH · DRC",
         head="Ebola in DRC passes 11,000 cases",
         deck="UN: 5,400 dead; cases doubled in 3 months.",
         ill=icon_ebola),
    dict(num=6, kicker="TECH · EARNINGS",
         head="Nvidia revenue doubles to $115.8bn",
         deck="Data-centre sales hit $107.6bn, up 110%.",
         ill=icon_chip),
    dict(num=7, kicker="WEATHER · INDIA",
         head="Cyclone Akvan nears India's east coast",
         deck="Landfall due Friday, gusts to 110 km/h.",
         ill=icon_cyclone),
    dict(num=8, kicker="ISRAEL · POLITICS",
         head="Kahana elected Knesset speaker",
         deck="Beats a Netanyahu loyalist.",
         ill=icon_knesset),
    dict(num=9, kicker="CLIMATE · COP31",
         head="75 nations back COP31 '35x35' goal",
         deck="Electricity to hit 35% of energy by 2035.",
         ill=icon_cop),
    dict(num=10, kicker="SPACE · NASA",
         head="Voyager 1 reaches one light-day out",
         deck="Signals now take 24 hours each way.",
         ill=icon_voyager),
    dict(num=11, kicker="HEALTH · USA",
         head="US loses measles-free status",
         deck="5,400 cases and 10 deaths this year.",
         ill=icon_measles),
    dict(num=12, kicker="EUROPE · UKRAINE WAR",
         head="Russia fires 141 drones at Ukraine",
         deck="Air force says 126 downed; 5 killed.",
         ill=icon_drones),
    dict(num=13, kicker="HORN OF AFRICA",
         head="Ethiopia, Eritrea mass troops",
         deck="Armies within striking distance: monitors.",
         ill=icon_horn),
]

# 34 single-line briefs (lead + rest, each line <= ~54 chars).
BRIEFS = [
    ("Siberia", "Russian An-12 crashes; 19 dead."),
    ("Gaza", "cold kills displaced people in tents."),
    ("Myanmar", "World Court to rule on genocide case."),
    ("Board of Peace", "blames Israel and Hamas."),
    ("UK", "sanctions 8 firms over West Bank building."),
    ("Venezuela", "unions block roads in pay protest."),
    ("USA", "computer outages reach the NSA."),
    ("EU", "proposes €45bn Ukraine loan for 2027."),
    ("UK inflation", "rises to 3.6%, a one-year high."),
    ("US officer", "held in UK over spying for Russia."),
    ("Cyclone Xavier", "Category 5, hits Cook Islands."),
    ("Sudan", "RSF drones killed 37 civilians, Amnesty says."),
    ("Indonesia", "hikes rates to 6% as rupiah slides."),
    ("Australia", "sanctions settler leader Weiss."),
    ("Yemen", "coalition hits 60 Houthi targets."),
    ("Manila", "Trump, Marcos vow defence boost."),
    ("Dhaka", "garment protests shut 500 factories."),
    ("Oil", "falls as US crude stocks jump 5.3m barrels."),
    ("Paraguay", "Ueno payout deadline now 2 Dec."),
    ("Tame Impala", "wins seven ARIAs in Sydney."),
    ("Java4Shell", "flaw spurs urgent patching."),
    ("Gold", "falls below $3,800, lowest in a year."),
    ("Sudan", "UN counts 2,230 civilian deaths in 2026."),
    ("FIFA", "Diallo to challenge Infantino for president."),
    ("Tencent", "Q3 revenue up 8%, below forecasts."),
    ("Peru", "M5.9 quake off south coast; no damage."),
    ("Cambridge", "'human' is 2026 Word of the Year."),
    ("Singapore", "Princess Aiko visits, first in 20 years."),
    ("Russia", "Ukrainian drones hit two oil refineries."),
    ("Japan", "Takaichi in China, first visit as PM."),
    ("Anthropic", "prices record IPO; trades Thursday."),
    ("Lahore", "most polluted big city again, AQI 339."),
    ("Riyadh", "coalition downs two Houthi missiles."),
    ("South Africa", "inflation jumps to 5.2%."),
]

DATE_CHECK = ("DATE CHECK — Left out because they were reported on 17 Nov, "
              "not today: Dhoni retires; China–Canada tariff relief; "
              "Thaçi sentence.")


def draw_brief(x, y, lead, rest, max_w, size=12):
    """One single-line brief: gold bullet, bold lead, regular rest."""
    circle(x + 3, y + 6, 2.5, GOLD)
    tx = x + 10
    full_lead = lead + ": "
    draw_text(tx, y, full_lead, size, INK, bold=True)
    draw_text(tx + text_width(full_lead, size, bold=True), y, rest,
              size, INK)


def draw_page():
    rect(0, 0, W, H, PAPER)

    # --- Masthead ---
    rect(0, 0, W, 108, NAVY)
    rect(16, 6, 1008, 8, GOLD)
    rect(16, 100, 1008, 102, GOLD)
    draw_text(512, 12, "Wednesday 18 November 2026", 60, WHITE,
              bold=True, align="center", font="serif")
    draw_text(512, 78, "THE DAY IN WORLD NEWS  ·  47 STORIES  ·  SIX CONTINENTS",
              18, GOLD, bold=True, align="center")

    # --- Hero row ---
    for i, hero in enumerate(HEROES):
        px = 16 + i * 330
        rect(px, 116, px + 322, 352, WHITE)
        frame(px, 116, px + 322, 352, NAVY, 2)
        hero["ill"](px + 2, 118, 318, 88)
        badge(px + 20, 136, hero["num"])
        draw_text(px + 12, 212, hero["kicker"], 15, RED, bold=True)
        end_y, _ = draw_wrapped(px + 12, 230, hero["head"], 25, 298, INK,
                                bold=True, lh=29, font="serif")
        draw_wrapped(px + 12, end_y + 6, hero["deck"], 15, 298, GREY, lh=18)

    # --- Story grid: 5 columns x 2 rows ---
    for i, story in enumerate(GRID):
        col, row = i % 5, i // 5
        px = 16 + col * 200
        py = 362 + row * 160
        rect(px, py, px + 192, py + 160, WHITE)
        frame(px, py, px + 192, py + 160, BORDER, 1)
        story["ill"](px + 1, py + 1, 190, 54)
        badge(px + 14, py + 14, story["num"],
              r=8 if story["num"] < 10 else 10)
        draw_text(px + 8, py + 59, story["kicker"], 12, RED, bold=True)
        end_y, _ = draw_wrapped(px + 8, py + 73, story["head"], 19, 176,
                                INK, bold=True, lh=23, font="serif")
        draw_wrapped(px + 8, end_y + 4, story["deck"], 14, 176, GREY, lh=17)

    # --- Map panel ---
    rect(16, 692, 316, 988, WHITE)
    frame(16, 692, 316, 988, BORDER, 1)
    draw_text(24, 698, "WHERE IT HAPPENED", 15, NAVY, bold=True)
    rect(24, 716, 308, 718, GOLD)
    draw_map(20, 720, 292, 264)
    fill_poly([(30, 956), (32, 962), (38, 964), (32, 966), (30, 972),
               (28, 966), (22, 964), (28, 962)], GOLD)
    draw_text(44, 960, "10 · VOYAGER 1", 11, GOLD_DK, bold=True)

    # --- Briefs panel: 2 columns x 17 single-line briefs ---
    rect(328, 692, 1008, 988, WHITE)
    frame(328, 692, 1008, 988, BORDER, 1)
    draw_text(340, 698, "ALSO ON WEDNESDAY 18 NOVEMBER", 15, NAVY, bold=True)
    rect(340, 716, 996, 718, GOLD)
    for i, (lead, rest) in enumerate(BRIEFS):
        col, row = i // 17, i % 17
        bx = 340 + col * 338
        by = 722 + row * 16
        draw_brief(bx, by, lead, rest, 320, size=12)

    # --- Footer: date check + sources ---
    rect(16, 992, 1008, 994, GOLD)
    draw_text(512, 997, DATE_CHECK, 12, INK, align="center")
    draw_text(512, 1011,
              "Every story was reported on Wednesday 18 November 2026. "
              "Sources: Reuters, AP, AFP, BBC, Al Jazeera, UN "
              "· Original drawings",
              12, GREY, align="center")


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    draw_page()
    rgb = downsample()
    data = encode_png(rgb, W, H)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
