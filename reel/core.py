#!/usr/bin/env python3
"""Shared canvas, fonts, fetch, icons, and encode loop."""

import ctypes
import json
import math
import os
import shutil
import subprocess
import tempfile
import urllib.request

import cairo
import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Pango, PangoCairo, GdkPixbuf, Gdk

W, H = 1080, 1920
FPS = 30
DUR = 8.0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COPYRIGHT = "© 수영 책방  Swimming Bookstore"

INK = (0.16, 0.11, 0.12)
DATE = (0.30, 0.36, 0.48)
WHITE = (1.0, 1.0, 1.0)

PALETTE = (
    (1.00, 0.28, 0.46),
    (1.00, 0.58, 0.12),
    (1.00, 0.86, 0.12),
    (0.18, 0.86, 0.48),
    (0.08, 0.78, 0.98),
    (0.36, 0.42, 1.00),
    (0.78, 0.30, 1.00),
    (1.00, 0.24, 0.72),
)

ICON_FILES = {
    "Claude Code": "claude.svg",
    "Codex": "codex.png",
    "Pi": "pi.svg",
    "OpenClaw": "openclaw.svg",
    "Hermes Agent": "hermes.svg",
    "Cline": "cline.png",
    "claude": "claude.svg",
    "openai": "openai.svg",
    "gemini": "gemini-mark.svg",
    "grok": "xai-logo.svg",
}

ICON_STYLE = {
    "Claude Code": {"bg": None, "pad": 6, "clip": False},
    "Codex": {"bg": None, "pad": 0, "clip": False},
    "Pi": {"bg": (0.067, 0.067, 0.067), "pad": 0, "clip": False},
    "OpenClaw": {"bg": None, "pad": 0, "clip": False},
    "Hermes Agent": {"bg": None, "pad": 0},
    "Cline": {"bg": None, "pad": 0},
    "claude": {"bg": None, "pad": 0, "clip": False},
    "openai": {"bg": None, "pad": 0, "clip": False},
    "gemini": {"bg": None, "pad": 0, "clip": False},
    "grok": {"bg": None, "pad": 0, "clip": False},
}


def load_local_fonts():
    path = os.path.join(ROOT, "fonts", "Orbitron.ttf")
    if not os.path.isfile(path):
        return
    try:
        fc = ctypes.cdll.LoadLibrary("libfontconfig.so.1")
        fc.FcConfigGetCurrent.restype = ctypes.c_void_p
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        fc.FcConfigAppFontAddFile.restype = ctypes.c_int
        fc.FcConfigAppFontAddFile(fc.FcConfigGetCurrent(), path.encode())
    except Exception:
        pass


load_local_fonts()


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "updates-reel"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def rgb(ctx, c, a=1.0):
    ctx.set_source_rgba(*c, a)


def round_rect(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def layout(ctx, text, size, weight="bold", width=None, align="left", font="Lato"):
    lay = PangoCairo.create_layout(ctx)
    fd = Pango.FontDescription()
    fd.set_family(font)
    fd.set_absolute_size(size * Pango.SCALE)
    fd.set_weight(Pango.Weight.BOLD if weight == "bold" else Pango.Weight.NORMAL)
    lay.set_font_description(fd)
    if width:
        lay.set_width(int(width * Pango.SCALE))
        lay.set_alignment(
            {
                "left": Pango.Alignment.LEFT,
                "center": Pango.Alignment.CENTER,
                "right": Pango.Alignment.RIGHT,
            }[align]
        )
    lay.set_text(text, -1)
    return lay


def show(ctx, text, x, y, size, weight="bold", color=INK, width=None, align="left", font="Lato"):
    lay = layout(ctx, text, size, weight, width, align, font)
    rgb(ctx, color)
    ctx.move_to(x, y)
    PangoCairo.show_layout(ctx, lay)
    return lay.get_pixel_size()


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def lerp(a, b, u):
    return a + (b - a) * u


def mix(c0, c1, u):
    return tuple(lerp(a, b, u) for a, b in zip(c0, c1))


def palette_at(u):
    u = u % 1.0
    n = len(PALETTE)
    x = u * n
    i = int(x) % n
    return mix(PALETTE[i], PALETTE[(i + 1) % n], x - int(x))


def rainbow(x0, y0, x1, y1, shift=0.0):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    n = len(PALETTE)
    start = int(shift * n) % n
    for i in range(n + 1):
        g.add_color_stop_rgb(i / n, *PALETTE[(start + i) % n])
    return g


def icon_key(item):
    return item.get("icon") or item["name"]


def load_icons(items):
    folder = os.path.join(ROOT, "icons")
    icons = {}
    for item in items:
        key = icon_key(item)
        if key in icons:
            continue
        path = os.path.join(folder, ICON_FILES[key])
        icons[key] = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 192, 192)
    return icons


