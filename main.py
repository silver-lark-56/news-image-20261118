#!/usr/bin/env python3
"""news-image-20261118 — one-page newspaper front page for Wednesday 18 November 2026.

Pure standard-library program: draws the whole page with vector primitives
into a 2x supersampled buffer, downsamples to 1024x1024, and writes a PNG
with a hand-rolled encoder (zlib). No network, no files read, no randomness
— two runs produce byte-identical output.
"""

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
# Single-stroke vector font, written for this program.
# Grid: x 0-5 (wide glyphs to 7), y 0-9. Cap top y=0, baseline y=7,
# x-height top y=2, descender bottom y=9. Each glyph is a list of strokes;
# a stroke is a polyline of (x, y) points. Two identical points = a dot.
# ---------------------------------------------------------------------------

_GLYPH_SRC = {
    "A": "07 30 57;14 44",
    "B": "00 07;00 40 53 44 04;04 44 55 47 07",
    "C": "50 20 02 05 27 57",
    "D": "00 07;00 40 54 47 07",
    "E": "50 00 07 57;04 34",
    "F": "00 07;00 50;04 34",
    "G": "50 20 02 05 27 57 55 35",
    "H": "00 07;50 57;04 54",
    "I": "20 27;00 50;07 57",
    "J": "50 56 47 27 05;00 50",
    "K": "00 07;50 24 57",
    "L": "00 07 57",
    "M": "07 00 24 50 57",
    "N": "07 00 57 50",
    "O": "10 40 52 55 47 17 05 02 10",
    "P": "07 00 40 53 44 04",
    "Q": "10 40 52 55 47 17 05 02 10;35 57",
    "R": "07 00 40 53 44 04;24 57",
    "S": "50 20 02 24 45 57 27",
    "T": "00 50;20 27",
    "U": "00 05 17 47 55 50",
    "V": "00 27 50",
    "W": "00 07 24 57 50",
    "X": "00 57;50 07",
    "Y": "00 24 50;24 27",
    "Z": "00 50 07 57",
    "a": "12 42 55 47 17 25 12;52 57",
    "b": "00 07;12 42 55 47 17 25 12",
    "c": "42 22 05 27 47",
    "d": "50 57;12 42 55 47 17 25 12",
    "e": "47 17 04 22 42 54 14",
    "f": "37 24 20 42;04 34",
    "g": "12 42 55 47 17 25 12;52 57 49 29 07",
    "h": "00 07;04 22 42 54 57",
    "i": "22 27;20 20",
    "j": "32 37 19 07;30 30",
    "k": "00 07;52 24 57",
    "l": "20 27",
    "m": "02 07;04 12 22 34 37;34 42 52 62 67",
    "n": "02 07;04 22 42 54 57",
    "o": "12 42 55 47 17 25 12",
    "p": "02 09;12 42 55 47 17 25 12",
    "q": "52 59;12 42 55 47 17 25 12",
    "r": "02 07;04 22 32 42",
    "s": "42 22 04 25 45 57 27",
    "t": "21 27 47;04 44",
    "u": "02 06 17 47 56 52",
    "v": "02 27 52",
    "w": "02 17 24 37 52",
    "x": "22 57;52 27",
    "y": "02 27 52;52 57 29 07",
    "z": "22 52 27 57",
    "0": "10 40 52 55 47 17 05 02 10",
    "1": "12 20 27;07 47",
    "2": "02 20 40 52 07 57",
    "3": "02 20 40 52 44 24;44 55 47 27 05",
    "4": "30 04 54;40 47",
    "5": "50 00 04 44 55 47 27 05",
    "6": "42 22 05 27 47 55 44 24",
    "7": "00 50 27",
    "8": "12 20 40 52 44 24 12;14 44 55 47 27 04 14",
    "9": "12 42 55 47 27 04 12;47 57 29",
    ".": "27 27",
    ",": "27 29 17",
    ":": "22 22;25 25",
    ";": "22 22;25 29 17",
    "!": "22 25;27 27",
    "?": "12 22 42 54 34 24;27 27",
    "'": "23 21",
    '"': "11 13;31 33",
    "(": "42 22 05 27 47",
    ")": "02 22 45 27 07",
    "-": "14 44",
    "–": "04 54",
    "—": "04 64",
    "/": "07 50",
    "%": "02 57;11 11;44 44",
    "$": "50 20 02 23 44 57 27;20 27",
    "&": "52 42 22 05 24 44 57 37;24 57",
    "+": "04 44;22 27",
    "=": "12 42;15 45",
    "€": "50 20 02 05 27 57;02 32;05 35",
    "£": "42 22 02 24 47 57;14 44",
    "•": "22 33",
    "·": "23 23",
    "°": "11 31 32 12 11",
    "×": "12 45;42 15",
    "→": "04 54;42 54 46",
    "#": "12 17;32 37;04 54;01 51",
    "*": "12 34;32 14;21 24",
    "_": "09 59",
}


