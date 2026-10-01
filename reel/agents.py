"""Glass theme for coding-agent version updates."""

import math

import cairo
from gi.repository import PangoCairo

from .core import (
    DATE,
    H,
    ICON_STYLE,
    INK,
    W,
    badge_text,
    draw_copyright,
    ease,
    layout,
    measure_orbitron,
    mix,
    paint_icon,
    palette_at,
    pretty_date,
    rainbow,
    rgb,
    show,
)


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


def draw(ctx, items, today, t, icons, title):
    bg(ctx, t)
    k = ease(t / 0.25) if t < 0.25 else 1.0
    ctx.push_group()
    draw_title(ctx, today, t, title, size=56)

    n = max(1, len(items))
    card_w = 920
    left = (W - card_w) / 2
    top, bottom = 310, 1788
    gap = 24
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
        key = item.get("icon") or item["name"]
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

        name_size = 44
        nw, nh = layout(ctx, item["name"], name_size, "bold").get_pixel_size()
        name_y = y + (card_h - nh) / 2
        show(ctx, item["name"], left + 148, name_y, name_size, "bold", INK)

        ver = item["version"]
        vw, vh = layout(ctx, ver, name_size, "bold").get_pixel_size()
        dw, dh = layout(ctx, item["day"], 36, "bold").get_pixel_size()
        right = left + card_w - 36
        badge = badge_text(item, today)
        if badge:
            bh = layout(ctx, badge, 28, "bold").get_pixel_size()[1] + 16
            draw_badge(ctx, badge, right, name_y - 10 - bh, t, delay=i * 0.08)
        show(ctx, ver, right - vw, name_y, name_size, "bold", INK)
        show(ctx, item["day"], right - dw, name_y + nh + 6, 36, "bold", DATE)
        ctx.restore()

    draw_copyright(ctx)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(k)