def paint_icon(ctx, pb, x, y, size, bg=None, pad=0, radius=26, clip=True):
    ctx.save()
    if clip:
        round_rect(ctx, x, y, size, size, radius)
        ctx.clip()
    if bg:
        rgb(ctx, bg)
        ctx.rectangle(x, y, size, size)
        ctx.fill()
    inner = max(1, size - 2 * pad)
    ctx.translate(x + pad, y + pad)
    ctx.scale(inner / pb.get_width(), inner / pb.get_height())
    Gdk.cairo_set_source_pixbuf(ctx, pb, 0, 0)
    ctx.paint()
    ctx.restore()


def pretty_date(iso):
    from datetime import datetime

    return datetime.strptime(iso, "%Y-%m-%d").strftime("%-d %b %Y").upper()


def age_label(day, today):
    from datetime import datetime

    if not day:
        return ""
    start = datetime.strptime(day, "%Y-%m-%d")
    end = datetime.strptime(today, "%Y-%m-%d")
    days = (end - start).days
    if days <= 0:
        return "TODAY"
    if days == 1:
        return "1 DAY AGO"
    if days < 7:
        return f"{days} DAYS AGO"
    weeks = days // 7
    if days < 30:
        return "1 WEEK AGO" if weeks == 1 else f"{weeks} WEEKS AGO"
    months = days // 30
    if days < 365:
        return "1 MONTH AGO" if months == 1 else f"{months} MONTHS AGO"
    years = days // 365
    return "1 YEAR AGO" if years == 1 else f"{years} YEARS AGO"


def measure_orbitron(ctx, title, size):
    glyphs = []
    cursor = 0.0
    for ch in title:
        lay = layout(ctx, ch, size, "bold", font="Orbitron")
        tw, th = lay.get_pixel_size()
        glyphs.append((ch, lay, tw, th, cursor))
        cursor += tw if ch != " " else size * 0.32
    return glyphs, cursor


def draw_copyright(ctx, color=DATE):
    show(
        ctx,
        COPYRIGHT,
        0,
        1856,
        22,
        "normal",
        color,
        width=W,
        align="center",
        font="Noto Sans CJK KR",
    )


def badge_text(item, today=None):
    if item["fresh"]:
        return "UPDATED TODAY"
    if item["yesterday"]:
        return "UPDATED YESTERDAY"
    if today and item.get("day"):
        age = age_label(item["day"], today)
        if age:
            return f"UPDATED {age}"
    return None


def glass_pane(ctx, x, y, w, h, top=0.22, mid=None, bot=0.08):
    pane = cairo.LinearGradient(x, y, x, y + h)
    pane.add_color_stop_rgba(0.00, 1, 1, 1, top)
    if mid is not None:
        pane.add_color_stop_rgba(0.45, 1, 1, 1, mid)
    pane.add_color_stop_rgba(1.00, 1, 1, 1, bot)
    ctx.set_source(pane)
    ctx.rectangle(x, y, w, h)
    ctx.fill()


def draw_badge(ctx, text, right, y, t, delay=0.0, size=28, align="right"):
    """Rainbow age pill. right is the right edge, or the center when align='center'."""
    from gi.repository import PangoCairo

    lay = layout(ctx, text, size, "bold")
    tw, th = lay.get_pixel_size()
    pad_x, pad_y = 16, 8
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x = right - bw / 2 if align == "center" else right - bw
    enter = ease((t - 0.14 - delay) / 0.22)
    if enter <= 0:
        return bh
    shift = (t * 0.85 + delay * 0.2) % 1.0
    sweep = (t * 1.05 + delay * 0.18) % 1.0

    ctx.save()
    ctx.push_group()
    ctx.rectangle(x, y, bw, bh)
    ctx.set_source(rainbow(x, y, x + bw, y + bh, shift))
    ctx.fill()

    ctx.save()
    ctx.rectangle(x, y, bw, bh)
    ctx.clip()
    sx = x + (sweep * 1.8 - 0.4) * bw
    shine = cairo.LinearGradient(sx, y, sx + bw * 0.32, y)
    shine.add_color_stop_rgba(0.00, 1, 1, 1, 0.00)
    shine.add_color_stop_rgba(0.50, 1, 1, 1, 0.28)
    shine.add_color_stop_rgba(1.00, 1, 1, 1, 0.00)
    ctx.set_source(shine)
    ctx.paint()
    ctx.restore()

    rgb(ctx, WHITE)
    ctx.move_to(x + pad_x, y + pad_y)
    PangoCairo.show_layout(ctx, lay)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(enter)
    ctx.restore()
    return bh


