"""Light glass tiles for LLM model updates."""

import math

import cairo
from gi.repository import PangoCairo

from .core import (
    DATE,
    H,
    ICON_STYLE,
    INK,
    W,
    WHITE,
    age_label,
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


def burst(ctx, count, radius, half, alpha, rot, wash, t):
    ctx.save()
    ctx.rotate(rot)
    for i in range(count):
        ang = i * math.pi * 2 / count
        hue = mix(palette_at(i / count + t * 0.05), (1, 1, 1), wash)
        rgb(ctx, hue, alpha)
        ctx.move_to(0, 0)
        ctx.arc(0, 0, radius, ang - half, ang + half)
        ctx.close_path()
        ctx.fill()
    ctx.restore()


def bg(ctx, t):
    sky = cairo.LinearGradient(0, 0, 0, H)
    sky.add_color_stop_rgb(0.00, 1.00, 0.98, 0.94)
    sky.add_color_stop_rgb(0.48, 0.97, 0.98, 1.00)
    sky.add_color_stop_rgb(1.00, 0.96, 0.97, 0.99)
    ctx.set_source(sky)
    ctx.paint()

    cx, cy = W / 2, H * 0.46
    core = cairo.RadialGradient(cx, cy, 30, cx, cy, 980)
    core.add_color_stop_rgba(0.00, 1.00, 0.97, 0.88, 0.72)
    core.add_color_stop_rgba(0.18, *mix(palette_at(t * 0.08), (1, 1, 1), 0.55), 0.22)
    core.add_color_stop_rgba(1.00, 1, 1, 1, 0.00)
    ctx.set_source(core)
    ctx.paint()

    ctx.save()
    ctx.translate(cx, cy)
    burst(ctx, 20, 2400, 0.078, 0.18, t * 0.10, 0.48, t)
    burst(ctx, 14, 2200, 0.032, 0.12, -t * 0.07, 0.38, t)
    burst(ctx, 28, 1400, 0.028, 0.10, t * 0.16, 0.32, t)
    ctx.restore()

    veil = cairo.LinearGradient(0, 0, 0, H)
    veil.add_color_stop_rgba(0.00, 1, 1, 1, 0.16)
    veil.add_color_stop_rgba(0.50, 1, 1, 1, 0.02)
    veil.add_color_stop_rgba(1.00, 1.00, 0.98, 0.95, 0.10)
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
    shift = (t * 0.85) % 1.0
    sweep = (t * 1.15) % 1.0

    for i, (ch, lay, tw, gh, ox) in enumerate(glyphs):
        if ch == " ":
            continue
        gx, gy = x0 + ox, y
        hue = mix(palette_at(shift + i * 0.08), (1, 1, 1), 0.38)

        ctx.save()
        ctx.move_to(gx, gy)
        PangoCairo.layout_path(ctx, lay)
        rgb(ctx, mix(hue, INK, 0.35), 0.92)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_width(12)
        ctx.stroke()
        ctx.restore()

        ctx.save()
        ctx.move_to(gx, gy)
        PangoCairo.layout_path(ctx, lay)
        ctx.clip()
        prism = cairo.LinearGradient(gx - tw, gy, gx + tw * 2.2, gy)
        for s in range(9):
            prism.add_color_stop_rgb(
                s / 8,
                *mix(palette_at(shift + s / 8 + i * 0.03), (1, 1, 1), 0.32),
            )
        ctx.set_source(prism)
        ctx.paint()

        sx = gx + (sweep * 1.8 - 0.4) * max(tw, 24)
        shine = cairo.LinearGradient(sx, gy, sx + max(tw, 24) * 0.45, gy)
        shine.add_color_stop_rgba(0.00, 1, 1, 1, 0.00)
        shine.add_color_stop_rgba(0.50, 1, 1, 1, 0.70)
        shine.add_color_stop_rgba(1.00, 1, 1, 1, 0.00)
        ctx.set_source(shine)
        ctx.paint()
        ctx.restore()

    show(ctx, date, 0, y + th + 16, 36, "bold", DATE, width=W, align="center")


def draw_badge(ctx, text, cx, y, t, delay=0.0):
    size = 26
    lay = layout(ctx, text, size, "bold")
    tw, th = lay.get_pixel_size()
    pad_x, pad_y = 16, 8
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x = cx - bw / 2
    enter = ease((t - 0.14 - delay) / 0.22)
    if enter <= 0:
        return bh
    shift = (t * 0.85 + delay * 0.2) % 1.0
    ctx.save()
    ctx.push_group()
    ctx.rectangle(x, y, bw, bh)
    ctx.set_source(rainbow(x, y, x + bw, y + bh, shift))
    ctx.fill()
    rgb(ctx, WHITE)
    ctx.move_to(x + pad_x, y + pad_y)
    PangoCairo.show_layout(ctx, lay)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(enter)
    ctx.restore()
    return bh


def glass_card(ctx, x, y, w, h):
    pane = cairo.LinearGradient(x, y, x, y + h)
    pane.add_color_stop_rgba(0.00, 1.00, 1.00, 1.00, 0.22)
    pane.add_color_stop_rgba(0.45, 1.00, 1.00, 1.00, 0.10)
    pane.add_color_stop_rgba(1.00, 1.00, 1.00, 1.00, 0.05)
    ctx.set_source(pane)
    ctx.rectangle(x, y, w, h)
    ctx.fill()


def draw(ctx, items, today, t, icons, title):
    bg(ctx, t)
    k = ease(t / 0.25) if t < 0.25 else 1.0
    ctx.push_group()
    draw_title(ctx, today, t, title)

    n = max(1, len(items))
    cols = 2
    rows = math.ceil(n / cols)
    gap_x, gap_y = 28, 26
    left = 56
    card_w = (W - left * 2 - gap_x * (cols - 1)) / cols
    top, bottom = 300, 1788
    card_h = (bottom - top - gap_y * (rows - 1)) / rows

    for i, item in enumerate(items):
        col = i % cols
        row = i // cols
        x = left + col * (card_w + gap_x)
        y = top + row * (card_h + gap_y)
        ctx.save()
        glass_card(ctx, x, y, card_w, card_h)

        box = 100
        bx = x + (card_w - box) / 2
        by = y + 40
        key = item.get("icon") or item["name"]
        style = ICON_STYLE.get(key, {"bg": None, "pad": 8, "clip": False})
        paint_icon(
            ctx,
            icons[key],
            bx,
            by,
            box,
            bg=style.get("bg"),
            pad=style.get("pad", 0),
            clip=False,
        )

        name = item["name"]
        name_size = 36
        name_y = by + box + 18
        nw, nh = layout(ctx, name, name_size, "bold").get_pixel_size()
        show(ctx, name, x, name_y, name_size, "bold", INK, width=card_w, align="center")

        dw, dh = layout(ctx, item["day"], 36, "bold").get_pixel_size()
        day_y = name_y + nh + 10
        show(ctx, item["day"], x, day_y, 36, "bold", DATE, width=card_w, align="center")

        badge = badge_text(item) or age_label(item["day"], today)
        if badge:
            draw_badge(ctx, badge, x + card_w / 2, day_y + dh + 10, t, delay=i * 0.08)
        ctx.restore()

    draw_copyright(ctx)
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(k)