def _parse_glyphs(src):
    out = {}
    for ch, s in src.items():
        strokes = []
        for part in s.split(";"):
            pts = []
            for tok in part.split():
                pts.append((int(tok[0]), int(tok[1])))
            if pts:
                strokes.append(pts)
        out[ch] = strokes
    return out


GLYPHS = _parse_glyphs(_GLYPH_SRC)
GLYPHS["’"] = GLYPHS["'"]
GLYPHS["“"] = GLYPHS['"']
GLYPHS["”"] = GLYPHS['"']

ADV = {"i": 3.5, "j": 4.0, "l": 3.5, ".": 3.5, ",": 3.5, ":": 3.5, ";": 3.5,
       "!": 3.5, "'": 3.0, "’": 3.0, "·": 3.5, "°": 4.0, "f": 4.0, "t": 4.5,
       "r": 4.5, " ": 3.0, "m": 7.5, "w": 7.5, "—": 8.0, "%": 7.0, "&": 7.0,
       "€": 6.5, "M": 7.0, "W": 7.5, "(": 4.0, ")": 4.0, "-": 4.0, "–": 6.0,
       "/": 4.5, "+": 6.0, "=": 6.0, "#": 6.5, "*": 5.0, "_": 6.0, "$": 6.0,
       "£": 6.0, "•": 4.0, "×": 5.5, "→": 6.5, "?": 6.0, '"': 5.0,
       "“": 5.0, "”": 5.0}


def _adv(ch):
    return ADV.get(ch, 6.0)


def text_width(s, size):
    u = size / 7.0
    return sum(_adv(c) for c in s) * u


def draw_text(x, y, s, size, color, bold=False, align="left"):
    """Draw text; (x, y) is the top-left of the cap-height box."""
    u = size / 7.0
    total = text_width(s, size)
    if align == "center":
        x -= total / 2
    elif align == "right":
        x -= total
    cx = x
    # Iteration: thicker strokes (was 0.15 bold / 0.105 regular) so
    # headlines and decks read bolder against competitors' serif type.
    sw = max(1.0, size * (0.19 if bold else 0.13))
    for ch in s:
        strokes = GLYPHS.get(ch)
        if strokes:
            for pts in strokes:
                if len(pts) == 2 and pts[0] == pts[1]:
                    circle(cx + pts[0][0] * u, y + pts[0][1] * u,
                           sw * 0.55, color)
                else:
                    polyline([(cx + px * u, y + py * u) for px, py in pts],
                             color, sw)
        cx += _adv(ch) * u
    return total


def wrap_text(s, size, max_w):
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_wrapped(x, y, s, size, max_w, color, bold=False, lh=None):
    if lh is None:
        lh = size * 1.5
    lines = wrap_text(s, size, max_w)
    for ln in lines:
        draw_text(x, y, ln, size, color, bold=bold)
        y += lh
    return y, lines


def badge(x, y, n, r=None):
    """Number badge: navy circle with a white number, centred at (x, y)."""
    s = str(n)
    if r is None:
        r = 10 if len(s) == 1 else 12
    circle(x, y, r, NAVY)
    circle(x, y, r, WHITE, fill=False, w=1.0)
    draw_text(x, y - 5.5, s, 11, WHITE, bold=True, align="center")