def draw_rows(ctx, items, today, t, icons, theme):
    """Wide glass rows: icon, name, version, date, age badge."""
    n = max(1, len(items))
    card_w = theme.get("card_w", 920)
    left = (W - card_w) / 2
    top = theme.get("top", 310)
    bottom = theme.get("bottom", 1788)
    gap = theme.get("gap", 24)
    card_h = (bottom - top - gap * (n - 1)) / n
    box = theme.get("box", 92)
    name_size = theme.get("name_size", 44)
    ver_size = theme.get("ver_size", 36)
    day_size = theme.get("day_size", 30)
    badge_size = theme.get("badge_size", 28)
    show_version = theme.get("show_version", True)
    ink = theme.get("ink", INK)
    date_color = theme.get("date", DATE)

    for i, item in enumerate(items):
        y = top + i * (card_h + gap)
        ctx.save()
        glass_pane(
            ctx,
            left,
            y,
            card_w,
            card_h,
            top=theme.get("pane_top", 0.22),
            mid=theme.get("pane_mid"),
            bot=theme.get("pane_bot", 0.08),
        )

        bx = left + 32
        by = y + (card_h - box) / 2
        key = icon_key(item)
        style = ICON_STYLE.get(key, {"bg": (1, 1, 1), "pad": 10})
        paint_icon(
            ctx,
            icons[key],
            bx,
            by,
            box,
            bg=style.get("bg"),
            pad=style.get("pad", 0),
            clip=style.get("clip", True),
        )

        ver = item["version"] if show_version else ""
        day = item["day"]
        right = left + card_w - 36
        vw = layout(ctx, ver, ver_size, "bold").get_pixel_size()[0] if ver else 0
        dw, dh = layout(ctx, day, day_size, "bold").get_pixel_size()
        vh = layout(ctx, ver or "0", ver_size, "bold").get_pixel_size()[1] if ver else 0
        name_x = left + 32 + box + 24
        max_name = right - max(vw, dw) - 36 - name_x
        size = name_size
        while size > 28 and layout(ctx, item["name"], size, "bold").get_pixel_size()[0] > max_name:
            size -= 2
        nw, nh = layout(ctx, item["name"], size, "bold").get_pixel_size()
        name_y = y + (card_h - nh) / 2
        show(ctx, item["name"], name_x, name_y, size, "bold", ink)

        badge = badge_text(item, today)
        badge_h = layout(ctx, badge, badge_size, "bold").get_pixel_size()[1] + 16 if badge else 0
        text_h = (vh + 8 + dh) if ver else dh
        block_h = (badge_h + 10 if badge else 0) + text_h
        block_y = y + (card_h - block_h) / 2
        if badge:
            draw_badge(ctx, badge, right, block_y, t, delay=i * 0.08, size=badge_size)
        text_y = block_y + (badge_h + 10 if badge else 0)
        if ver:
            show(ctx, ver, right - vw, text_y, ver_size, "bold", ink)
            text_y += vh + 8
        show(ctx, day, right - dw, text_y, day_size, "bold", date_color)
        ctx.restore()


def render(items, today, slug, title, draw_fn):
    tmp = tempfile.mkdtemp(prefix="reel_")
    icons = load_icons(items)
    try:
        n = int(round(DUR * FPS))
        for i in range(n):
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
            ctx = cairo.Context(surface)
            draw_fn(ctx, items, today, i / FPS, icons, title)
            surface.write_to_png(os.path.join(tmp, f"f{i:04d}.png"))
            if i % 30 == 0:
                print(f"{slug} frame {i}/{n}", flush=True)
        out = os.path.join(ROOT, f"reel_{slug}_{today}.mp4")
        subprocess.check_call(
            [
                "/usr/bin/ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                str(FPS),
                "-i",
                os.path.join(tmp, "f%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-crf",
                "20",
                "-preset",
                "veryfast",
                out,
            ]
        )
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
