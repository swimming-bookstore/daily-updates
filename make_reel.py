#!/usr/bin/env python3
"""Vertical reel — coding agents. Highlight a row only if it shipped today."""

import ctypes
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone

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
OUTDIR = os.path.dirname(os.path.abspath(__file__))


def load_local_fonts():
    path = os.path.join(OUTDIR, "fonts", "Orbitron.ttf")
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

INK = (0.16, 0.11, 0.12)
TEAL = (0.18, 0.52, 0.62)
MUTED = (0.42, 0.34, 0.34)
CARD = (1.0, 0.99, 0.97)
CREAM = (0.98, 0.94, 0.90)
DATE = (0.30, 0.36, 0.48)

# Claude Code, Codex, Pi, then OpenClaw, Hermes Agent, Cline.
SOURCES = [
    {"name": "Claude Code", "npm": "https://registry.npmjs.org/@anthropic-ai/claude-code"},
    {"name": "Codex", "npm": "https://registry.npmjs.org/@openai/codex"},
    {"name": "Pi", "npm": "https://registry.npmjs.org/@earendil-works/pi-coding-agent"},
    {"name": "OpenClaw", "npm": "https://registry.npmjs.org/openclaw"},
    {
        "name": "Hermes Agent",
        "github": "https://api.github.com/repos/NousResearch/hermes-agent/releases/latest",
    },
    {"name": "Cline", "npm": "https://registry.npmjs.org/cline"},
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "updates-reel"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def latest_version(data):
    """Newest publish, skipping per-platform package builds."""
    skip = ("darwin", "linux", "win32", "arm64", "x64")
    times = data.get("time", {})
    versions = [
        v for v in times
        if v not in ("modified", "created") and not any(part in v for part in skip)
    ]
    if not versions:
        return data["dist-tags"]["latest"]
    return max(versions, key=lambda v: times[v])


def load_npm(src):
    data = fetch_json(src["npm"])
    version = latest_version(data)
    published = data["time"][version]
    return version, published


def load_github(src):
    try:
        data = fetch_json(src["github"])
        version = (data.get("tag_name") or "").lstrip("v")
        name = data.get("name") or ""
        # "Hermes Agent v0.21.5 (v2026.9.24)" — show the semver, date comes from published_at.
        if " v" in name:
            version = name.split(" v", 1)[1].split(" ", 1)[0].split("(", 1)[0]
        published = data.get("published_at") or ""
        return version, published
    except Exception:
        html_url = src["github"].replace("https://api.github.com/repos/", "https://github.com/").replace("/releases/latest", "/releases/latest")
        req = urllib.request.Request(html_url, headers={"User-Agent": "updates-reel"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", "ignore")
            final = resp.geturl()
        tag = final.rsplit("/", 1)[-1].lstrip("v")
        version = tag
        m = re.search(r"Hermes Agent v([0-9]+\.[0-9]+\.[0-9]+)", html)
        if m:
            version = m.group(1)
        published = ""
        m = re.search(r'datetime="([0-9T:\-Z]+)"', html)
        if m:
            published = m.group(1)
        return version, published


def load_items(today, yesterday):
    items = []
    for src in SOURCES:
        version, published = load_github(src) if src.get("github") else load_npm(src)
        day = published[:10]
        items.append(
            {
                "name": src["name"],
                "version": version,
                "published": published,
                "day": day,
                "fresh": day == today,
                "yesterday": day == yesterday,
            }
        )
    return items


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
            {"left": Pango.Alignment.LEFT, "center": Pango.Alignment.CENTER, "right": Pango.Alignment.RIGHT}[align]
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


def pop(t):
    t = max(0.0, min(1.0, t))
    c1 = 1.4
    c3 = c1 + 1
    return max(0.05, 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2)


def lerp(a, b, u):
    return a + (b - a) * u


def mix(c0, c1, u):
    return tuple(lerp(a, b, u) for a, b in zip(c0, c1))


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


def draw_badge(ctx, text, right, y, t, delay=0.0):
    size = 28
    lay = layout(ctx, text, size, "bold")
    tw, th = lay.get_pixel_size()
    pad_x, pad_y = 16, 8
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x = right - bw
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

    rgb(ctx, (1, 1, 1))
    ctx.move_to(x + pad_x, y + pad_y)
    PangoCairo.show_layout(ctx, lay)

    ctx.pop_group_to_source()
    ctx.paint_with_alpha(enter)
    ctx.restore()
    return bh


def bg(ctx, t):
    sky = cairo.LinearGradient(0, 0, 0, H)
    sky.add_color_stop_rgb(0.00, 0.93, 0.97, 0.99)
    sky.add_color_stop_rgb(0.42, 0.96, 0.94, 0.98)
    sky.add_color_stop_rgb(1.00, 0.90, 0.95, 0.97)
    ctx.set_source(sky)
    ctx.paint()

    ctx.save()
    ctx.set_line_width(90)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    bands = (
        ((0.42, 0.78, 0.90), 0.22, 0.18, 1.1, 140),
        ((0.78, 0.68, 0.94), 0.18, 0.42, 0.85, 320),
        ((0.55, 0.86, 0.82), 0.16, 0.70, 0.95, 520),
        ((0.68, 0.80, 0.96), 0.14, 1.05, 0.75, 780),
        ((0.80, 0.74, 0.92), 0.12, 1.38, 1.05, 1080),
    )
    for color, a, phase, speed, base in bands:
        rgb(ctx, color, a)
        ctx.new_path()
        amp = 48 + 18 * math.sin(t * 0.4 + phase)
        for x in range(-40, W + 80, 16):
            yy = (
                base
                + math.sin(x * 0.008 + t * speed + phase) * amp
                + math.sin(x * 0.018 - t * speed * 0.6 + phase * 2) * 22
            )
            if x <= -40:
                ctx.move_to(x, yy)
            else:
                ctx.line_to(x, yy)
        ctx.stroke()
    ctx.restore()

    veil = cairo.LinearGradient(0, 0, 0, H)
    veil.add_color_stop_rgba(0.00, 1, 1, 1, 0.18)
    veil.add_color_stop_rgba(0.45, 1, 1, 1, 0.04)
    veil.add_color_stop_rgba(1.00, 0.72, 0.82, 0.92, 0.16)
    ctx.set_source(veil)
    ctx.paint()


# Official product marks (not invented glyphs).
ICON_FILES = {
    "Claude Code": "claude.svg",
    "Codex": "codex.png",
    "Pi": "pi.svg",
    "OpenClaw": "openclaw.svg",
    "Hermes Agent": "hermes.svg",
    "Cline": "cline.png",
}
# App icons already include a rounded tile. Wordmarks/logos stay unclipped.
ICON_STYLE = {
    "Claude Code": {"bg": None, "pad": 6, "clip": False},
    "Codex": {"bg": None, "pad": 0, "clip": False},
    "Pi": {"bg": (0.067, 0.067, 0.067), "pad": 0, "clip": False},
    "OpenClaw": {"bg": None, "pad": 0, "clip": False},
    "Hermes Agent": {"bg": None, "pad": 0},
    "Cline": {"bg": None, "pad": 0},
}


def load_icons():
    folder = os.path.join(OUTDIR, "icons")
    icons = {}
    for name, fname in ICON_FILES.items():
        path = os.path.join(folder, fname)
        icons[name] = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 192, 192)
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
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%-d %b %Y").upper()


def spaced(ctx, text, size, tracking, weight="bold", width=None, align="center"):
    lay = layout(ctx, text, size, weight, width, align)
    attrs = Pango.AttrList()
    attrs.insert(Pango.attr_letter_spacing_new(int(tracking * Pango.SCALE)))
    lay.set_attributes(attrs)
    return lay


def draw_title(ctx, today, t):
    title = "Claude Code Version Update"
    date = pretty_date(today)
    size = 44
    y = 96

    glyphs = []
    cursor = 0.0
    for ch in title:
        lay = layout(ctx, ch, size, "bold", font="Orbitron")
        tw, th = lay.get_pixel_size()
        glyphs.append((ch, lay, tw, th, cursor))
        cursor += tw if ch != " " else size * 0.32
    total = cursor
    x0 = (W - total) / 2
    th = max(g[3] for g in glyphs)

    ctx.save()
    for i, (ch, lay, tw, gh, ox) in enumerate(glyphs):
        if ch == " ":
            continue
        color = palette_at(t * 0.22 + i / max(1, len(glyphs)) * 0.85)
        color = mix(color, (1, 1, 1), 0.16)
        ctx.save()
        ctx.move_to(x0 + ox, y)
        rgb(ctx, color)
        PangoCairo.show_layout(ctx, lay)
        ctx.restore()
    ctx.restore()

    show(ctx, date, 0, y + th + 18, 36, "bold", DATE, width=W, align="center")


def draw(ctx, items, today, t, icons):
    bg(ctx, t)
    k = ease(t / 0.25) if t < 0.25 else 1.0
    ctx.push_group()

    draw_title(ctx, today, t)

    n = max(1, len(items))
    card_w = 920
    left = (W - card_w) / 2
    top, bottom = 300, 1820
    gap = 28
    card_h = (bottom - top - gap * (n - 1)) / n

    for i, item in enumerate(items):
        y = top + i * (card_h + gap)
        ctx.save()

        pane = cairo.LinearGradient(left, y, left, y + card_h)
        pane.add_color_stop_rgba(0.00, 1.00, 1.00, 1.00, 0.22)
        pane.add_color_stop_rgba(1.00, 1.00, 1.00, 1.00, 0.08)
        ctx.set_source(pane)
        ctx.rectangle(left, y, card_w, card_h)
        ctx.fill()

        box = 92
        bx = left + 32
        by = y + (card_h - box) / 2
        style = ICON_STYLE.get(item["name"], {"bg": (1, 1, 1), "pad": 10})
        paint_icon(
            ctx,
            icons[item["name"]],
            bx,
            by,
            box,
            bg=style.get("bg"),
            pad=style.get("pad", 0),
            clip=style.get("clip", True),
        )

        nw, nh = layout(ctx, item["name"], 44, "bold").get_pixel_size()
        show(ctx, item["name"], left + 148, y + (card_h - nh) / 2, 44, "bold", INK)

        ver = item["version"]
        vw, vh = layout(ctx, ver, 40, "bold").get_pixel_size()
        dw, dh = layout(ctx, item["day"], 28, "bold").get_pixel_size()
        stack = vh + 6 + dh
        if item["fresh"]:
            badge = "UPDATED"
        elif item["yesterday"]:
            badge = "UPDATED YESTERDAY"
        else:
            badge = None
        sy = y + (card_h - stack) / 2
        right = left + card_w - 36
        if badge:
            bh = layout(ctx, badge, 28, "bold").get_pixel_size()[1] + 16
            draw_badge(ctx, badge, right, sy - 10 - bh, t, delay=i * 0.08)
        show(ctx, ver, right - vw, sy, 40, "bold", INK)
        show(ctx, item["day"], right - dw, sy + vh + 6, 28, "bold", DATE)
        ctx.restore()

    ctx.pop_group_to_source()
    ctx.paint_with_alpha(k)


def render(items, today):
    tmp = tempfile.mkdtemp(prefix="reel_")
    icons = load_icons()
    try:
        n = int(round(DUR * FPS))
        for i in range(n):
            surface = cairo.ImageSurface(cairo.FORMAT_RGB24, W, H)
            ctx = cairo.Context(surface)
            draw(ctx, items, today, i / FPS, icons)
            surface.write_to_png(os.path.join(tmp, f"f{i:04d}.png"))
            if i % 30 == 0:
                print(f"frame {i}/{n}", flush=True)
        out = os.path.join(OUTDIR, f"reel_claude_code_version_update_{today}.mp4")
        subprocess.check_call(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-framerate", str(FPS),
                "-i", os.path.join(tmp, "f%04d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", "-crf", "20",
                "-preset", "veryfast",
                out,
            ]
        )
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    items = load_items(today, yesterday)
    for item in items:
        if item["fresh"]:
            mark = "UPDATED"
        elif item["yesterday"]:
            mark = "UPDATED YESTERDAY"
        else:
            mark = "quiet"
        print(f"{item['name']} v{item['version']} {item['published']} {mark}", flush=True)
    print("wrote", render(items, today), flush=True)


if __name__ == "__main__":
    main()