# ---------------------------------------------------------------------------
# Illustrations — flat vector drawings, one per story.
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
    fill_poly([(x, y + h), (x, y + 55), (x + 55, y + 50), (x + 95, y + 68),
               (x + 110, y + h)], SAND)
    fill_poly([(x + 160, y), (x + w, y), (x + w, y + 30), (x + 215, y + 28),
               (x + 185, y + 12)], SAND)
    fill_poly([(x + 178, y + 38), (x + 208, y + 34), (x + 218, y + 42),
               (x + 192, y + 48), (x + 175, y + 45)], LAND)
    dashed_line(x + 205, y + 22, x + 150, y + 50, DARK, 1.0)
    dashed_line(x + 185, y + 18, x + 132, y + 40, DARK, 1.0)
    fill_poly([(x + 150, y + 46), (x + 144, y + 54), (x + 156, y + 54)], DARK)
    fill_poly([(x + 132, y + 36), (x + 126, y + 44), (x + 138, y + 44)], DARK)
    circle(x + 88, y + 60, 4, RED)
    circle(x + 130, y + 42, 4, RED)
    burst(x + 198, y + 40, 9, RED)
    draw_text(x + 40, y + 6, "GULF", 9, NAVY, bold=True)
    draw_text(x + 250, y + 8, "IRAN", 8, GREY, bold=True)
    draw_text(x + 168, y + 52, "QESHM", 8, INK, bold=True)
    draw_text(x + 58, y + 70, "BAHRAIN", 8, INK, bold=True)
    draw_text(x + 122, y + 28, "KUWAIT", 8, INK, bold=True)


def ill_kerch(x, y, w, h):
    rect(x, y, x + w, y + h, SKY)
    rect(x, y + 68, x + w, y + h, WATER)
    rect(x + 8, y + 46, x + 140, y + 56, DARK)
    rect(x + 192, y + 46, x + w - 8, y + 56, DARK)
    for px in (36, 108, 216, 276):
        rect(x + px, y + 56, x + px + 8, y + 76, DARK)
    fill_poly([(x + 150, y + 60), (x + 186, y + 76), (x + 179, y + 84),
               (x + 145, y + 68)], (120, 126, 134))
    line(x + 152, y + 84, x + 158, y + 76, WHITE, 2.0)
    line(x + 164, y + 86, x + 164, y + 78, WHITE, 2.0)
    line(x + 176, y + 84, x + 170, y + 77, WHITE, 2.0)
    circle(x + 152, y + 38, 8, (150, 150, 150))
    circle(x + 166, y + 30, 10, (170, 170, 170))
    circle(x + 180, y + 38, 7, (150, 150, 150))
    burst(x + 166, y + 50, 8, RED)
    draw_text(x + 40, y + 6, "KERCH STRAIT", 9, NAVY, bold=True)
    draw_text(x + w - 78, y + 6, "SPAN DOWN", 9, RED, bold=True)


def ill_shenzhen(x, y, w, h):
    rect(x, y, x + w, y + h, SKY)
    rect(x, y + 84, x + w, y + h, (200, 200, 190))
    for bx, top, bw in [(6, 44, 20), (30, 30, 24), (58, 50, 18), (80, 36, 22),
                        (106, 52, 20), (130, 28, 26), (160, 46, 18),
                        (182, 34, 24), (210, 52, 20), (234, 40, 22),
                        (260, 30, 24), (288, 48, 22)]:
        rect(x + bx, y + top, x + bx + bw, y + 84, NAVY2)
    _flag(x + 70, y + 14, "CN")
    _flag(x + 159, y + 14, "US")
    _flag(x + 248, y + 14, "RU")
    draw_text(x + 8, y + 86, "SHENZHEN", 9, NAVY, bold=True)


