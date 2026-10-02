"""Glass theme for coding-agent version updates."""

import math

import cairo
from gi.repository import PangoCairo

from .core import (
    DATE,
    H,
    W,
    draw_copyright,
    draw_rows,
    ease,
    measure_orbitron,
    mix,
    palette_at,
    pretty_date,
    rgb,
    show,
)


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


def draw_title(ctx, today, t, title, size=56):
    date = pretty_date(today)
    y = 84
    glyphs, total = measure_orbitron(ctx, title, size)
    if total > W - 56:
        size = size * (W - 56) / total
        glyphs, total = measure_orbitron(ctx, title, size)
    x0 = (W - total) / 2
    th = max(g[3] for g in glyphs)

    for i, (ch, lay, tw, gh, ox) in enumerate(glyphs):
        if ch == " ":
            continue
        color = mix(palette_at(t * 0.22 + i / max(1, len(glyphs)) * 0.85), (1, 1, 1), 0.16)
        ctx.save()
        ctx.move_to(x0 + ox, y)
        rgb(ctx, color)
        PangoCairo.show_layout(ctx, lay)
        ctx.restore()

    show(ctx, date, 0, y + th + 16, 36, "bold", DATE, width=W, align="center")


THEME = {
    "card_w": 920,
    "top": 310,
    "bottom": 1788,
    "gap": 24,
    "box": 92,
    "name_size": 44,
    "ver_size": 36,
    "day_size": 30,
    "badge_size": 28,
    "show_version": True,
    "pane_top": 0.22,
    "pane_bot": 0.08,
}


def draw(ctx, items, today, t, icons, title):
    bg(ctx, t)
    k = ease(t / 0.25) if t < 0.25 else 1.0
    ctx.push_group()
    draw_title(ctx, today, t, title, size=56)
    draw_rows(ctx, items, today, t, icons, THEME)
    draw_copyright(ctx)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(k)