def icon_capitol(x, y, w, h):
    rect(x, y, x + w, y + h, (232, 228, 216))
    circle(x + 52, y + 38, 20, NAVY2)
    rect(x + 28, y + 38, x + 76, y + h, (232, 228, 216))
    rect(x + 30, y + 38, x + 74, y + 43, NAVY2)
    for cx in (34, 49, 64):
        rect(x + cx, y + 43, x + cx + 6, y + 58, NAVY2)
    rect(x + 100, y + 16, x + 156, y + 28, (40, 80, 160))
    rect(x + 100, y + 32, x + 144, y + 44, RED)
    draw_text(x + 160, y + 16, "56", 11, NAVY, bold=True)
    draw_text(x + 148, y + 32, "44", 11, NAVY, bold=True)
    draw_text(x + 100, y + 48, "SENATE", 8, GREY, bold=True)


def icon_ebola(x, y, w, h):
    rect(x, y, x + w, y + h, (242, 232, 220))
    fill_poly([(x + 12, y + 10), (x + 34, y + 6), (x + 58, y + 12),
               (x + 72, y + 24), (x + 64, y + 42), (x + 46, y + 54),
               (x + 30, y + 50), (x + 18, y + 38), (x + 8, y + 28)],
              (180, 140, 100))
    rect(x + 170, y + 12, x + 186, y + 44, RED)
    rect(x + 160, y + 22, x + 196, y + 34, RED)
    draw_text(x + 150, y + 48, "11,000+", 11, RED, bold=True)


def icon_chip(x, y, w, h):
    rect(x, y, x + w, y + h, (226, 240, 220))
    rect(x + 28, y + 10, x + 74, y + 50, (30, 130, 60))
    rect(x + 39, y + 21, x + 63, y + 39, (20, 100, 45))
    for i in range(4):
        rect(x + 20, y + 14 + i * 9, x + 28, y + 18 + i * 9, (30, 130, 60))
        rect(x + 74, y + 14 + i * 9, x + 82, y + 18 + i * 9, (30, 130, 60))
    draw_text(x + 96, y + 14, "$115.8bn", 16, (20, 100, 45), bold=True)
    draw_text(x + 96, y + 36, "UP 103%", 11, INK, bold=True)


def icon_cyclone(x, y, w, h):
    rect(x, y, x + w, y + h, (220, 232, 240))
    cx, cy = x + 50, y + 31
    pts = []
    for i in range(60):
        t = i / 60 * 4 * math.pi
        r = 2 + i * 0.4
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t) * 0.8))
    polyline(pts, NAVY2, 2.0)
    draw_text(x + 96, y + 14, "110 km/h", 15, NAVY, bold=True)
    draw_text(x + 96, y + 36, "GUSTS", 10, GREY, bold=True)


def icon_knesset(x, y, w, h):
    rect(x, y, x + w, y + h, (232, 228, 216))
    fill_poly([(x + 18, y + 16), (x + 88, y + 16), (x + 53, y + 5)], NAVY2)
    for i in range(4):
        rect(x + 22 + i * 17, y + 20, x + 30 + i * 17, y + 48, NAVY2)
    rect(x + 18, y + 48, x + 90, y + 54, NAVY2)
    rect(x + 128, y + 12, x + 208, y + 48, WHITE)
    frame(x + 128, y + 12, x + 208, y + 48, NAVY, 1)
    draw_text(x + 138, y + 18, "66–52", 16, NAVY, bold=True)


def icon_cop(x, y, w, h):
    rect(x, y, x + w, y + h, (220, 235, 230))
    circle(x + 48, y + 31, 23, (80, 150, 200))
    fill_poly([(x + 38, y + 20), (x + 50, y + 16), (x + 56, y + 26),
               (x + 44, y + 30)], (90, 180, 90))
    fill_poly([(x + 42, y + 38), (x + 60, y + 40), (x + 54, y + 50),
               (x + 42, y + 46)], (90, 180, 90))
    rect(x + 112, y + 10, x + 120, y + 42, WHITE)
    frame(x + 112, y + 10, x + 120, y + 42, INK, 1)
    rect(x + 114, y + 24, x + 118, y + 42, RED)
    circle(x + 116, y + 46, 7, RED)
    draw_text(x + 136, y + 16, "COP31", 14, NAVY, bold=True)
    draw_text(x + 136, y + 36, "STALLED", 10, RED, bold=True)


def icon_voyager(x, y, w, h):
    rect(x, y, x + w, y + h, (16, 24, 44))
    for sx, sy in [(18, 10), (36, 18), (86, 8), (104, 26), (196, 12),
                   (176, 42), (28, 46), (150, 50)]:
        circle(x + sx, y + sy, 1.5, WHITE)
    circle(x + 56, y + 31, 12, GOLD)
    circle(x + 59, y + 29, 9, (16, 24, 44))
    rect(x + 66, y + 27, x + 78, y + 35, GOLD)
    line(x + 78, y + 31, x + 94, y + 20, GOLD, 2.0)
    draw_text(x + 104, y + 14, "1 LIGHT-DAY", 13, WHITE, bold=True)
    draw_text(x + 104, y + 36, "25.9bn km OUT", 10, (200, 200, 200), bold=True)


def _virus(cx, cy, r, color):
    for i in range(8):
        a = math.pi * i / 4
        line(cx + r * 0.8 * math.cos(a), cy + r * 0.8 * math.sin(a),
             cx + r * 1.4 * math.cos(a), cy + r * 1.4 * math.sin(a), color, 2.0)
    circle(cx, cy, r, color)


def icon_measles(x, y, w, h):
    rect(x, y, x + w, y + h, (240, 228, 228))
    _virus(x + 42, y + 29, 13, RED)
    _virus(x + 80, y + 38, 8, (200, 90, 80))
    _virus(x + 66, y + 13, 6, (200, 90, 80))
    draw_text(x + 104, y + 14, "5,400", 16, RED, bold=True)
    draw_text(x + 104, y + 36, "CASES", 10, INK, bold=True)


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


# (story number, lon, lat, label dx, label dy)
PINS = [(1, 56.3, 26.9, 16, -12), (2, 36.6, 45.3, 14, -10),
        (3, 114.1, 22.5, 0, 0), (4, -152, 64, 0, 0), (5, 23, -2, 0, 0),
        (6, -122, 37.4, 0, 0), (7, 88, 16, 0, 0), (8, 35.2, 31.8, 12, 10),
        (9, 30.7, 36.9, -16, 0), (11, -98, 39.5, 0, 0)]


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
    for num, lon, lat, dx, dy in PINS:
        px = x0 + (lon + 180) / 360 * w
        py = y0 + (90 - lat) / 150 * h
        lx, ly = px + dx, py + dy
        if dx or dy:
            line(px, py, lx, ly, RED, 1.0)
            circle(px, py, 2, RED)
        circle(lx, ly, 8, RED)
        circle(lx, ly, 8, WHITE, fill=False, w=1.0)
        draw_text(lx, ly - 4, str(num), 8, WHITE, bold=True, align="center")


# ---------------------------------------------------------------------------
# Content — every claim verified against reporting on 18 November 2026.
# ---------------------------------------------------------------------------

HEROES = [
    dict(num=1, kicker="GULF WAR · STRAIT OF HORMUZ",
         head="US jets hit Iran site on Qeshm; drones target Bahrain, Kuwait",
         deck="Drones targeted a US radar site and Ali Al Salem; "
              "both say intercepted.",
         ill=ill_gulf),
    dict(num=2, kicker="UKRAINE · CRIMEA",
         head="Kerch bridge span falls into strait on second day of strikes",
         deck="Part of the road deck fell into the strait below.",
         ill=ill_kerch),
    dict(num=3, kicker="DIPLOMACY · SHENZHEN",
         head="Xi and Putin meet in Shenzhen before Thursday trilateral",
         deck="Xi hit out at trade protectionism; Putin attacked sanctions.",
         ill=ill_shenzhen),
]

GRID = [
    dict(num=4, kicker="ALASKA · POLITICS",
         head="Peltola wins Alaska; Senate turns blue",
         deck="Peltola unseats Dan Sullivan in Alaska.",
         ill=icon_capitol),
    dict(num=5, kicker="HEALTH · DRC",
         head="Ebola in DRC passes 11,000 cases",
         deck="UN: 5,400 dead; most victims are children under five.",
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
         head="Knesset elects Kahana as speaker, 66–52",
         deck="Eisenkot ally replaces a Netanyahu loyalist.",
         ill=icon_knesset),
    dict(num=9, kicker="CLIMATE · COP31",
         head="COP31 climate talks stall in Antalya",
         deck="Rich and poor nations split over finance.",
         ill=icon_cop),
    dict(num=10, kicker="SPACE · NASA",
         head="Voyager 1 reaches one light-day out",
         deck="Signals now take 24 hours each way.",
         ill=icon_voyager),
    dict(num=11, kicker="HEALTH · USA",
         head="US loses measles-free status",
         deck="5,400 cases and 10 deaths recorded this year.",
         ill=icon_measles),
]

NUMBERS = [
    ("56–44", "Democrats take the Senate"),
    ("$115.8bn", "Nvidia revenue, up 103%"),
    ("110 km/h", "Cyclone Akvan's peak gusts"),
    ("25.9bn km", "Voyager 1 from Earth"),
]

# Iteration: 21 briefs (was 12) across 3 columns; every new brief
# verified against 18 Nov 2026 reporting before use.
BRIEFS = [
    ("Siberia", "Russian military An-12 crashes; 19 dead."),
    ("Gaza", "cold kills displaced people in tents."),
    ("Myanmar", "World Court to rule on genocide case."),
    ("Board of Peace", "blames both sides."),
    ("UK", "sanctions 8 firms over West Bank settlements."),
    ("Venezuela", "unions block roads in pay protest."),
    ("USA", "repeated computer outages reach the NSA."),
    ("EU", "proposes €45bn Ukraine loan for 2027."),
    ("UK inflation", "rises to 3.6%, highest in a year."),
    ("US officer", "arrested in UK over spying for Russia."),
    ("Cyclone Xavier", "Category 5, hits Cook Islands."),
    ("Sudan", "Amnesty: RSF drones killed 37 civilians."),
    ("Indonesia", "hikes rates to 6% as rupiah slides."),
    ("Australia", "sanctions settler leader Weiss."),
    ("Yemen", "coalition hits 60 Houthi targets."),
    ("Manila", "Trump, Marcos vow defence boost."),
    ("Dhaka", "garment protests shut 500 factories."),
    ("Oil", "falls as US crude stocks jump 5.3m barrels."),
    ("Paraguay", "Ueno payout deadline now 2 Dec."),
    ("Tame Impala", "wins seven ARIA Awards in Sydney."),
    ("Java4Shell", "flaw spurs urgent patching."),
]


def draw_brief(x, y, lead, rest, max_w, size=10):
    """One brief: gold bullet, bold lead, regular rest, wrapped to 2 lines."""
    circle(x + 3, y + 4, 2.5, GOLD)
    tx = x + 10
    full_lead = lead + ": "
    words = rest.split(" ")
    lines = []
    cur = full_lead
    for word in words:
        trial = cur + word if cur.endswith(" ") or cur == full_lead else cur + " " + word
        if cur == full_lead:
            trial = full_lead + word
        elif text_width(cur + " " + word, size) <= max_w:
            trial = cur + " " + word
        else:
            trial = None
        if trial is not None and text_width(trial, size) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    lh = size * 1.25
    for i, ln in enumerate(lines[:2]):
        yy = y + i * lh
        if i == 0:
            draw_text(tx, yy, full_lead, size, INK, bold=True)
            rest_part = ln[len(full_lead):]
            if rest_part:
                draw_text(tx + text_width(full_lead, size), yy, rest_part,
                          size, INK)
        else:
            draw_text(tx, yy, ln, size, INK)


def draw_page():
    rect(0, 0, W, H, PAPER)

    # --- Masthead ---
    rect(0, 0, W, 116, NAVY)
    rect(16, 6, 1008, 8, GOLD)
    rect(16, 108, 1008, 110, GOLD)
    draw_text(512, 20, "Wednesday 18 November 2026", 44, WHITE,
              bold=True, align="center")
    draw_text(512, 78, "THE DAY IN WORLD NEWS  ·  32 STORIES  ·  SIX CONTINENTS",
              13, GOLD, bold=True, align="center")

    # --- Hero row ---
    for i, hero in enumerate(HEROES):
        px = 16 + i * 330
        rect(px, 126, px + 322, 376, WHITE)
        frame(px, 126, px + 322, 376, NAVY, 2)
        hero["ill"](px + 2, 128, 318, 100)
        badge(px + 20, 146, hero["num"])
        draw_text(px + 12, 236, hero["kicker"], 11, RED, bold=True)
        end_y, _ = draw_wrapped(px + 12, 254, hero["head"], 18, 298, INK,
                                bold=True, lh=26)
        draw_wrapped(px + 12, end_y + 6, hero["deck"], 11, 298, GREY, lh=15)

    # --- By the numbers ---
    rect(16, 388, 1008, 450, NAVY)
    draw_text(83, 398, "BY THE", 14, GOLD, bold=True, align="center")
    draw_text(83, 418, "NUMBERS", 14, GOLD, bold=True, align="center")
    rect(150, 396, 152, 442, GOLD)
    for i, (num, cap) in enumerate(NUMBERS):
        cx = 160 + i * 212 + 106
        draw_text(cx, 396, num, 26, GOLD, bold=True, align="center")
        draw_text(cx, 428, cap, 10, WHITE, align="center")

    # --- Story grid ---
    for i, story in enumerate(GRID):
        col, row = i % 4, i // 4
        px = 16 + col * 250
        py = 462 + row * 172
        rect(px, py, px + 242, py + 160, WHITE)
        frame(px, py, px + 242, py + 160, BORDER, 1)
        story["ill"](px + 1, py + 1, 240, 62)
        badge(px + 16, py + 16, story["num"], r=9 if story["num"] < 10 else 11)
        draw_text(px + 10, py + 70, story["kicker"], 9, RED, bold=True)
        end_y, _ = draw_wrapped(px + 10, py + 84, story["head"], 13.5, 222,
                                INK, bold=True, lh=19)
        draw_wrapped(px + 10, end_y + 5, story["deck"], 10.5, 222, GREY, lh=14)

    # --- Map panel ---
    rect(16, 806, 436, 986, WHITE)
    frame(16, 806, 436, 986, BORDER, 1)
    draw_text(24, 812, "WHERE IT HAPPENED", 11, NAVY, bold=True)
    fill_poly([(308, 810), (310, 816), (316, 818), (310, 820), (308, 826),
               (306, 820), (300, 818), (306, 816)], GOLD)
    draw_text(322, 813, "10 · VOYAGER 1", 9, GOLD_DK, bold=True)
    rect(24, 828, 428, 830, GOLD)
    draw_map(20, 834, 412, 146)

    # --- Briefs panel ---
    rect(448, 806, 1008, 986, WHITE)
    frame(448, 806, 1008, 986, BORDER, 1)
    draw_text(460, 812, "IN BRIEF", 11, NAVY, bold=True)
    rect(460, 828, 996, 830, GOLD)
    for i, (lead, rest) in enumerate(BRIEFS):
        col, row = i // 7, i % 7
        bx = 460 + col * 179
        by = 833 + row * 21.5
        draw_brief(bx, by, lead, rest, 164, size=8.5)

    # --- Footer ---
    rect(16, 992, 1008, 994, GOLD)
    draw_text(512, 998,
              "Every story was reported on Wednesday 18 November 2026; "
              "disputed claims are attributed.",
              9, INK, align="center")
    draw_text(512, 1010,
              "Sources: Reuters, AP, AFP, BBC, Al Jazeera and the UN "
              "· Original drawings",
              9, GREY, align="center")


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
